# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
NPC Compiler Agent — Phase 5: Stat block factory with Ollama function calling.

Tools (exact from design chat):
- create_npc(concept) -> builds legal ABC, assigns ability scores, skills, feats
- save_npc_to_db(npc_json)
- level_up(character_id)

Outputs JSON importable by Foundry VTT / Pathbuilder.

Pipeline (same pattern as CharacterBuilderAgent):
1. LLM generates an NPC JSON blueprint with format="json", retried up to
   3 times by app.agents.json_builder with the validation error fed back.
2. NPCModel (Pydantic) validates the blueprint: level 1-20, ability scores
   8-18, skill ranks, feat levels/types.
3. Only a fully-valid NPC reaches the caller. When the LLM is unavailable
   or every retry is rejected, the deterministic template
   (_build_from_concept) is used as a clearly-marked fallback
   (source="fallback"), never silently passed off as LLM-generated.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.json_builder import generate_validated_json
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Tool Definitions (exact from design chat)
# ──────────────────────────────────────────────────────────────

NPC_COMPILER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_npc",
            "description": "Build a legal Pathfinder NPC from concept. Returns full ABC stat block.",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string", "description": "e.g., 'cranky level 5 Dwarven alchemist shopkeep who hates the Pathfinder Society'"}
                },
                "required": ["concept"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_npc_to_db",
            "description": "Save NPC JSON to campaign database",
            "parameters": {
                "type": "object",
                "properties": {
                    "npc_json": {"type": "object"}
                },
                "required": ["npc_json"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "level_up",
            "description": "Level up an existing NPC",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer"}
                },
                "required": ["character_id"]
            }
        }
    }
]

NPC_COMPILER_SYSTEM = """You are a Pathfinder NPC Compiler. Build legal ABC stat blocks.
Output JSON matching the exact schema below. No flavor text.
Follow Pathfinder 2e ABC rules: Ancestry + Background + Class.
Assign ability scores using standard array or point buy.
Select valid feats for level. Include all derived stats (AC, saves, HP, Perception, class DC, spell DC).
Return ONLY the JSON object."""


NPC_SCHEMA = {
    "name": "string",
    "level": "integer",
    "ancestry": "string",
    "heritage": "string | null",
    "background": "string",
    "class": "string",
    "key_ability": "string",
    "ability_scores": {"str": "int", "dex": "int", "con": "int", "int": "int", "wis": "int", "cha": "int"},
    "ac": "int | null",
    "hp": "int | null",
    "perception": "int | null",
    "saves": {"fortitude": "int", "reflex": "int", "will": "int"},
    "class_dc": "int | null",
    "spell_dc": "int | null",
    "skills": [{"name": "string", "rank": "untrained|trained|expert|master|legendary", "modifier": "int"}],
    "feats": [{"name": "string", "level": "int", "type": "ancestry|skill|class|general"}],
    "formulas": ["string"],  # for alchemists (optional)
    "equipment": [{"name": "string", "quantity": "int", "bulk": "string"}],
    "personality": "string",
    "hooks": ["string"]
}


# ──────────────────────────────────────────────────────────────
# Validated NPC model (mirrors NPC_SCHEMA)
# ──────────────────────────────────────────────────────────────

_SKILL_RANKS = ("untrained", "trained", "expert", "master", "legendary")
_FEAT_TYPES = ("ancestry", "skill", "class", "general")


class NPCAbilityScores(BaseModel):
    # "int" cannot be a field name under `from __future__ import annotations`
    # (the annotation `int` then resolves to the field itself); same
    # int_/alias pattern as rules_lawyer.AbilityScoresModel.
    model_config = {"populate_by_name": True}

    str: int = Field(..., ge=8, le=18)
    dex: int = Field(..., ge=8, le=18)
    con: int = Field(..., ge=8, le=18)
    int_: int = Field(..., ge=8, le=18, alias="int")
    wis: int = Field(..., ge=8, le=18)
    cha: int = Field(..., ge=8, le=18)


class NPCSaves(BaseModel):
    fortitude: int = Field(..., ge=-5, le=50)
    reflex: int = Field(..., ge=-5, le=50)
    will: int = Field(..., ge=-5, le=50)


