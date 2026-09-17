# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Campaign API — REST endpoints for campaign state, notes, and continuity.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.api.deps import get_repo
from app.db.repository import CampaignRepository
from app.agents.continuity import ContinuityKeeper, ContinuityAgent
from app.llm.orchestrator import LLMOrchestrator
from app.llm.ollama_client import OllamaClient
from app.config import get_settings
from app.api.security import get_audit_logger, get_current_user, require_auth, get_client_ip, AuditLogger

import json
import logging
logger = logging.getLogger(__name__)

audit_logger = AuditLogger()

router = APIRouter(prefix="/campaign", tags=["campaign"])


# ──────────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────────

class CampaignNote(BaseModel):
    prompt: str
    response: str


class CampaignStateResponse(BaseModel):
    party: list[dict]
    notes: list[dict]


class NoteRequest(BaseModel):
    prompt: str
    response: str


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
    campaign: Optional[dict] = None
    party: Optional[list[dict]] = None
    npcs: Optional[list[dict]] = None
    locations: Optional[list[dict]] = None
    items: Optional[list[dict]] = None
    quests: Optional[list[dict]] = None
    party_members: Optional[list[dict]] = None
    sessions: Optional[list[dict]] = None
    notes: Optional[list[dict]] = None
    decisions: Optional[list[dict]] = None
    replace_existing: bool = True


class SummarizeSessionRequest(BaseModel):
    events: list[str] = Field(default_factory=list)
    campaign_name: str = "Untitled Campaign"


class SummarizeSessionResponse(BaseModel):
    summary: str
    event_count: int


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────

@router.get("", response_model=CampaignStateResponse)
async def get_campaign(
    campaign_id: int = 1,
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> CampaignStateResponse:
    """Get current campaign state (party + session notes)."""
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign",
        action="read",
        ip=get_client_ip(request) if 'request' in locals() else "unknown"
    )
    state = repo.get_campaign_state(campaign_id)
    return CampaignStateResponse(**state)


