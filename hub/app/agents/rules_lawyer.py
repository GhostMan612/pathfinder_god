# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Rules Lawyer Agent — Phase 5: Fact-checker with Ollama function calling.

Tools (exact schemas from design chat):
- lookup_rule(query) -> searches vector DB of Archives of Nethys / SRD
- calculate_dc(level, rarity, proficiency) -> does the math
- validate_action(action, character_sheet) -> "Can a level 3 Fighter Trip an Ogre?"
"""

import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.rag.retriever import Retriever
from app.telemetry import log_miss

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# Deterministic PF2e Remaster tables (Gemini §15.4 — never LLM)
# ══════════════════════════════════════════════════════════════

# Table 10-5: Level-Based DCs (CRB Remaster). -1/0 for negative levels.
LEVEL_DC: dict[int, int] = {
    -1: 13, 0: 14, 1: 15, 2: 16, 3: 18, 4: 19, 5: 20,
    6: 22, 7: 23, 8: 24, 9: 26, 10: 27, 11: 28, 12: 30,
    13: 31, 14: 32, 15: 34, 16: 35, 17: 36, 18: 38,
    19: 39, 20: 40, 21: 42, 22: 44, 23: 46, 24: 48, 25: 50,
}

# Simple DCs by proficiency rank (no level). Used for Recall Knowledge etc.
SIMPLE_DC: dict[str, int] = {
    "untrained": 10, "trained": 15, "expert": 20, "master": 30, "legendary": 40,
}

RARITY_ADJ: dict[str, int] = {"common": 0, "uncommon": 2, "rare": 5, "unique": 10}

# Action → required skill (deterministic validate_action). Keys lowercased.
ACTION_SKILL: dict[str, str] = {
    "trip": "athletics", "grapple": "athletics", "shove": "athletics",
    "disarm": "athletics", "reposition": "athletics",
    "demoralize": "intimidation", "feint": "deception", "create a diversion": "deception",
    "hide": "stealth", "sneak": "stealth", "avoid notice": "stealth",
    "pick a lock": "thievery", "disable a device": "thievery", "palm an object": "thievery",
    "recall knowledge": "arcana",  # fallback; actual check uses specific lore
    "arcana": "arcana", "nature": "nature", "religion": "religion",
    "occultism": "occultism", "society": "society", "crafting": "crafting",
    "medicine": "medicine", "survival": "survival", "diplomacy": "diplomacy",
    "deception": "deception", "intimidation": "intimidation",
}

# ══ Strict Pydantic mirror of spoke/lib/models/character.dart ══

class AbilityScoresModel(BaseModel):
    str: int = 10
    dex: int = 10
    con: int = 10
    int_: int = Field(default=10, alias="int")
    wis: int = 10
    cha: int = 10
    model_config = {"populate_by_name": True}

class SkillProficienciesModel(BaseModel):
    acrobatics: int = 0; arcana: int = 0; athletics: int = 0; crafting: int = 0
    deception: int = 0; diplomacy: int = 0; intimidation: int = 0; lore: int = 0
    medicine: int = 0; nature: int = 0; occultism: int = 0; performance: int = 0
    religion: int = 0; society: int = 0; stealth: int = 0; survival: int = 0
    thievery: int = 0

class DefenseProficienciesModel(BaseModel):
    fortitude: int = 0; reflex: int = 0; will: int = 0; perception: int = 0
    unarmored: int = 0; lightArmor: int = 0; mediumArmor: int = 0; heavyArmor: int = 0
    simpleWeapons: int = 0; martialWeapons: int = 0; advancedWeapons: int = 0; unarmed: int = 0

class ClassProficienciesModel(BaseModel):
    classDC: int = 0; spellDC: int = 0; spellAttack: int = 0

class ProficienciesModel(BaseModel):
    skills: SkillProficienciesModel = Field(default_factory=SkillProficienciesModel)
    defenses: DefenseProficienciesModel = Field(default_factory=DefenseProficienciesModel)
    classProfs: ClassProficienciesModel = Field(default_factory=ClassProficienciesModel)

class CharacterSheetModel(BaseModel):
    """Strict Pydantic mirror of Character.toMap(). Accepts JSON strings or dicts."""
    name: str = ""
    ancestry: str = "Human"
    heritage: str = ""
    background: str = ""
    character_class: str = Field(default="Fighter", alias="character_class")
    level: int = 1
    abilities: AbilityScoresModel = Field(default_factory=AbilityScoresModel)
    proficiencies: ProficienciesModel = Field(default_factory=ProficienciesModel)

    model_config = {"populate_by_name": True, "extra": "allow"}

    @classmethod
    def from_any(cls, data: Any) -> "CharacterSheetModel":
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                return cls()
        if not isinstance(data, dict):
            return cls()
        # Flutter stores abilities/proficiencies as JSON strings inside toMap()
        for k in ("abilities", "proficiencies"):
            if isinstance(data.get(k), str):
                try:
                    data[k] = json.loads(data[k])
                except Exception:
                    data[k] = {}
        # alias int -> int_
        if "abilities" in data and isinstance(data["abilities"], dict) and "int" in data["abilities"]:
            data["abilities"]["int"] = data["abilities"].pop("int")
        return cls.model_validate(data)

# ══════════════════════════════════════════════════════════════
# Tool Definitions (exact from design chat)
# ══════════════════════════════════════════════════════════════

RULES_LAWYER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_rule",
            "description": "Search Pathfinder 2e rules, feats, conditions, traits",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_dc",
            "description": "Calculate DC by level, rarity, proficiency",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer"},
                    "rarity": {"type": "string", "enum": ["common", "uncommon", "rare", "unique"]},
                    "proficiency": {"type": "string", "enum": ["untrained", "trained", "expert", "master", "legendary"]}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_action",
            "description": "Check if action is legal for character",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "character_sheet": {"type": "object"},
                    "target": {"type": "object"}
                },
                "required": ["action", "character_sheet"]
            }
        }
    }
]

RULES_LAWYER_SYSTEM = """You are a Pathfinder 2e Rules Lawyer. NEVER answer from memory.
ALWAYS call lookup_rule first. Cite the source trait and page.
For math (DC, bonuses), call calculate_dc or compute from character sheet.
If asked "Can X do Y?", call validate_action.
Be concise. No flavor text."""


@dataclass
class RuleLookupResult:
    name: str
    content: str
    source_book: str
    page: str | None = None


@dataclass
class DCResult:
    dc: int
    breakdown: str


@dataclass
class ValidationResult:
    legal: bool
    reason: str
    rule_citation: str


ABSTENTION_TEXT = "I don't have that rule in my books."

_ABSTENTION_INSTRUCTION = (
    "\n\nCRITICAL - NO RULE FOUND FOR THIS. Your excerpts do not contain "
    "the rule being asked about. Do NOT invent a number, DC, bonus, or "
    "rule name, and do NOT guess from general knowledge. Say plainly: "
    "\"I don't have that rule in my books.\" Then offer to adjudicate it "
    "as a house rule and state that it is your ruling, not a citation."
)

@dataclass
class Citation:
    """One deterministic source tag for an adjudication.

    Built from the retriever rows, never from the model's prose, so a citation
    cannot drift into naming a rule the model never actually saw.
    """

    source_book: str
    name: str
    category: str = ""

    def tag(self) -> str:
        return f"[{self.source_book} - {self.name}]"


# A bracketed "[Book - Rule]" tag in model prose. Deliberately conservative:
# it requires the book-name dash-name shape so ordinary square brackets in
# prose (dice notation, flow tables, "[sic]") are left alone.
_INLINE_TAG_RE = re.compile(r"\[([^\[\]\n]{1,80}?)\s+-\s+([^\[\]\n]{1,80}?)\]")


def sanitize_inline_citations(
    text: str, valid_tags: set[str]
) -> tuple[str, list[str]]:
    """Strip bracketed citation tags the model was never shown.

    Verbatim forwarding fixed re-narration dropping citations, and the
    deterministic Sources block is built from retrieval rows, so the *sources*
    are trustworthy. The prose is not: a 3B model will still sprinkle in
    plausible-looking ``[Core Rulebook - Grapple]`` tags for rules that were not
    in its context. Those are worse than no citation at all, because they read
    as verified.

    Returns ``(cleaned_text, stripped_tags)``. A tag matching one of
    ``valid_tags`` (case-insensitively, whitespace-normalised) is kept; anything
    else shaped like a citation is removed along with one preceding space, and
    reported so it can be logged as a retrieval defect.
    """
    if not text or "[" not in text:
        return text, []

    lookup = {re.sub(r"\s+", " ", t).strip().casefold() for t in valid_tags}
    stripped: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        whole = match.group(0)
        normalized = re.sub(r"\s+", " ", whole).strip().casefold()
        if normalized in lookup:
            return whole
        stripped.append(whole)
        return ""

    cleaned = _INLINE_TAG_RE.sub(_replace, text)
    if not stripped:
        return text, []
    # Removing a mid-sentence tag can leave a double space; tidy those without
    # touching intentional paragraph breaks.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.;:!?])", r"\1", cleaned)
    return cleaned, stripped


class InlineCitationScrubber:
    """Streaming-safe wrapper around :func:`sanitize_inline_citations`.

    A tag can straddle two model chunks, so scrubbing each chunk independently
    would miss ``"[Core Rulebook - Grap"`` + ``"ple]"``. This holds back any
    trailing text that could still grow into a bracket, and only emits the part
    that is provably safe.
    """

    def __init__(self, valid_tags: set[str]) -> None:
        self._valid = set(valid_tags)
        self._held = ""
        self.stripped: list[str] = []

    def feed(self, chunk: str) -> str:
        """Consume a chunk, returning the text that is safe to emit now."""
        if not chunk:
            return ""
        self._held += chunk
        # Everything up to the last unmatched '[' is safe: no later chunk can
        # change a bracket that is already closed.
        last_open = self._held.rfind("[")
        if last_open == -1 or "]" in self._held[last_open:]:
            safe, self._held = self._held, ""
        else:
            safe, self._held = self._held[:last_open], self._held[last_open:]
        cleaned, found = sanitize_inline_citations(safe, self._valid)
        self.stripped.extend(found)
        return cleaned

    def finish(self) -> str:
        """Flush the held-back tail at end of stream.

        A held-back tail can still be an *unterminated* citation - the stream
        ended mid-tag. Showing "[Core Rulebook - Grap" to the player is both
        ugly and misleading, so an unmatched opener and everything after it is
        dropped and recorded as a stripped hallucination.
        """
        tail, self._held = self._held, ""
        last_open = tail.rfind("[")
        if last_open != -1 and "]" not in tail[last_open:]:
            self.stripped.append(tail[last_open:].strip())
            tail = tail[:last_open]
        cleaned, found = sanitize_inline_citations(tail, self._valid)
        self.stripped.extend(found)
        return cleaned


class RulesLawyerAgent:
    def __init__(self, repo: CampaignRepository):
        self.repo = repo
        self.settings = get_settings()
        self.ollama = OllamaClient(self.settings.ollama_host)
        self.retriever = Retriever(repo)

    async def lookup_rule(self, query: str) -> RuleLookupResult:
        """Search rules via RAG retriever."""
        results = await self.retriever.search(query, edition="2e", limit=3)
        if not results:
            return RuleLookupResult(name="Not Found", content="No matching rule found", source_book="")
        r = results[0]
        return RuleLookupResult(
            name=r["name"],
            content=r["content"],
            source_book=r.get("source_book", "Core Rulebook"),
        )

    async def calculate_dc(self, level: int, rarity: str = "common", proficiency: str = "trained") -> DCResult:
        """Deterministic DC - never LLM (Gemini A15.4)."""
        rarity = (rarity or "common").strip().lower()
        proficiency = (proficiency or "trained").strip().lower()

        if rarity not in RARITY_ADJ:
            return DCResult(
                dc=0,
                breakdown=f"unknown rarity {rarity!r}; expected one of {sorted(RARITY_ADJ)}",
            )
        if proficiency not in SIMPLE_DC:
            return DCResult(
                dc=0,
                breakdown=(
                    f"unknown proficiency {proficiency!r}; "
                    f"expected one of {sorted(SIMPLE_DC)}"
                ),
            )

        # Simple (proficiency-only) DC, e.g. Recall Knowledge. This path was
        # unreachable: LEVEL_DC covers -1..25, so base is only None outside that
        # range, and the branch that held the SIMPLE_DC lookup could never run.
        # calculate_dc(level=0, proficiency="master") returned 14 where PF2e
        # requires DC 30.
        if level is None or proficiency != "trained":  # type: ignore[comparison-overlap]
            simple = SIMPLE_DC[proficiency]
            return DCResult(
                dc=simple,
                breakdown=f"Simple DC, {proficiency} = {simple} (no creature level)",
            )

        base = LEVEL_DC.get(level)
        if base is None:
            # Out of range: extrapolate 2 per level beyond 25, clamp below -1.
            if level > 25:
                base = 50 + (level - 25) * 2
            else:
                base = 13

        rarity_adj = RARITY_ADJ[rarity]
        dc = base + rarity_adj
        # Proficiency does NOT adjust level-based DC per Remaster; simple DC
        # already encodes it.
        return DCResult(dc=dc, breakdown=f"Level {level} base {base} + rarity {rarity} (+{rarity_adj}) = {dc} [{rarity}/{proficiency}]")

    async def validate_action(
        self,
        action: str,
        character_sheet: dict,
        target: dict | None = None
    ) -> ValidationResult:
        """Deterministic validation: check proficiency rank for action's required skill.

        Never guesses — looks up ACTION_SKILL then checks CharacterSheetModel.
        Mirrors spoke/lib/models/character.dart SkillProficiencies index: 0=untrained.
        """
        key = (action or "").strip().lower()
        # Normalize "Trip the ogre" -> "trip"
        first = key.split()[0] if key else ""
        skill = ACTION_SKILL.get(key) or ACTION_SKILL.get(first) or None

        sheet = CharacterSheetModel.from_any(character_sheet)

        if skill is None:
            # Unknown action — fallback to rule lookup for citation, assume legal but flag
            rule_result = await self.lookup_rule(f"{action} action traits")
            return ValidationResult(
                legal=True,
                reason=f"Unknown action '{action}' not in deterministic table; per {rule_result.name}: {rule_result.content[:160]} — assuming legal, narrate with caution.",
                rule_citation=f"{rule_result.source_book} - {rule_result.name}",
            )

        # Deterministic proficiency check
        rank: int = getattr(sheet.proficiencies.skills, skill, 0)
        # rank is index: 0 untrained, 1 trained, etc.
        if rank >= 1:
            return ValidationResult(
                legal=True,
                reason=f"Success: Action '{action}' is legal. Roll {skill.capitalize()} vs DC (proficiency rank {rank} ≥ trained).",
                rule_citation=f"Core Rulebook - {skill.capitalize()}",
            )
        else:
            return ValidationResult(
                legal=False,
                reason=f"Error: {action.capitalize()} requires {skill.capitalize()} (trained+). Character is untrained (rank 0).",
                rule_citation=f"Core Rulebook - {skill.capitalize()} (Untrained)",
            )

    # ══════════════════════════════════════════════════════════════
    # Ollama Function Calling Interface
    # ══════════════════════════════════════════════════════════════

    async def run_with_tools(self, user_query: str) -> str:
        """Run the agent with Ollama function calling."""
        client = self.ollama
        messages = [
            {"role": "system", "content": RULES_LAWYER_SYSTEM},
            {"role": "user", "content": user_query}
        ]

        # First call - let LLM decide which tool to use
        response = await client.generate(
            prompt=json.dumps(messages),
            system="",
            model=self.settings.model_for("reasoning"),
        )
        return response

    async def stream_adjudication(
        self,
        query: str,
        edition: str = "2e",
        context: list[dict] | None = None,
        abstain: bool = False,
        route_score: float | None = None,
    ) -> tuple[AsyncGenerator[str, None], list[Citation]]:
        """Adjudicate a rules question and yield it verbatim.

        BP-08 Pillar B. This exists so the GM never re-narrates a rules ruling:
        the caller streams these chunks straight to the client and then appends
        the deterministic Sources block. Re-narration by a second model was
        stripping mechanical nuance and mutating exact citation tags.

        Returns a tuple of (stream, citations) rather than a string so the
        caller can emit the body first and the citations afterwards, and so the
        stream has to be consumed lazily - a concatenated string cannot be
        un-concatenated by the orchestrator.

        Citations come from the retrieval rows (`context`), never from the
        model's output, so they are exactly the rules that were in front of it.
        """
        citations = [
            Citation(
                source_book=str(hit.get("source_book") or ""),
                name=str(hit.get("name") or ""),
                category=str(hit.get("category") or ""),
            )
            for hit in (context or [])
            if hit.get("name")
        ]

        # Pillar A hard stop. When there is nothing to ground an answer we do
        # NOT call the model at all: relying on a 3B model to obey a "don't
        # invent a number" instruction is precisely how the "DC of 20" and the
        # fabricated Waffle Iron DC got into the game in the first place.
        #
        # Both conditions trigger it: an explicit `abstain` from the caller's
        # calibrated gate, OR retrieval that produced no citable row. The second
        # matters because it makes the guarantee hold for every caller instead
        # of depending on each one having run the gate first.
        if abstain or not citations:
            # Record WHY we could not answer. A refusal is correct behaviour,
            # but a rising count is the signal that the rules DB is missing
            # material the group actually asks about.
            log_miss(
                "abstain",
                query,
                route_score=route_score,
                details={
                    "reason": "flagged" if abstain else "no_retrieval",
                    "edition": edition,
                    "rows": len(context or []),
                },
            )

            async def _refuse() -> AsyncGenerator[str, None]:
                yield ABSTENTION_TEXT

            return _refuse(), []

        valid_tags = {c.tag() for c in citations}

        async def _generate() -> AsyncGenerator[str, None]:
            # Reached only when `citations` is non-empty, i.e. there is at least
            # one citable row. The previous shape also appended
            # _ABSTENTION_INSTRUCTION when `not context`, but that branch became
            # unreachable once empty context short-circuited above: reaching here
            # requires a citable row, which requires a non-empty context.
            system = RULES_LAWYER_SYSTEM
            scrubber = InlineCitationScrubber(valid_tags)
            async for chunk in self.ollama.stream(
                prompt=query,
                system=system,
                model=self.settings.model_for("reasoning"),
            ):
                if chunk:
                    safe = scrubber.feed(chunk)
                    if safe:
                        yield safe
            tail = scrubber.finish()
            if tail:
                yield tail
            if scrubber.stripped:
                # The model cited rules it was never shown: a retrieval or
                # prompt defect worth chasing, not something to show the player.
                log_miss(
                    "bad_inline_citation",
                    query,
                    route_score=route_score,
                    details={"stripped": scrubber.stripped[:10]},
                )

        return _generate(), citations

    async def adjudicate(
        self,
        query: str,
        edition: str = "2e",
        context: list[dict] | None = None,
        abstain: bool = False,
        route_score: float | None = None,
    ) -> tuple[str, list[Citation]]:
        """Buffered counterpart of stream_adjudication.

        Returns (answer, citations). Same zero-LLM guarantee: with abstain=True
        (or with no usable context) this returns the deterministic refusal
        without touching Ollama. Inline citation scrubbing happens in the shared
        stream, so the buffered path inherits it.
        """
        stream, citations = await self.stream_adjudication(
            query=query,
            edition=edition,
            context=context,
            abstain=abstain,
            route_score=route_score,
        )
        parts: list[str] = []
        async for chunk in stream:
            parts.append(chunk)
        return "".join(parts), citations


# ══════════════════════════════════════════════════════════════
# Standalone Tool Functions (for direct calling)
# ══════════════════════════════════════════════════════════════

async def lookup_rule_tool(query: str, repo: CampaignRepository) -> dict:
    agent = RulesLawyerAgent(repo)
    result = await agent.lookup_rule(query)
    return {"name": result.name, "content": result.content, "source_book": result.source_book}


async def calculate_dc_tool(level: int, rarity: str = "common", proficiency: str = "trained", repo: CampaignRepository = None) -> dict:
    agent = RulesLawyerAgent(repo or CampaignRepository())
    result = await agent.calculate_dc(level, rarity, proficiency)
    return {"dc": result.dc, "breakdown": result.breakdown}


async def validate_action_tool(action: str, character_sheet: dict, target: dict | None = None, repo: CampaignRepository = None) -> dict:
    agent = RulesLawyerAgent(repo or CampaignRepository())
    result = await agent.validate_action(action, character_sheet, target)
    return {"legal": result.legal, "reason": result.reason, "rule_citation": result.rule_citation}
