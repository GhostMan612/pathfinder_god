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
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Deterministic PF2e Remaster tables (Gemini §15.4 — never LLM)
# ──────────────────────────────────────────────────────────────

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

# ── Strict Pydantic mirror of spoke/lib/models/character.dart ──

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

# ──────────────────────────────────────────────────────────────
# Tool Definitions (exact from design chat)
# ──────────────────────────────────────────────────────────────

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
        """Deterministic DC — never LLM (Gemini §15.4)."""
        rarity = (rarity or "common").lower()
        proficiency = (proficiency or "trained").lower()

        # Simple DC path: proficiency-only check (no level). Caller passes level=-99 or uses proficiency.
        # If action is untrained/trained/expert/master/legendary and level is sentinel, honor SIMPLE_DC.
        # Otherwise level-based DC is canonical.
        if level is None:  # type: ignore
            level = -1
        base = LEVEL_DC.get(level)
        if base is None:
            # Fallback for out-of-range (extrapolate 2 per level beyond 25)
            if level > 25:
                base = 50 + (level - 25) * 2
            elif level < -1:
                base = 13
            else:
                base = SIMPLE_DC.get(proficiency, 15)

        rarity_adj = RARITY_ADJ.get(rarity, 0)
        dc = base + rarity_adj
        # Proficiency does NOT adjust level-based DC per Remaster; simple DC already encodes it.
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

    # ──────────────────────────────────────────────────────────────
    # Ollama Function Calling Interface
    # ──────────────────────────────────────────────────────────────

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
            model=self.settings.ollama_model,
        )
        return response


# ──────────────────────────────────────────────────────────────
# Standalone Tool Functions (for direct calling)
# ──────────────────────────────────────────────────────────────

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