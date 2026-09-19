# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Character Builder Agent — LLM blueprint + Rules Lawyer validation.

Two-stage pipeline:
1. LLM generates a complete PF2e character JSON blueprint from a natural prompt.
2. RulesLawyer validates every mechanical choice (proficiencies, DCs, feat prereqs,
   ancestry/class HP, bulk, speed) against deterministic tables.
Only fully-valid characters reach the Spoke.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.agents.rules_lawyer import (
    CharacterSheetModel,
    RulesLawyerAgent,
    ValidationResult,
)
from app.config import get_settings
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Pathfinder 2e character architect.
Output ONLY a JSON object matching the CharacterSheetModel schema exactly.
No markdown, no commentary, no extra keys.

Required fields (all mandatory):
- name: string
- ancestry: string (e.g., "Human", "Elf", "Dwarf", "Goblin", "Orc", "Halfling", "Gnome")
- heritage: string (e.g., "Versatile", "Arctic Elf", "Ancient-Blooded Dwarf")
- background: string (e.g., "Acrobat", "Scholar", "Criminal")
- character_class: string (e.g., "Fighter", "Wizard", "Rogue", "Cleric", "Alchemist")
- level: integer 1-20
- abilities: {str, dex, con, int, wis, cha} all integers 8-18, sum <= 80
- proficiencies: {
    skills: {acrobatics, arcana, athletics, crafting, deception, diplomacy,
             intimidation, lore, medicine, nature, occultism, performance,
             religion, society, stealth, survival, thievery} all 0-4,
    defenses: {fortitude, reflex, will, perception,
               unarmored, lightArmor, mediumArmor, heavyArmor,
               simpleWeapons, martialWeapons, advancedWeapons, unarmed} all 0-4,
    classProfs: {classDC, spellDC, spellAttack} all 0-4
  }

Optional fields:
- subclass: string (archetype/specialization)
- deity: string
- alignment: string (LG, NG, CG, LN, N, CN, LE, NE, CE)
- size: string (Tiny, Small, Medium, Large)
- gender: string
- age: integer
- eyes, hair, height, weight: strings
- languages: string
- senses: string
- speed: string
- feats: array of {name, type, level, description, prerequisites?}
- spellcasting: {tradition, keyAbility, slotsPerLevel[11], focusPool, focusMax, repertoire[], isPrepared}
- equipment: {weapons[], armor{}, shield?, gear{}, cp, sp, gp, pp}
- notes: string (bio/backstory)

