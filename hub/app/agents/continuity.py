# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Continuity Keeper Agent â€” Phase 3: Campaign Persistence & Long-term Memory

Extracts entities from session logs, writes to SQLite, generates summaries.
Runs after each /campaign/note to maintain continuity across sessions.

Tool interface (for GM Storyteller):
- process_session(campaign_id, session_num, session_log) -> SessionSummary
- get_campaign_context(campaign_id) -> {summary, entities, facts}
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.llm.orchestrator import LLMOrchestrator

if TYPE_CHECKING:
    from app.llm.orchestrator import LLMOrchestrator

logger = logging.getLogger(__name__)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Data Classes
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class ExtractedEntity:
    """A single entity extracted from session text."""
    type: str  # npc | location | item | quest | decision
    name: str
    attributes: dict = field(default_factory=dict)
    confidence: float = 1.0
    source_text: str = ""


@dataclass
class ExtractedEntities:
    """All entities extracted from a session."""
    npcs: list[ExtractedEntity] = field(default_factory=list)
    locations: list[ExtractedEntity] = field(default_factory=list)
    items: list[ExtractedEntity] = field(default_factory=list)
    quests: list[ExtractedEntity] = field(default_factory=list)
    decisions: list[ExtractedEntity] = field(default_factory=list)

    def all_names(self) -> list[str]:
        names = []
        for entities in [self.npcs, self.locations, self.items, self.quests, self.decisions]:
            names.extend([e.name for e in entities])
        return names


@dataclass
class Fact:
    """A discrete fact for session continuity."""
    fact: str
    category: str  # npc | location | item | quest | decision | mechanic
    confidence: float


@dataclass
class SessionSummary:
    """Complete session processing output."""
    summary: str
    facts: list[Fact]
    entities: ExtractedEntities


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Prompts
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

ENTITY_EXTRACTION_SYSTEM = """You are the Continuity Keeper for a Pathfinder campaign.
Extract ALL entities from the session log. Return ONLY valid JSON.

Entity types and required fields:
- npc: name, alias?, role (ally/enemy/neutral/unknown), level?, ancestry?, class?, disposition?, notes?
- location: name, type (settlement/dungeon/wilderness/planar/other), parent?, description?
- item: name, type (weapon/armor/consumable/magic/artifact/currency/other), level?, traits?, holder?, location?, notes?
- quest: name, status (active/completed/failed/on_hold), giver?, description?, objectives?, rewards?
- decision: decision, context?, consequences?, made_by?

Return format:
{
  "npcs": [...],
  "locations": [...],
  "items": [...],
  "quests": [...],
  "decisions": [...]
}

Be thorough. Include minor NPCs, mentioned locations, loot gained/lost, quest updates, and player choices."""


SUMMARY_SYSTEM = """You are the Continuity Keeper for a Pathfinder campaign.
Write a 500-word narrative summary of this session.
Focus on: key events, NPC interactions, combat highlights, decisions made, cliffhangers.
Mention entities by name. Style: GM session recap, evocative but concise.
Return ONLY the summary text, no JSON."""


