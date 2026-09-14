# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Continuity Keeper Agent — Phase 3: Campaign Persistence & Long-term Memory

Extracts entities from session logs, writes to SQLite, generates summaries.
Runs after each /campaign/note to maintain continuity across sessions.

Tool interface (for GM Storyteller):
- process_session(campaign_id, session_num, session_log) -> SessionSummary
- get_campaign_context(campaign_id) -> {summary, entities, facts}
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.db.repository import CampaignRepository
from app.llm.orchestrator import LLMOrchestrator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.llm.orchestrator import LLMOrchestrator

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Continuity Keeper
# ──────────────────────────────────────────────────────────────

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
        await self.repo.save_session(
            campaign_id=campaign_id,
            session_num=session_num,
            summary=summary,
            facts=facts,
            raw_log=session_log,
        )

        return SessionSummary(summary=summary, facts=facts, entities=entities)

    async def _extract_entities(self, log: str) -> ExtractedEntities:
        prompt = f"{ENTITY_EXTRACTION_SYSTEM}\n\nLog:\n{log}\n\nReturn ONLY valid JSON."
        response = await self.llm.generate(prompt, system="")
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Entity extraction returned non-JSON; returning empty entities")
            return ExtractedEntities()

        return ExtractedEntities(
            npcs=[ExtractedEntity(type="npc", **e) for e in data.get("npcs", [])],
            locations=[ExtractedEntity(type="location", **e) for e in data.get("locations", [])],
            items=[ExtractedEntity(type="item", **e) for e in data.get("items", [])],
            quests=[ExtractedEntity(type="quest", **e) for e in data.get("quests", [])],
            decisions=[ExtractedEntity(type="decision", **e) for e in data.get("decisions", [])],
        )

    async def _upsert_entities(
        self,
        campaign_id: int,
        session_num: int,
        entities: ExtractedEntities,
    ) -> None:
        for npc in entities.npcs:
            await self.repo.upsert_npc(
                campaign_id=campaign_id,
                name=npc.name,
                alias=npc.attributes.get("alias"),
                role=npc.attributes.get("role", "unknown"),
                level=npc.attributes.get("level"),
                ancestry=npc.attributes.get("ancestry"),
                class_=npc.attributes.get("class"),
                disposition=npc.attributes.get("disposition", "unknown"),
                notes=npc.attributes.get("notes"),
                session_num=session_num,
            )

        for loc in entities.locations:
            await self.repo.upsert_location(
                campaign_id=campaign_id,
                name=loc.name,
                type_=loc.attributes.get("type", "other"),
                parent_name=loc.attributes.get("parent"),
                description=loc.attributes.get("description"),
                session_num=session_num,
            )

        for item in entities.items:
            await self.repo.upsert_item(
                campaign_id=campaign_id,
                name=item.name,
                type_=item.attributes.get("type", "other"),
                level=item.attributes.get("level"),
                traits=item.attributes.get("traits", []),
                holder_name=item.attributes.get("holder"),
                location_name=item.attributes.get("location"),
                notes=item.attributes.get("notes"),
                session_num=session_num,
            )

        for quest in entities.quests:
            await self.repo.upsert_quest(
                campaign_id=campaign_id,
                name=quest.name,
                status=quest.attributes.get("status", "active"),
                giver_name=quest.attributes.get("giver"),
                description=quest.attributes.get("description"),
                objectives=quest.attributes.get("objectives", []),
                rewards=quest.attributes.get("rewards", []),
                session_num=session_num,
            )

        for decision in entities.decisions:
            await self.repo.add_decision(
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
        response = await self.llm.generate(prompt, system="")
        try:
            fact_data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Fact extraction returned non-JSON; returning empty facts")
            return []
        return [Fact(**f) for f in fact_data]

    def get_campaign_context(self, campaign_id: int) -> dict[str, Any]:
        """Build context for next session: recent summary + relevant entities."""
        session = self.repo.get_latest_session(campaign_id)
        if not session:
            return {"summary": "", "entities": {}, "facts": []}

        entities = {
            "npcs": self.repo.get_npcs(campaign_id),
            "locations": self.repo.get_locations(campaign_id),
            "quests": self.repo.get_active_quests(campaign_id),
        }
        return {
            "summary": session.summary,
            "entities": entities,
            "facts": session.facts,
        }