# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Campaign API â€” REST endpoints for campaign state, notes, and continuity.
"""
import json
import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from pydantic import BaseModel, Field

from app.agents.continuity import ContinuityAgent, ContinuityKeeper
from app.api.deps import get_repo
from app.api.security import (
    AuditLogger,
    get_client_ip,
    require_auth,
)
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.llm.orchestrator import LLMOrchestrator

logger = logging.getLogger(__name__)

audit_logger = AuditLogger()

router = APIRouter(prefix="/campaign", tags=["campaign"])


class CampaignNote(BaseModel):
    # Bounded: both fields are appended verbatim into sessions.raw_log and then
    # re-spliced into the GM system prompt, so an unbounded string grew the
    # database and the prompt without limit.
    prompt: str = Field(..., min_length=1, max_length=4000)
    response: str = Field(..., min_length=1, max_length=4000)


class CampaignStateResponse(BaseModel):
    party: list[dict]
    notes: list[dict]


class NoteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    response: str = Field(..., min_length=1, max_length=4000)


class CampaignExport(BaseModel):
    """Complete campaign export for backup/transfer."""
    campaign: dict
    party: list[dict]
    npcs: list[dict]
    locations: list[dict]
    items: list[dict]
    quests: list[dict]
    sessions: list[dict]
    party_members: list[dict]
    notes: list[dict]
    decisions: list[dict]
    exported_at: str
    version: str


class CampaignImport(BaseModel):
    # Every list is capped. These were `list[dict] | None` with no bound, and
    # the import handler iterates them one row at a time, each opening its own
    # sqlite connection and INSERT, so a single request could drive hundreds of
    # thousands of round-trips against the campaign DB.
    campaign: dict | None = None
    party: list[dict] | None = Field(default=None, max_length=500)
    npcs: list[dict] | None = Field(default=None, max_length=500)
    locations: list[dict] | None = Field(default=None, max_length=500)
    items: list[dict] | None = Field(default=None, max_length=500)
    quests: list[dict] | None = Field(default=None, max_length=500)
    party_members: list[dict] | None = Field(default=None, max_length=500)
    sessions: list[dict] | None = Field(default=None, max_length=500)
    notes: list[dict] | None = Field(default=None, max_length=500)
    decisions: list[dict] | None = Field(default=None, max_length=500)
    replace_existing: bool = True


class SummarizeSessionRequest(BaseModel):
    # Bounded: unbounded `events` was sent straight to Ollama, so one request
    # could occupy the CPU-only box with an arbitrarily large body.
    events: list[str] = Field(default_factory=list, max_length=500)
    campaign_name: str = Field(default="Untitled Campaign", max_length=200)


class SummarizeSessionResponse(BaseModel):
    summary: str
    event_count: int


@router.get("", response_model=CampaignStateResponse)
async def get_campaign(
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
    request: Request = None,
) -> CampaignStateResponse:
    """Get current campaign state (party + session notes)."""
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign",
        action="read",
        ip=get_client_ip(request) if request else "unknown"
    )
    state = repo.get_campaign_state(campaign_id)
    return CampaignStateResponse(**state)


@router.post("/note", response_model=CampaignStateResponse)
async def add_campaign_note(
    note: CampaignNote,
    background_tasks: BackgroundTasks,
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
    request: Request = None,
) -> CampaignStateResponse:
    """
    Add a note to the campaign log.
    Triggers Continuity Keeper in background to extract entities and summarize.
    """
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign_note",
        action="create",
        ip=get_client_ip(request) if request else "unknown"
    )
    
    session_num = repo.get_latest_session_num(campaign_id) + 1

    repo.add_session_note(campaign_id, session_num, note.prompt, note.response)

    orchestrator = LLMOrchestrator(repo)
    continuity_keeper = ContinuityKeeper(repo, orchestrator)
    async def _safe_process():
        try:
            await continuity_keeper.process_session(campaign_id, session_num, note.prompt + "\n" + note.response)
        except Exception as e:
            logger.warning(f"Continuity processing failed: {e}")
    background_tasks.add_task(_safe_process)

    state = repo.get_campaign_state(campaign_id)
    return CampaignStateResponse(**state)


@router.post("/reset", response_model=CampaignStateResponse)
async def reset_campaign(
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
    request: Request = None,
) -> CampaignStateResponse:
    """Reset campaign to empty state."""
    audit_logger.log_admin_action(
        admin_id=user.get("sub", "unknown"),
        action="reset_campaign",
        target=f"campaign_{campaign_id}",
        ip=get_client_ip(request)
    )
    repo.reset_campaign(campaign_id)
    repo.get_or_create_campaign(campaign_id)
    state = repo.get_campaign_state(campaign_id)
    return CampaignStateResponse(**state)


@router.post("/summarize-session", response_model=SummarizeSessionResponse)
async def summarize_session(
    request: SummarizeSessionRequest,
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> SummarizeSessionResponse:
    """Turn raw session events into an atmospheric journal entry."""
    clean = [e.strip() for e in request.events if e and e.strip()]
    if not clean:
        raise HTTPException(status_code=400, detail="No events to summarize")
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    agent = ContinuityAgent(llm)
    try:
        journal = await agent.summarize_session(clean, request.campaign_name)
    except RuntimeError:
        # Logged, not returned: the RuntimeError text can name model internals.
        logger.exception("session summarization failed")
        raise HTTPException(status_code=503, detail="An internal error occurred.")
    finally:
        await llm.close()
    return SummarizeSessionResponse(summary=journal.summary, event_count=journal.event_count)


@router.get("/export", response_model=CampaignExport, tags=["campaign", "export"])
async def export_campaign(
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
    request: Request = None,
) -> CampaignExport:
    """Export complete campaign data for backup or transfer."""
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign",
        action="export",
        ip=get_client_ip(request)
    )
    
    campaign = repo.get_or_create_campaign(campaign_id)
    party = repo.get_party(campaign_id)
    npcs = repo.get_npcs(campaign_id)
    locations = repo.get_locations(campaign_id)
    
    with repo._conn() as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM items WHERE campaign_id = ?", (campaign_id,)).fetchall()]
        quests = [dict(r) for r in conn.execute("SELECT * FROM quests WHERE campaign_id = ?", (campaign_id,)).fetchall()]
        sessions = [dict(r) for r in conn.execute("SELECT * FROM sessions WHERE campaign_id = ? ORDER BY session_num", (campaign_id,)).fetchall()]
        party_members = [dict(r) for r in conn.execute("SELECT * FROM party_members WHERE campaign_id = ?", (campaign_id,)).fetchall()]
        notes = [dict(r) for r in conn.execute("SELECT * FROM session_notes WHERE campaign_id = ? ORDER BY created_at DESC", (campaign_id,)).fetchall()]
        decisions = [dict(r) for r in conn.execute("SELECT * FROM player_decisions WHERE campaign_id = ? ORDER BY created_at DESC", (campaign_id,)).fetchall()]
    
    export = CampaignExport(
        campaign=dict(campaign.__dict__) if campaign else {},
        party=party,
        npcs=[dict(npc.__dict__) for npc in npcs],
        locations=[dict(loc.__dict__) for loc in locations],
        items=items,
        quests=quests,
        sessions=sessions,
        party_members=party_members,
        notes=notes,
        decisions=decisions,
        exported_at=datetime.now(UTC).isoformat(),
        version="1.0",
    )
    
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign",
        action="export",
        ip=get_client_ip(request)
    )
    
    return export


@router.post("/import", response_model=CampaignStateResponse, tags=["campaign", "import"])
async def import_campaign(
    import_data: CampaignImport,
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
    request: Request = None,
) -> CampaignStateResponse:
    """Import campaign data from backup. Use replace_existing=true to overwrite."""
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign",
        action="import",
        ip=get_client_ip(request)
    )
    
    if import_data.campaign:
        repo.get_or_create_campaign(campaign_id)
        if import_data.replace_existing:
            with repo._conn() as conn:
                # campaigns.name and .edition are NOT NULL, so a partial
                # campaign payload used to raise IntegrityError -> 500.
                conn.execute(
                    "UPDATE campaigns SET name=?, edition=? WHERE id=?",
                    (
                        import_data.campaign.get("name") or f"Campaign {campaign_id}",
                        import_data.campaign.get("edition") or "2e",
                        campaign_id,
                    ),
                )

    # Every block below used to splat the raw row with **row. export_campaign
    # emits SELECT *-shaped dicts carrying id, campaign_id, created_at,
    # updated_at and DB column names (class, type, stats_json, traits_json),
    # while the repository signatures want class_, type_, stats, traits. The
    # first campaign_id collision alone was
    #   TypeError: upsert_party_member() got multiple values for 'campaign_id'
    # so /campaign/import could not import its own export - backup/restore was
    # 100% broken. Fields are now whitelisted and renamed explicitly.
    def _json_list(value) -> list:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return []
        return value or []

    def _safe_int(value, default, *, field: str = "value"):
        """int() that reports a 400 instead of raising an unhandled 500.

        Imported payloads are arbitrary nested JSON, so `int(x)` on a string
        like "high" or a dict used to raise ValueError/TypeError straight out
        of the handler and surface as a 500 with a traceback.
        """
        if value is None or value == "":
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid integer for {field}: {value!r}",
            ) from None

    if import_data.party:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM party_members WHERE campaign_id = ?", (campaign_id,))
        # One connection for the whole party (was one per member).
        repo.upsert_party_batch(
            campaign_id,
            [
                {
                    "name": member.get("name"),
                    "player_name": member.get("player_name"),
                    "class_": member.get("class_", member.get("class")),
                    "level": _safe_int(member.get("level"), 1, field="party.level"),
                    "ancestry": member.get("ancestry"),
                    "background": member.get("background"),
                    "stats": _json_list(member.get("stats", member.get("stats_json"))) or None,
                }
                for member in import_data.party
            ],
        )

    if import_data.npcs and import_data.replace_existing:
        with repo._conn() as conn:
            conn.execute("DELETE FROM npcs WHERE campaign_id = ?", (campaign_id,))

    if import_data.locations and import_data.replace_existing:
        with repo._conn() as conn:
            conn.execute("DELETE FROM locations WHERE campaign_id = ?", (campaign_id,))

    if import_data.items and import_data.replace_existing:
        with repo._conn() as conn:
            conn.execute("DELETE FROM items WHERE campaign_id = ?", (campaign_id,))

    if import_data.quests and import_data.replace_existing:
        with repo._conn() as conn:
            conn.execute("DELETE FROM quests WHERE campaign_id = ?", (campaign_id,))

    # One connection, one commit for the whole entity set (O2). Previously each
    # entity opened its own sqlite connection - roughly 50 for a typical
    # extraction - and each also ran its own _ensure_campaign INSERT.
    if import_data.npcs or import_data.locations or import_data.items or import_data.quests:
        repo.upsert_entities_batch(
            campaign_id,
            npcs=[
                {
                    "name": npc.get("name"),
                    "alias": npc.get("alias"),
                    "role": npc.get("role"),
                    "level": _safe_int(npc.get("level"), None, field="npcs.level"),
                    "ancestry": npc.get("ancestry"),
                    "class_": npc.get("class_", npc.get("class")),
                    "disposition": npc.get("disposition"),
                    "notes": npc.get("notes"),
                }
                for npc in (import_data.npcs or [])
            ],
            locations=[
                {
                    "name": loc.get("name"),
                    "type": loc.get("type") or loc.get("type_"),
                    "parent_name": loc.get("parent_name"),
                    "description": loc.get("description"),
                }
                for loc in (import_data.locations or [])
            ],
            items=[
                {
                    "name": item.get("name"),
                    "type": item.get("type") or item.get("type_"),
                    "level": _safe_int(item.get("level"), None, field="items.level"),
                    "traits": _json_list(item.get("traits", item.get("traits_json"))),
                    "holder_name": item.get("holder_name"),
                    "location_name": item.get("location_name"),
                    "notes": item.get("notes"),
                }
                for item in (import_data.items or [])
            ],
            quests=[
                {
                    "name": quest.get("name"),
                    "status": quest.get("status"),
                    "giver_name": quest.get("giver_name"),
                    "description": quest.get("description"),
                    "objectives": _json_list(
                        quest.get("objectives", quest.get("objectives_json"))
                    ),
                    "rewards": _json_list(quest.get("rewards", quest.get("rewards_json"))),
                }
                for quest in (import_data.quests or [])
            ],
        )

    # party_members is deliberately NOT handled here: it targets the same table as
    # `party` (get_party() and SELECT * FROM party_members are the same rows).
    # With replace_existing the second DELETE wiped what the first block had
    # just inserted, so a payload where the two differed lost the party silently.

    if import_data.sessions:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM sessions WHERE campaign_id = ?", (campaign_id,))
        # One connection for the whole history. The sessions_fts triggers fire
        # per row inside the shared transaction, so imported sessions are
        # searchable immediately via search_sessions.
        repo.insert_sessions_batch(
            campaign_id,
            [
                {
                    "session_num": _safe_int(
                        session.get("session_num"), 1, field="sessions.session_num"
                    ),
                    "summary": session.get("summary", ""),
                    "facts": _json_list(session.get("facts", session.get("facts_json", []))),
                    "raw_log": session.get("raw_log", ""),
                }
                for session in import_data.sessions
            ],
        )

    if import_data.notes:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM session_notes WHERE campaign_id = ?", (campaign_id,))
        # Bulk insert in one transaction. This loop previously opened a whole
        # sqlite connection - connect, PRAGMA, insert, commit, close - for every
        # single note, so restoring a large campaign cost one connection per row.
        note_rows = [
            (
                _safe_int(note.get("session_num"), 1, field="notes.session_num"),
                str(note.get("note_type") or "gm"),
                str(note.get("content") or ""),
            )
            for note in import_data.notes
        ]
        repo.insert_session_notes(campaign_id, note_rows)

    if import_data.decisions:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM player_decisions WHERE campaign_id = ?", (campaign_id,))
        for decision in import_data.decisions:
            repo.add_decision(
                campaign_id=campaign_id,
                session_num=int(decision.get("session_num", 1)),
                decision=decision.get("decision", ""),
                context=decision.get("context"),
                consequences=decision.get("consequences"),
                made_by=decision.get("made_by", "party"),
            )

    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign",
        action="import",
        ip=get_client_ip(request)
    )
    
    state = repo.get_campaign_state(campaign_id)
    return CampaignStateResponse(**state)


@router.get("/backup", response_class=Response, tags=["campaign", "export"])
async def download_backup(
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
    request: Request = None,
):
    """Download campaign backup as JSON file."""
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign",
        action="backup_download",
        ip=get_client_ip(request)
    )
    
    export = await export_campaign(campaign_id, repo, user, request)
    
    import json

    from fastapi.responses import Response
    
    filename = f"pathfinder_campaign_{campaign_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    
    return Response(
        content=json.dumps(export.model_dump(), indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


class NPCRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    alias: str | None = Field(None, max_length=120)
    # schema.sql CHECKs restrict these to a fixed set. As free strings any other
    # value raised an unhandled sqlite3.IntegrityError -> 500, so
    # {"name":"X","role":"silly"} returned a server error instead of a 422.
    role: Literal["ally", "enemy", "neutral", "unknown"] = "unknown"
    level: int | None = Field(None, ge=0, le=30)
    ancestry: str | None = Field(None, max_length=60)
    class_: str | None = Field(None, alias="class", max_length=60)
    disposition: Literal["friendly", "hostile", "wary", "unknown"] = "unknown"
    notes: str | None = Field(None, max_length=4000)


@router.get("/npcs")
async def list_npcs(
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> list[dict]:
    npcs = repo.get_npcs(campaign_id)
    return [dict(npc.__dict__) for npc in npcs]


@router.post("/npcs")
async def create_npc(
    npc: NPCRequest,
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> dict:
    npc_id = repo.upsert_npc(
        campaign_id=campaign_id,
        name=npc.name,
        alias=npc.alias,
        role=npc.role,
        level=npc.level,
        ancestry=npc.ancestry,
        class_=npc.class_,
        disposition=npc.disposition,
        notes=npc.notes,
    )
    return {"id": npc_id, "name": npc.name}


class PartyMemberRequest(BaseModel):
    # Mirrors NPCRequest. Previously every field here was a bare str/int, so a
    # 10MB "name" or a negative "level" went straight into party_members.
    name: str = Field(..., min_length=1, max_length=120)
    player_name: str | None = Field(None, max_length=120)
    class_: str | None = Field(None, alias="class", max_length=60)
    level: int = Field(1, ge=0, le=30)
    ancestry: str | None = Field(None, max_length=60)
    background: str | None = Field(None, max_length=120)
    stats: dict | None = None


@router.get("/party")
async def list_party(
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> list[dict]:
    return repo.get_party(campaign_id)


@router.post("/party")
async def add_party_member(
    member: PartyMemberRequest,
    campaign_id: int = Query(1, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> dict:
    member_id = repo.upsert_party_member(
        campaign_id=campaign_id,
        name=member.name,
        player_name=member.player_name,
        class_=member.class_,
        level=member.level,
        ancestry=member.ancestry,
        background=member.background,
        stats=member.stats,
    )
    return {"id": member_id, "name": member.name}