FACT_EXTRACTION_SYSTEM = """You are the Continuity Keeper for a Pathfinder campaign.
Extract 10-20 key facts from this session as a JSON array.
Each fact: {"fact": "string", "category": "npc|location|item|quest|decision|mechanic", "confidence": 0.0-1.0}
Only include facts useful for future continuity.
Return ONLY the JSON array."""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Continuity Keeper
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def repair_json_text(text: str) -> str:
    """Best-effort salvage of JSON out of small-model output.

    qwen2.5:3b routinely wraps JSON in prose, emits ```json fences, leaks a
    <think> block, and leaves trailing commas. json.loads() rejects all of those,
    and the caller used to fall back to *no entities at all* rather than
    recovering the payload.
    """
    if not text:
        return ""
    out = text.strip()

    # Drop a reasoning block if the model leaked one.
    if "<think>" in out and "</think>" in out:
        out = out.split("</think>", 1)[1].strip()

    # Strip Markdown fences, keeping the fenced body.
    if out.startswith("```"):
        out = re.sub(r"^```[a-zA-Z]*\s*", "", out)
        out = re.sub(r"\s*```$", "", out).strip()

    # Pull the outermost {...} or [...] out of surrounding prose. Try the
    # opener that appears FIRST in the text, so a bare array keeps its brackets
    # instead of being collapsed into the object nested inside it.
    candidates: list[str] = []
    obj_start, obj_end = out.find("{"), out.rfind("}")
    arr_start, arr_end = out.find("["), out.rfind("]")
    if obj_start != -1 and obj_end > obj_start:
        candidates.append((obj_start, "{", "}", out[obj_start : obj_end + 1]))
    if arr_start != -1 and arr_end > arr_start:
        candidates.append((arr_start, "[", "]", out[arr_start : arr_end + 1]))
    candidates.sort(key=lambda c: c[0])

    for _, _, _, candidate in candidates:
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                json.loads(repaired)
                return repaired
            except json.JSONDecodeError:
                continue

    # Nothing parsed; return the trailing-comma-repaired original for logging.
    return re.sub(r",\s*([}\]])", r"\1", out)


def parse_json_loose(text: str) -> object | None:
    """json.loads with repair. Returns None when nothing salvageable is found."""
    candidate = repair_json_text(text)
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        logger.debug("Loose JSON parse failed after repair")
        return None


# Top-level key aliases the 3B model reaches for instead of the contract names.
_KEY_ALIASES = {
    "npcs": ("npcs", "npc", "characters", "people", "persons", "actors", "creatures"),
    "locations": ("locations", "location", "places", "rooms", "areas", "sites"),
    "items": ("items", "item", "loot", "objects", "treasures", "equipment"),
    "quests": ("quests", "quest", "tasks", "hooks", "objectives"),
    "decisions": ("decisions", "decision", "choices", "actions"),
}


def _coerce_entries(raw: object) -> list[dict]:
    """Normalise a model's entity list into dicts.

    A bare-string list ("npcs": ["Garrick"]) is the common 3B failure: the old
    `[e for e in raw if isinstance(e, dict)]` silently DROPPED every one of them,
    so a perfectly good extraction produced no NPCs at all.
    """
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for entry in raw:
        if isinstance(entry, dict):
            out.append(entry)
        elif isinstance(entry, str) and entry.strip():
            out.append({"name": entry.strip()})
    return out


def normalize_entity_payload(data: object) -> dict[str, list[dict]]:
    """Map aliased top-level keys onto the contract and coerce entries."""
    if not isinstance(data, dict):
        return {}
    normalized: dict[str, list[dict]] = {}
    lower_map = {str(k).lower(): k for k in data}
    for canonical, aliases in _KEY_ALIASES.items():
        # Accumulate across EVERY alias rather than stopping at the first: a
        # model that emits both "characters" and "people" means both.
        collected: list[dict] = []
        seen_names: set[str] = set()
        for alias in aliases:
            actual = lower_map.get(alias)
            if actual is None:
                continue
            for entry in _coerce_entries(data.get(actual)):
                key = str(entry.get("name", "")).strip().lower()
                if key and key in seen_names:
                    continue
                if key:
                    seen_names.add(key)
                collected.append(entry)
        if collected:
            normalized[canonical] = collected
    return normalized