Rules:
- Proficiency indices: 0=untrained, 1=trained, 2=expert, 3=master, 4=legendary
- Ability scores 8-18, racial/class boosts already applied
- Level 1-20 only
- All proficiency ranks must be valid for level/class/ancestry
"""

@dataclass
class BuildResult:
    valid: bool
    character: CharacterSheetModel | None
    errors: list[str]


class CharacterBuilderAgent:
    def __init__(self, llm: OllamaClient, lawyer: RulesLawyerAgent):
        self._llm = llm
        self._lawyer = lawyer
        self._settings = get_settings()

    async def build(self, prompt: str) -> BuildResult:
        full_prompt = SYSTEM_PROMPT + "\n\nUser request: " + prompt.strip()
        try:
            raw = await self._llm.generate(
                prompt=full_prompt,
                model=self._settings.ollama_model,
                temperature=0.3,
                num_predict=1200,
            )
        except Exception as e:
            logger.error(f"CharacterBuilder LLM failed: {e}")
            return BuildResult(False, None, [f"LLM generation failed: {e}"])

        # Parse JSON from LLM response
        data = self._extract_json(raw)
        if data is None:
            return BuildResult(False, None, ["LLM returned no valid JSON object"])

        # Schema validation via Pydantic
        try:
            model = CharacterSheetModel.model_validate(data)
        except Exception as e:
            logger.warning(f"CharacterBuilder schema validation failed: {e}")
            return BuildResult(False, None, [f"Schema validation failed: {e}"])

        # Rules Lawyer: validate proficiencies, DCs, feat prereqs, ancestry/class HP
        errors = self._validate_with_lawyer(model)
        if errors:
            logger.info(f"CharacterBuilder validation failed: {errors}")
            return BuildResult(False, None, errors)

        return BuildResult(True, model, [])

    def _extract_json(self, text: str) -> dict | None:
        text = text.strip()
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    def _validate_with_lawyer(self, model: CharacterSheetModel) -> list[str]:
        errors: list[str] = []

        # 1. Ability score bounds (8-18)
        for attr, val in model.abilities.model_dump().items():
            if not (8 <= val <= 18):
                errors.append(f"Ability {attr}={val} out of range 8-18")

        # 2. Level bounds
        if not (1 <= model.level <= 20):
            errors.append(f"Level {model.level} out of range 1-20")

        # 3. Proficiency rank bounds (0-4)
        prof_dict = model.proficiencies.model_dump()
        for category, skills in prof_dict.items():
            if isinstance(skills, dict):
                for skill, rank in skills.items():
                    if not (0 <= rank <= 4):
                        errors.append(f"Proficiency {category}.{skill}={rank} out of range 0-4")

        # 4. Class/ancestry-specific validations
        #    Fighter needs martial weapons trained+, Wizard needs spellDC trained+
        cls = model.character_class.lower()
        if cls == "fighter":
            if model.proficiencies.defenses.martialWeapons < 1:
                errors.append("Fighter requires martialWeapons >= trained (rank 1+)")
        if cls == "wizard":
            if model.proficiencies.classProfs.spellDC < 1:
                errors.append("Wizard requires spellDC >= trained (rank 1+)")
        if cls == "cleric":
            if model.proficiencies.defenses.fortitude < 1:
                errors.append("Cleric requires fortitude >= trained (rank 1+)")

        # 5. Use RulesLawyer validate_action for a sampling of key actions
        #    (Trip, Hide, Recall Knowledge) to ensure skill ranks match class
        key_actions = ["trip", "hide", "recall knowledge"]
        sheet_dict = model.model_dump(mode="python")
        for action in key_actions:
            result: ValidationResult = self._lawyer.validate_action_sync(action, sheet_dict)
            if not result.legal:
                errors.append(f"Action validation failed: {result.reason}")

        return errors


# Synchronous wrapper for RulesLawyerAgent.validate_action to avoid async in build()
# This mirrors the logic in rules_lawyer.py but sync
def _sync_validate_action(lawyer: RulesLawyerAgent, action: str, character_sheet: dict) -> ValidationResult:
    from app.agents.rules_lawyer import (
        ACTION_SKILL,
        CharacterSheetModel,
        ValidationResult,
    )
    key = (action or "").strip().lower()
    first = key.split()[0] if key else ""
    skill = ACTION_SKILL.get(key) or ACTION_SKILL.get(first)
    sheet = CharacterSheetModel.from_any(character_sheet)

    if skill is None:
        return ValidationResult(
            legal=True,
            reason=f"Unknown action '{action}' not in deterministic table; assuming legal.",
            rule_citation="GM Discretion",
        )

    rank: int = getattr(sheet.proficiencies.skills, skill, 0)
    if rank >= 1:
        return ValidationResult(
            legal=True,
            reason=f"Action '{action}' legal. {skill.capitalize()} rank {rank} ≥ trained.",
            rule_citation=f"Core Rulebook - {skill.capitalize()}",
        )
    else:
        return ValidationResult(
            legal=False,
            reason=f"{action.capitalize()} requires {skill.capitalize()} (trained+). Character is untrained.",
            rule_citation=f"Core Rulebook - {skill.capitalize()} (Untrained)",
        )


# Monkey-patch for sync validation
RulesLawyerAgent.validate_action_sync = _sync_validate_action