class NPCSkill(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    rank: Literal["untrained", "trained", "expert", "master", "legendary"]
    modifier: int = Field(..., ge=-10, le=50)


class NPCFeat(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    level: int = Field(..., ge=1, le=20)
    type: Literal["ancestry", "skill", "class", "general"]


class NPCEquipment(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    quantity: int = Field(default=1, ge=1, le=999)
    bulk: str = Field(default="1", max_length=10)


class NPCModel(BaseModel):
    """Validated NPC blueprint, matching NPC_SCHEMA exactly."""

    model_config = {"populate_by_name": True}

    name: str = Field(..., min_length=1, max_length=120)
    level: int = Field(..., ge=1, le=20)
    ancestry: str = Field(..., min_length=1, max_length=60)
    heritage: str | None = Field(default=None, max_length=60)
    background: str = Field(..., min_length=1, max_length=120)
    class_: str = Field(..., alias="class", min_length=1, max_length=60)
    key_ability: Literal["str", "dex", "con", "int", "wis", "cha"]
    ability_scores: NPCAbilityScores
    ac: int | None = Field(default=None, ge=1, le=60)
    hp: int | None = Field(default=None, ge=1, le=100000)
    perception: int | None = Field(default=None, ge=-5, le=50)
    saves: NPCSaves | None = None
    class_dc: int | None = Field(default=None, ge=1, le=60)
    spell_dc: int | None = Field(default=None, ge=1, le=60)
    skills: list[NPCSkill] = Field(default_factory=list, max_length=30)
    feats: list[NPCFeat] = Field(default_factory=list, max_length=30)
    formulas: list[str] = Field(default_factory=list, max_length=30)
    equipment: list[NPCEquipment] = Field(default_factory=list, max_length=30)
    personality: str = Field(default="", max_length=1000)
    hooks: list[str] = Field(default_factory=list, max_length=10)


@dataclass
class NPCStatBlock:
    name: str
    level: int
    ancestry: str
    heritage: str | None
    background: str
    class_: str
    key_ability: str
    ability_scores: dict[str, int]
    skills: list[dict]
    feats: list[dict]
    formulas: list[str] | None
    equipment: list[dict]
    personality: str
    hooks: list[str]
    ac: int | None = None
    hp: int | None = None
    perception: int | None = None
    saves: dict[str, int] | None = None
    class_dc: int | None = None
    spell_dc: int | None = None
    # Provenance: "llm" when the blueprint came from the model, "fallback"
    # when every LLM attempt failed and the deterministic template was used.
    source: str = "llm"
    attempts: int = 1
    errors: list[str] = field(default_factory=list)

    def to_foundry_json(self) -> dict:
        """Convert to Foundry VTT Actor import format."""
        return {
            "name": self.name,
            "type": "npc",
            "system": {
                "details": {
                    "level": {"value": self.level},
                    "ancestry": self.ancestry,
                    "heritage": self.heritage or "",
                    "background": self.background,
                    "class": self.class_,
                },
                "abilities": self.ability_scores,
                "attributes": {
                    "ac": {"value": self.ac},
                    "hp": {"value": self.hp, "max": self.hp},
                    "perception": {"value": self.perception},
                    "classDC": {"value": self.class_dc},
                    "spellDC": {"value": self.spell_dc},
                },
                "saves": self.saves or {},
                "skills": {s["name"]: {"rank": s["rank"], "value": s["modifier"]} for s in self.skills},
                "feats": {f["name"]: {"level": f["level"], "type": f["type"]} for f in self.feats},
                "equipment": self.equipment,
            },
            "flags": {"core": {"personality": self.personality, "hooks": self.hooks}}
        }


@dataclass
class NPCBuildResult:
    valid: bool
    npc: NPCStatBlock | None
    source: str  # "llm" | "fallback"
    attempts: int
    errors: list[str] = field(default_factory=list)


class NPCCompilerAgent:
    def __init__(self, repo: CampaignRepository, llm: OllamaClient | None = None):
        self.repo = repo
        self.settings = get_settings()
        self.ollama = llm or OllamaClient(self.settings.ollama_host)

    async def build(self, concept: str) -> NPCBuildResult:
        """Generate an NPC from a concept via the LLM, with template fallback.

        Returns a valid NPC in all normal cases: LLM blueprint when it
        validates, otherwise the deterministic template marked
        source="fallback" with the LLM errors attached.
        """
        prompt = (
            NPC_COMPILER_SYSTEM
            + "\n\nSchema (exact JSON keys):\n"
            + json.dumps(NPC_SCHEMA, indent=2)
            + "\n\nConcept: "
            + concept.strip()
        )
        validated: dict[str, NPCModel] = {}

        def _validate(data: object) -> list[str]:
            if not isinstance(data, dict):
                return ["LLM returned a JSON value that is not an object"]
            try:
                validated["model"] = NPCModel.model_validate(data)
            except Exception as exc:
                return [f"Schema validation failed: {exc}"]
            return []

        outcome = await generate_validated_json(
            self.ollama,
            prompt=prompt,
            model=self.settings.model_for("builders"),
            temperature=0.3,
            num_predict=1200,
            validate=_validate,
        )
        if outcome.data is not None and "model" in validated:
            npc = self._stat_block_from_model(
                validated["model"],
                source="llm",
                attempts=outcome.attempts,
                errors=outcome.errors,
            )
            return NPCBuildResult(True, npc, "llm", outcome.attempts, outcome.errors)

        logger.warning(
            "NPC LLM build failed after %d attempt(s) (%s); using template fallback",
            outcome.attempts,
            "; ".join(outcome.errors),
        )
        try:
            fallback = self._build_from_concept(concept)
        except Exception as exc:  # pragma: no cover - template is deterministic
            logger.error("NPC template fallback failed: %s", exc)
            return NPCBuildResult(
                False, None, "fallback", outcome.attempts, [*outcome.errors, f"Fallback failed: {exc}"]
            )
        fallback.source = "fallback"
        fallback.attempts = outcome.attempts
        fallback.errors = [
            *outcome.errors,
            "LLM generation failed after retries; used deterministic template fallback",
        ]
        return NPCBuildResult(True, fallback, "fallback", outcome.attempts, fallback.errors)

    async def create_npc(self, concept: str) -> NPCStatBlock:
        """Generate NPC from concept using Ollama with structured output."""
        result = await self.build(concept)
        if result.npc is None:
            raise RuntimeError(f"NPC build failed: {'; '.join(result.errors)}")
        return result.npc

    async def save_npc_to_db(self, npc_json: dict, campaign_id: int = 1) -> dict:
        return await save_npc_to_db_tool(npc_json, self.repo, campaign_id)

    async def level_up(self, character_id: int, campaign_id: int = 1) -> dict:
        return await level_up_tool(character_id, self.repo, campaign_id)

    @staticmethod
    def _stat_block_from_model(
        model: NPCModel,
        *,
        source: str,
        attempts: int,
        errors: list[str],
    ) -> NPCStatBlock:
        return NPCStatBlock(
            name=model.name,
            level=model.level,
            ancestry=model.ancestry,
            heritage=model.heritage,
            background=model.background,
            class_=model.class_,
            key_ability=model.key_ability,
            ability_scores=model.ability_scores.model_dump(by_alias=True),
            skills=[s.model_dump() for s in model.skills],
            feats=[f.model_dump() for f in model.feats],
            formulas=list(model.formulas) if model.formulas else None,
            equipment=[e.model_dump() for e in model.equipment],
            personality=model.personality,
            hooks=list(model.hooks),
            ac=model.ac,
            hp=model.hp,
            perception=model.perception,
            saves=model.saves.model_dump() if model.saves else None,
            class_dc=model.class_dc,
            spell_dc=model.spell_dc,
            source=source,
            attempts=attempts,
            errors=list(errors),
        )

    def _build_from_concept(self, concept: str) -> NPCStatBlock:
        """Parse concept and build legal ABC stat block.

        Deterministic template. Used ONLY as the fallback when the LLM is
        unavailable or every retry is rejected; callers mark it as such.
        """
        # Parse level from concept
        level_match = re.search(r"level\s+(\d+)", concept, re.IGNORECASE)
        level = int(level_match.group(1)) if level_match else 1
        level = max(1, min(level, 20))

        # Parse ancestry/class from concept (simplified)
        concept_lower = concept.lower()
        ancestry = "Human"
        # Match on stems. The previous equality-free substring test looked correct but
        # "dwarf" is not a substring of "dwarven" (d-w-a-r-f vs d-w-a-r-v), nor is
        # "elf" of "elven". Every adjectival form therefore fell through to Human,
        # so a "Dwarven alchemist" got Human feats.
        for stem, name in (
            ("halfling", "Halfling"),
            ("dwarv", "Dwarf"),  # adjectival "Dwarven" (see note above)
            ("dwarf", "Dwarf"),
            ("gnome", "Gnome"),
            ("goblin", "Goblin"),
            ("elv", "Elf"),  # adjectival "Elven"
            ("elf", "Elf"),
            ("half-orc", "Half-Orc"),
            ("orc", "Orc"),
            ("tiefling", "Tiefling"),
            ("human", "Human"),
        ):
            if stem in concept_lower:
                ancestry = name
                break

        class_ = "Fighter"
        if "wizard" in concept_lower: class_ = "Wizard"
        elif "rogue" in concept_lower: class_ = "Rogue"
        elif "cleric" in concept_lower: class_ = "Cleric"
        elif "alchemist" in concept_lower: class_ = "Alchemist"
        elif "bard" in concept_lower: class_ = "Bard"
        elif "champion" in concept_lower: class_ = "Champion"
        elif "ranger" in concept_lower: class_ = "Ranger"
        elif "sorcerer" in concept_lower: class_ = "Sorcerer"

        # Build basic stat block. Derived values are still approximate, but they
        # are present (the LLM path must supply its own via NPCModel).
        scores = self._standard_array(level)
        mods = {key: (value - 10) // 2 for key, value in scores.items()}
        key_ability = self._key_ability(class_)
        class_dc = 10 + level + 2 + mods[key_ability]
        return NPCStatBlock(
            name=self._generate_name(ancestry, class_, concept),
            level=level,
            ancestry=ancestry,
            heritage=None,
            background="Merchant" if "shopkeep" in concept_lower else "Artisan",
            class_=class_,
            key_ability=key_ability,
            ability_scores=scores,
            skills=self._skills_for_class(class_, level),
            feats=self._feats_for_class(class_, level, ancestry),
            formulas=self._formulas_for_class(class_),
            equipment=self._equipment_for_class(class_),
            personality="Gruff, suspicious of the Pathfinder Society, secretly proud of his craft",
            hooks=["Needs rare reagent from Pathfinder lodge", "Hides a Pathfinder star in his cellar"],
            ac=10 + level + 4,
            hp=max(1, 12 + level * 5 + mods["con"]),
            perception=level + 2 + mods["wis"],
            saves={
                "fortitude": level + 2 + mods["con"],
                "reflex": level + 2 + mods["dex"],
                "will": level + 2 + mods["wis"],
            },
            class_dc=class_dc,
            spell_dc=class_dc if class_ in {"Wizard", "Cleric", "Bard", "Sorcerer"} else None,
            source="fallback",
        )

    def _generate_name(self, ancestry: str, class_: str, concept: str) -> str:
        names = {
            "Dwarf": ["Thorin", "Borin", "Durin", "Gimli", "Kili", "Fili"],
            "Elf": ["Elrond", "Legolas", "Thranduil", "Celeborn", "Galadriel"],
            "Human": ["Marcus", "Aldric", "Bran", "Cedric", "Darian"],
            "Goblin": ["Ruk", "Grib", "Snag", "Vex", "Zik"],
        }
        options = names.get(ancestry, ["Adventurer"])
        digest = hashlib.sha256(
            f"{concept.strip().lower()}|{ancestry}|{class_}".encode()
        ).digest()
        return f"{options[digest[0] % len(options)]} the {class_}"

    def _key_ability(self, class_: str) -> str:
        return {"Wizard": "int", "Sorcerer": "cha", "Cleric": "wis", "Rogue": "dex",
                "Fighter": "str", "Champion": "str", "Ranger": "dex", "Alchemist": "int",
                "Bard": "cha"}.get(class_, "str")

    def _standard_array(self, level: int) -> dict[str, int]:
        # PF2e standard array: 15, 14, 13, 12, 10, 8.
        #
        # The previous base was 10/12/14/13/11/8 - not the standard array at all,
        # despite the comment - and boosts = level added a point per level to
        # STR/DEX/CON only, leaving INT/WIS/CHA at their base forever. At level 5
        # that produced CON 19 and DEX 17, which are unreachable in PF2e and were
        # then rejected by character_builder's own 8..18 range check.
        scores = {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}
        # +1 at 1st level, then one ASI per level, capped at 18.
        boosts = min(max(level, 0), 4)
        return {k: min(v + boosts, 18) for k, v in scores.items()}

    def _skills_for_class(self, class_: str, level: int) -> list[dict]:
        class_skills = {
            "Fighter": ["Athletics", "Intimidation", "Acrobatics"],
            "Wizard": ["Arcana", "Crafting", "Academic Lore"],
            "Rogue": ["Stealth", "Thievery", "Deception"],
            "Cleric": ["Medicine", "Religion", "Diplomacy"],
            "Alchemist": ["Crafting", "Medicine", "Academic Lore"],
            "Bard": ["Performance", "Diplomacy", "Deception"],
            "Champion": ["Athletics", "Religion", "Intimidation"],
            "Ranger": ["Survival", "Nature", "Stealth"],
            "Sorcerer": ["Arcana", "Deception", "Intimidation"],
        }
        skills = class_skills.get(class_, ["Athletics"])
        prof = "expert" if level >= 3 else "trained"
        return [{"name": s, "rank": prof, "modifier": level + 3} for s in skills]

    def _feats_for_class(self, class_: str, level: int, ancestry: str) -> list[dict]:
        feats = []
        # Ancestry feat at 1st
        feats.append({"name": f"{ancestry} Weapon Familiarity", "level": 1, "type": "ancestry"})
        # Class feats
        class_feats = {
            "Fighter": [("Sudden Charge", 1), ("Power Attack", 2), ("Quick Reversal", 4)],
            "Wizard": [("Reach Spell", 1), ("Widen Spell", 2), ("Quickened Casting", 4)],
            "Rogue": [("Surprise Attack", 1), ("Mobility", 2), ("Cunning Crawler", 4)],
            "Alchemist": [("Quick Bomber", 1), ("Calculated Splash", 2), ("Perpetual Infusions", 7)],
        }
        for name, lvl in class_feats.get(class_, []):
            if lvl <= level:
                feats.append({"name": name, "level": lvl, "type": "class"})
        return feats

    def _formulas_for_class(self, class_: str) -> list[str] | None:
        if class_ == "Alchemist":
            return ["Lesser Acid Flask", "Lesser Alchemist's Fire", "Bottled Lightning", "Lesser Elixir of Life"]
        return None

    def _equipment_for_class(self, class_: str) -> list[dict]:
        equipment = {
            "Fighter": [{"name": "Longsword", "quantity": 1, "bulk": "1"}, {"name": "Chain Mail", "quantity": 1, "bulk": "3"}],
            "Wizard": [{"name": "Spellbook", "quantity": 1, "bulk": "1"}, {"name": "Staff", "quantity": 1, "bulk": "1"}],
            "Rogue": [{"name": "Shortsword", "quantity": 1, "bulk": "1"}, {"name": "Leather Armor", "quantity": 1, "bulk": "1"}],
            "Alchemist": [{"name": "Alchemist's Tools", "quantity": 1, "bulk": "2"}, {"name": "Formula Book", "quantity": 1, "bulk": "1"}],
        }
        return equipment.get(class_, [{"name": "Backpack", "quantity": 1, "bulk": "1"}])


# ──────────────────────────────────────────────────────────────
# Standalone Tool Functions (for direct calling / Ollama function calling)
# ──────────────────────────────────────────────────────────────

async def create_npc_tool(concept: str, repo: CampaignRepository) -> dict:
    """Tool: create_npc(concept) -> full stat block JSON.

    The returned dict carries both ``"class"`` (the JSON-schema key) and
    ``"class_"`` (the dataclass field), so the create -> save flow can read
    either spelling, plus ``source``/``attempts`` provenance.
    """
    agent = NPCCompilerAgent(repo)
    npc = await agent.create_npc(concept)
    result = dict(npc.__dict__)
    result["class"] = npc.class_
    return result


async def save_npc_to_db_tool(npc_json: dict, repo: CampaignRepository, campaign_id: int = 1) -> dict:
    """Tool: save_npc_to_db(npc_json)"""
    npc_id = repo.upsert_npc(
        campaign_id=campaign_id,
        name=npc_json.get("name") or "Unknown",
        # NPCStatBlock declares class_, and create_npc_tool returns
        # npc.__dict__, so there is no "class" key - the documented
        # create_npc -> save_npc_to_db flow raised KeyError: 'class'.
        alias=npc_json.get("alias"),
        # schema.sql CHECKs restrict role to ally|enemy|neutral|unknown and
        # disposition to friendly|hostile|wary|unknown. "npc"/"neutral" both
        # violated those, so every save raised IntegrityError and the GM was
        # told the NPC had been stored when it had not.
        role="neutral",
        level=npc_json.get("level"),
        ancestry=npc_json.get("ancestry"),
        class_=npc_json.get("class_") or npc_json.get("class"),
        disposition="unknown",
        notes=json.dumps({"personality": npc_json.get("personality", ""), "hooks": npc_json.get("hooks", [])})
    )
    return {"id": npc_id, "saved": True}


async def level_up_tool(character_id: int, repo: CampaignRepository, campaign_id: int = 1) -> dict:
    """Tool: level_up(character_id)"""
    npc = repo.get_npc_by_id(campaign_id, character_id)
    if npc is None:
        return {"error": f"no NPC id {character_id} in campaign {campaign_id}"}
    new_level = (npc.level or 1) + 1
    repo.upsert_npc(
        campaign_id=campaign_id,
        name=npc.name,
        alias=npc.alias,
        role=npc.role,
        level=new_level,
        ancestry=npc.ancestry,
        class_=npc.class_,
        disposition=npc.disposition,
        notes=npc.notes,
    )
    return {"character_id": character_id, "leveled_up": True, "new_level": new_level}