class ContinuityKeeper:
    def __init__(self, repo: CampaignRepository, orchestrator: "LLMOrchestrator"):
        self.repo = repo
        self.orchestrator = orchestrator
        self.llm = orchestrator.ollama

    async def process_session(
        self,
        campaign_id: int,
        session_num: int,
        session_log: str,
    ) -> SessionSummary:
        """Run after each session ends. Extract, persist, summarize."""
        logger.info(f"Processing continuity for campaign {campaign_id}, session {session_num}")

        # 1. Extract entities
        entities = await self._extract_entities(session_log)

        # 2. Upsert to DB
        await self._upsert_entities(campaign_id, session_num, entities)

        # 3. Generate narrative summary
        summary = await self._generate_summary(session_log, entities)

        # 4. Extract key facts
        facts = await self._extract_facts(session_log, entities)

        # 5. Persist session record
        self.repo.save_session(
            campaign_id=campaign_id,
            session_num=session_num,
            summary=summary,
            facts=[asdict(f) for f in facts],
            raw_log=session_log,
        )

        # 6. Fold this session into the campaign's evergreen chronicle so the
        # GM can carry continuity forward without stuffing every log into the
        # prompt. FTS5 sessions_fts is already kept in sync by a trigger.
        await self._refresh_chronicle(campaign_id, summary)

        return SessionSummary(summary=summary, facts=facts, entities=entities)

    async def _refresh_chronicle(self, campaign_id: int, new_summary: str) -> None:
        """Merge the fresh session summary into one rolling campaign summary."""
        prev = self.repo.get_campaign_summary(campaign_id) or ""
        prompt = (
            CHRONICLER_SYSTEM
            + "\n\nPrevious campaign chronicle:\n"
            + (prev if prev else "(none yet)")
            + "\n\nNew session summary:\n"
            + new_summary
            + "\n\nRewrite as one concise, current campaign chronicle. Carry forward unresolved threads."
        )
        try:
            merged = (await self.llm.generate(prompt, system="")) or ""
            merged = merged.strip()
            if merged:
                self.repo.update_campaign_summary(campaign_id, merged)
        except Exception:
            logger.warning("chronicle refresh failed", exc_info=True)

    def search_sessions(
        self,
        query: str,
        campaign_id: int = 1,
        limit: int = 5,
        embedder: object | None = None,
    ) -> list[dict]:
        """Recall past sessions (hybrid semantic + lexical memory)."""
        return self.repo.search_sessions(query=query, campaign_id=campaign_id, limit=limit, embedder=embedder)

    async def _extract_entities(self, log: str) -> ExtractedEntities:
        prompt = f"{ENTITY_EXTRACTION_SYSTEM}\n\nLog:\n{log}\n\nReturn ONLY valid JSON."
        # format="json" + temperature 0 makes Ollama grammar-constrain the
        # reply, which is the only reliable way to get parseable JSON out of
        # qwen2.5:3b. repair below still runs, because grammar mode is not
        # guaranteed and the model can still emit prose around it.
        response = await self.llm.generate(
            prompt, system="", temperature=0.0, format="json"
        )
        data = parse_json_loose(response)

        if data is None:
            logger.warning("Entity extraction returned unparseable JSON; returning empty entities")
            return ExtractedEntities()

        if isinstance(data, list):
            # A bare top-level array: treat it as a list of entities.
            data = {"npcs": data}

        if not isinstance(data, dict):
            # phi4-mini sometimes returns an object-shaped array. data.get()
            # then raised AttributeError, and because the caller swallows
            # exceptions into a warning, /campaign/note returned 200 having
            # written no entities, no summary and no session row.
            logger.warning(
                "Entity extraction returned %s, not an object; returning empty entities",
                type(data).__name__,
            )
            return ExtractedEntities()

        payload = normalize_entity_payload(data)
        if not payload:
            logger.warning("Entity extraction produced no recognised entity keys")
            return ExtractedEntities()

        return ExtractedEntities(
            npcs=[self._entity("npc", e) for e in payload.get("npcs", [])],
            locations=[self._entity("location", e) for e in payload.get("locations", [])],
            items=[self._entity("item", e) for e in payload.get("items", [])],
            quests=[self._entity("quest", e) for e in payload.get("quests", [])],
            decisions=[self._entity("decision", e) for e in payload.get("decisions", [])],
        )

    @staticmethod
    def _entity(entry_type: str, entry: dict) -> ExtractedEntity:
        fields = dict(entry)
        name = fields.pop("name", "Unknown")
        confidence = fields.pop("confidence", 1.0)
        source_text = fields.pop("source_text", "")
        attributes = fields.pop("attributes", None) or {}
        attributes.update(fields)
        return ExtractedEntity(
            type=entry_type,
            name=name,
            attributes=attributes,
            confidence=confidence,
            source_text=source_text,
        )

    async def _upsert_entities(
        self,
        campaign_id: int,
        session_num: int,
        entities: ExtractedEntities,
    ) -> None:
        """Persist an extracted entity set over a single DB connection (O2).

        This used to call upsert_npc/location/item/quest per entity, and each
        of those opened its own sqlite connection and ran its own
        _ensure_campaign INSERT. A typical extraction produced ~50 connections
        for what is logically one transaction. upsert_entities_batch keeps the
        same per-row SQL (FK resolution still reads rows written earlier in the
        batch) but shares one connection and one commit.
        """
        self.repo.upsert_entities_batch(
            campaign_id,
            npcs=[
                {
                    "name": npc.name,
                    "alias": npc.attributes.get("alias"),
                    "role": npc.attributes.get("role", "unknown"),
                    "level": npc.attributes.get("level"),
                    "ancestry": npc.attributes.get("ancestry"),
                    "class_": npc.attributes.get("class"),
                    "disposition": npc.attributes.get("disposition", "unknown"),
                    "notes": npc.attributes.get("notes"),
                    "session_num": session_num,
                }
                for npc in entities.npcs
            ],
            locations=[
                {
                    "name": loc.name,
                    "type": loc.attributes.get("type", "other"),
                    "parent_name": loc.attributes.get("parent"),
                    "description": loc.attributes.get("description"),
                    "session_num": session_num,
                }
                for loc in entities.locations
            ],
            items=[
                {
                    "name": item.name,
                    "type": item.attributes.get("type", "other"),
                    "level": item.attributes.get("level"),
                    "traits": item.attributes.get("traits", []),
                    "holder_name": item.attributes.get("holder"),
                    "location_name": item.attributes.get("location"),
                    "notes": item.attributes.get("notes"),
                    "session_num": session_num,
                }
                for item in entities.items
            ],
            quests=[
                {
                    "name": quest.name,
                    "status": quest.attributes.get("status", "active"),
                    "giver_name": quest.attributes.get("giver"),
                    "description": quest.attributes.get("description"),
                    "objectives": quest.attributes.get("objectives", []),
                    "rewards": quest.attributes.get("rewards", []),
                    "session_num": session_num,
                }
                for quest in entities.quests
            ],
        )

        # Decisions have no upsert/uniqueness semantics (they are an append-only
        # log), so they keep their own writer.
        for decision in entities.decisions:
            self.repo.add_decision(
                campaign_id=campaign_id,
                session_num=session_num,
                decision=decision.attributes.get("decision", decision.name),
                context=decision.attributes.get("context"),
                consequences=decision.attributes.get("consequences"),
                made_by=decision.attributes.get("made_by", "party"),
            )

    async def _generate_summary(self, log: str, entities: ExtractedEntities) -> str:
        entity_names = ", ".join(entities.all_names())
        prompt = f"{SUMMARY_SYSTEM}\n\nEntities to mention: {entity_names}\n\nLog:\n{log}"
        return await self.llm.generate(prompt, system="")

    async def _extract_facts(self, log: str, entities: ExtractedEntities) -> list[Fact]:
        prompt = f"{FACT_EXTRACTION_SYSTEM}\n\nLog:\n{log}\n\nReturn ONLY valid JSON."
        response = await self.llm.generate(
            prompt, system="", temperature=0.0, format="json"
        )
        fact_data = parse_json_loose(response)
        if fact_data is None:
            logger.warning("Fact extraction returned unparseable JSON; returning empty facts")
            return []
        if isinstance(fact_data, dict):
            # Some models wrap the array in {"facts": [...]}.
            for key in ("facts", "results", "items"):
                if isinstance(fact_data.get(key), list):
                    fact_data = fact_data[key]
                    break
        if not isinstance(fact_data, list):
            logger.warning(
                "Fact extraction returned %s, not an array; returning empty facts",
                type(fact_data).__name__,
            )
            return []
        # A single malformed entry used to raise TypeError/ValueError out of
        # Fact(**f), which the caller swallowed - so one bad object from the
        # model discarded every other fact in the response.
        out: list[Fact] = []
        for f in fact_data:
            if not isinstance(f, dict):
                continue
            try:
                out.append(
                    Fact(
                        fact=str(f.get("fact", "")),
                        category=str(f.get("category") or "mechanic"),
                        confidence=float(f.get("confidence", 1.0)),
                    )
                )
            except (TypeError, ValueError) as exc:
                logger.warning(f"skipping malformed fact {f!r}: {exc}")
        return out

    def get_campaign_context(self, campaign_id: int) -> dict[str, Any]:
        """Build context for next session WITHOUT leaking the whole database.

        The crisp campaign chronicle (re-rendered after each session) plus the
        latest session's summary/facts seed every turn. Entities are bounded to
        the most recent handful rather than the full table, so a long campaign
        does not consume the context window. Full history is recallable via
        search_sessions(), not stuffed into the prompt.
        """
        chronicle = self.repo.get_campaign_summary(campaign_id) or ""
        session = self.repo.get_latest_session(campaign_id)

        # Bound entity dumps; full table retrieval for a specific entity goes
        # through the recall tool / search_sessions, not this context block.
        npcs = self.repo.get_npcs(campaign_id) or []
        locations = self.repo.get_locations(campaign_id) or []
        quests = self.repo.get_active_quests(campaign_id) or []
        entities = {
            "npcs": npcs[:8],
            "locations": locations[:8],
            "quests": quests[:5],
        }

        if not session and not chronicle:
            return {"chronicle": "", "summary": "", "entities": entities, "facts": []}

        return {
            "chronicle": chronicle,
            "summary": chronicle or (session.summary if session else ""),
            "entities": entities,
            "facts": session.facts if session else [],
        }