@router.post("/note", response_model=CampaignStateResponse)
async def add_campaign_note(
    note: CampaignNote,
    background_tasks: BackgroundTasks,
    campaign_id: int = 1,
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> CampaignStateResponse:
    """
    Add a note to the campaign log.
    Triggers Continuity Keeper in background to extract entities and summarize.
    """
    audit_logger.log_data_access(
        user_id=user.get("sub", "unknown"),
        resource="campaign_note",
        action="create",
        ip=get_client_ip(request) if 'request' in locals() else "unknown"
    )
    
    session_num = repo.get_latest_session_num(campaign_id) + 1

    # Add the note to the session log
    repo.add_session_note(campaign_id, session_num, note.prompt, note.response)

    # Background task: process continuity (entity extraction, summary, facts)
    orchestrator = LLMOrchestrator(repo)
    continuity_keeper = ContinuityKeeper(repo, orchestrator)
    async def _safe_process():
        try:
            await continuity_keeper.process_session(campaign_id, session_num, note.prompt + "\n" + note.response)
        except Exception as e:
            logger.warning(f"Continuity processing failed: {e}")
    background_tasks.add_task(_safe_process)

    # Return updated state
    state = repo.get_campaign_state(campaign_id)
    return CampaignStateResponse(**state)


@router.post("/reset", response_model=CampaignStateResponse)
async def reset_campaign(
    campaign_id: int = 1,
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
    # Re-create default campaign
    repo.get_or_create_campaign(campaign_id)
    state = repo.get_campaign_state(campaign_id)
    return CampaignStateResponse(**state)


# ──────────────────────────────────────────────────────────────
# Session Summarization — Campaign Journal
# ──────────────────────────────────────────────────────────────

@router.post("/summarize-session", response_model=SummarizeSessionResponse)
async def summarize_session(request: SummarizeSessionRequest) -> SummarizeSessionResponse:
    """Turn raw session events into an atmospheric journal entry."""
    clean = [e.strip() for e in request.events if e and e.strip()]
    if not clean:
        raise HTTPException(status_code=400, detail="No events to summarize")
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    agent = ContinuityAgent(llm)
    try:
        journal = await agent.summarize_session(clean, request.campaign_name)
    finally:
        await llm.close()
    return SummarizeSessionResponse(summary=journal.summary, event_count=journal.event_count)


# ──────────────────────────────────────────────────────────────
# Export/Import — Campaign Backup & Restore
# ──────────────────────────────────────────────────────────────

@router.get("/export", response_model=CampaignExport, tags=["campaign", "export"])
async def export_campaign(
    campaign_id: int = 1,
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
    
    # Gather all campaign data
    campaign = repo.get_or_create_campaign(campaign_id)
    party = repo.get_party(campaign_id)
    npcs = repo.get_npcs(campaign_id)
    locations = repo.get_locations(campaign_id)
    
    # Get items, quests, sessions, party_members, notes, decisions
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
        exported_at=datetime.utcnow().isoformat(),
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
    campaign_id: int = 1,
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
                conn.execute("UPDATE campaigns SET name=?, edition=? WHERE id=?", 
                           (import_data.campaign.get("name"), import_data.campaign.get("edition"), campaign_id))
    
    if import_data.party:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM party_members WHERE campaign_id = ?", (campaign_id,))
        for member in import_data.party:
            repo.upsert_party_member(campaign_id=campaign_id, **member)
    
    if import_data.npcs:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM npcs WHERE campaign_id = ?", (campaign_id,))
        for npc in import_data.npcs:
            repo.upsert_npc(campaign_id=campaign_id, **npc)
    
    if import_data.locations:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM locations WHERE campaign_id = ?", (campaign_id,))
        for loc in import_data.locations:
            repo.upsert_location(campaign_id=campaign_id, **loc)
    
    if import_data.items:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM items WHERE campaign_id = ?", (campaign_id,))
        for item in import_data.items:
            repo.upsert_item(campaign_id=campaign_id, **item)
    
    if import_data.quests:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM quests WHERE campaign_id = ?", (campaign_id,))
        for quest in import_data.quests:
            repo.upsert_quest(campaign_id=campaign_id, **quest)
    
    if import_data.party_members:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM party_members WHERE campaign_id = ?", (campaign_id,))
        for member in import_data.party_members:
            repo.upsert_party_member(campaign_id=campaign_id, **member)

    if import_data.sessions:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM sessions WHERE campaign_id = ?", (campaign_id,))
        for session in import_data.sessions:
            raw_facts = session.get("facts", session.get("facts_json", []))
            if isinstance(raw_facts, str):
                try:
                    raw_facts = json.loads(raw_facts)
                except ValueError:
                    raw_facts = []
            repo.save_session(
                campaign_id=campaign_id,
                session_num=int(session.get("session_num", 1)),
                summary=session.get("summary", ""),
                facts=raw_facts if isinstance(raw_facts, list) else [],
                raw_log=session.get("raw_log", ""),
            )

    if import_data.notes:
        if import_data.replace_existing:
            with repo._conn() as conn:
                conn.execute("DELETE FROM session_notes WHERE campaign_id = ?", (campaign_id,))
        for note in import_data.notes:
            with repo._conn() as conn:
                conn.execute(
                    "INSERT INTO session_notes (campaign_id, session_num, note_type, content) VALUES (?, ?, ?, ?)",
                    (
                        campaign_id,
                        int(note.get("session_num", 1)),
                        note.get("note_type", "gm"),
                        note.get("content", ""),
                    ),
                )

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
    campaign_id: int = 1,
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
    
    # Get full export
    export = await export_campaign(campaign_id, repo, user, request)
    
    from fastapi.responses import Response
    import json
    
    filename = f"pathfinder_campaign_{campaign_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    return Response(
        content=json.dumps(export.model_dump(), indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ──────────────────────────────────────────────────────────────
# NPC Management (for Spoke Character sync)
# ──────────────────────────────────────────────────────────────

class NPCRequest(BaseModel):
    name: str
    alias: str | None = None
    role: str = "unknown"
    level: int | None = None
    ancestry: str | None = None
    class_: str | None = Field(None, alias="class")
    disposition: str = "unknown"
    notes: str | None = None


@router.get("/npcs")
async def list_npcs(
    campaign_id: int = 1,
    repo: CampaignRepository = Depends(get_repo),
) -> list[dict]:
    npcs = repo.get_npcs(campaign_id)
    return [dict(npc.__dict__) for npc in npcs]


@router.post("/npcs")
async def create_npc(
    npc: NPCRequest,
    campaign_id: int = 1,
    repo: CampaignRepository = Depends(get_repo),
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


# ──────────────────────────────────────────────────────────────
# Party / Characters
# ──────────────────────────────────────────────────────────────

class PartyMemberRequest(BaseModel):
    name: str
    player_name: str | None = None
    class_: str | None = Field(None, alias="class")
    level: int = 1
    ancestry: str | None = None
    background: str | None = None
    stats: dict | None = None


@router.get("/party")
async def list_party(
    campaign_id: int = 1,
    repo: CampaignRepository = Depends(get_repo),
) -> list[dict]:
    return repo.get_party(campaign_id)


@router.post("/party")
async def add_party_member(
    member: PartyMemberRequest,
    campaign_id: int = 1,
    repo: CampaignRepository = Depends(get_repo),
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