CHRONICLER_SYSTEM = "You are a chronicler recording a Pathfinder campaign journal. Write a concise, atmospheric 2-paragraph summary of these events."


@dataclass
class SessionJournal:
    campaign_name: str
    summary: str
    event_count: int


class ContinuityAgent:
    def __init__(self, llm: OllamaClient):
        self._llm = llm
        self._settings = get_settings()

    async def summarize_session(
        self, events: list[str], campaign_name: str
    ) -> SessionJournal:
        clean = [e.strip() for e in events if e and e.strip()]
        if not clean:
            return SessionJournal(campaign_name=campaign_name, summary="", event_count=0)
        log = "\n".join(f"- {e}" for e in clean)
        try:
            summary = await self._llm.generate(
                prompt=f"{CHRONICLER_SYSTEM}\n\nCampaign: {campaign_name}\n\nEvents:\n{log}",
                model=self._settings.model_for("continuity"),
                temperature=0.4,
                num_predict=400,
            )
        except Exception as e:
            # Returning an empty SessionJournal here reported success: the
            # endpoint answered 200 with summary="" and the Spoke wrote an
            # empty chronicle entry as though the session had been summarised.
            # Propagate so the caller can answer 503.
            logger.warning(f"ContinuityAgent summarization failed: {e}")
            raise RuntimeError(f"local LLM unavailable: {e}") from e
        return SessionJournal(
            campaign_name=campaign_name,
            summary=summary.strip(),
            event_count=len(clean),
        )

