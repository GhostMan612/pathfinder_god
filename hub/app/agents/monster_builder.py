# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Monster Builder Agent — LLM stat block + deterministic PF2e sanity checks.

Same pattern as CharacterBuilderAgent:
1. LLM generates a complete PF2e creature JSON blueprint with format="json",
   retried up to 3 times by app.agents.json_builder with the validation
   error fed back.
2. MonsterModel (Pydantic) validates the shape; _validate_monster checks
   the numbers are plausible for the creature's level (HP/AC/saves/damage).
3. A boss is not a separate builder: build(..., elite=True) applies the
   elite template (+2 AC/saves/attack/damage, HP x1.2) after validation,
   matching EncounterBuilderAgent.TEMPLATE_MODIFIERS.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.json_builder import generate_validated_json
from app.config import get_settings

logger = logging.getLogger(__name__)

DAMAGE_RE = re.compile(r"^\s*(\d+)\s*d\s*(\d+)\s*(?:\+\s*(\d+))?\s*$")
VALID_DICE = (4, 6, 8, 10, 12, 20)


class MonsterSaves(BaseModel):
    fortitude: int = Field(..., ge=-5, le=50)
    reflex: int = Field(..., ge=-5, le=50)
    will: int = Field(..., ge=-5, le=50)


class MonsterStrike(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    attack_bonus: int = Field(..., ge=-5, le=50)
    damage: str = Field(..., min_length=3, max_length=20)  # NdM, e.g. "2d8+4"
    damage_type: str = Field(default="slashing", max_length=40)
    damage_bonus: int = Field(default=0, ge=-5, le=20)


class MonsterModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    level: int = Field(..., ge=1, le=20)
    creature_type: str = Field(..., min_length=1, max_length=60)
    traits: list[str] = Field(default_factory=list, max_length=10)
    hp: int = Field(..., ge=1, le=100000)  # cap is shape-only; validate_monster enforces plausibility per level
    ac: int = Field(..., ge=5, le=60)
    perception: int = Field(..., ge=-5, le=50)
    saves: MonsterSaves
    strikes: list[MonsterStrike] = Field(..., min_length=1, max_length=10)
    abilities: list[str] = Field(default_factory=list, max_length=20)
    tactics: str = Field(default="", max_length=1000)
    loot_table: list[str] = Field(default_factory=list, max_length=20)
    template: Literal["normal", "elite", "weak"] = "normal"


@dataclass
class MonsterBuildResult:
    valid: bool
    monster: MonsterModel | None
    errors: list[str] = field(default_factory=list)
    attempts: int = 1


SYSTEM_PROMPT = """You are a Pathfinder 2e monster designer.
Output ONLY a JSON object matching this schema exactly. No markdown, no commentary.

Required fields:
- name: evocative creature name (string)
- level: integer 1-20
- creature_type: string (e.g. "undead", "beast", "humanoid", "fiend", "construct")
- traits: array of strings (e.g. ["undead", "evil"])
- hp: integer, plausible hit points for the level (roughly 10-40 at level 1, growing with level)
- ac: integer, plausible Armor Class for the level (roughly 12-18 at level 1, growing with level)
- perception: integer modifier
- saves: {fortitude, reflex, will} integer modifiers
- strikes: array of at least one {name, attack_bonus, damage ("NdM" or "NdM+X"), damage_type, damage_bonus}
- abilities: array of special ability names/descriptions (strings)
- tactics: one or two sentences describing how it fights
- loot_table: array of strings (items it might carry)

Rules:
- Damage dice must be NdM with M in 4, 6, 8, 10, 12, 20 and 1-6 dice
- Build a NORMAL creature; any elite/weak template is applied afterwards, not by you
"""


def validate_monster(model: MonsterModel, requested_level: int | None = None) -> list[str]:
    """Deterministic PF2e sanity checks on a validated MonsterModel."""
    errors: list[str] = []
    level = model.level
    if requested_level is not None and level != requested_level:
        errors.append(f"Requested level {requested_level}, got level {level}")
    # HP: generous PF2e-plausible band. Level 1 creatures sit ~8-40 HP;
    # even the toughest level 20 creature stays well under 40 + 30/level.
    hp_min = max(1, level * 3)
    hp_max = 40 + level * 30
    if not (hp_min <= model.hp <= hp_max):
        errors.append(f"HP {model.hp} implausible for level {level} (expected {hp_min}-{hp_max})")
    # AC: roughly 10 + level at the low end, 30 + level at the high end.
    if not (8 + level <= model.ac <= 30 + level):
        errors.append(f"AC {model.ac} implausible for level {level} (expected {8 + level}-{30 + level})")
    for strike in model.strikes:
        match = DAMAGE_RE.match(strike.damage or "")
        if not match:
            errors.append(f"Strike '{strike.name}' damage '{strike.damage}' is not NdM notation")
            continue
        dice_count, die = int(match.group(1)), int(match.group(2))
        if not (1 <= dice_count <= 6):
            errors.append(f"Strike '{strike.name}' has {dice_count} damage dice (expected 1-6)")
        if die not in VALID_DICE:
            errors.append(f"Strike '{strike.name}' uses d{die} (expected d4/d6/d8/d10/d12/d20)")
    return errors


class MonsterBuilderAgent:
    def __init__(self, llm):
        self._llm = llm
        self._settings = get_settings()

    async def build(
        self, prompt: str, level: int | None = None, elite: bool = False
    ) -> MonsterBuildResult:
        full_prompt = SYSTEM_PROMPT + "\n\nUser request: " + prompt.strip()
        if level is not None:
            full_prompt += f"\nTarget level: {level}"
        validated: dict[str, MonsterModel] = {}

        def _validate(data: object) -> list[str]:
            if not isinstance(data, dict):
                return ["LLM returned a JSON value that is not an object"]
            try:
                model = MonsterModel.model_validate(data)
            except Exception as exc:
                return [f"Schema validation failed: {exc}"]
            monster_errors = validate_monster(model, requested_level=level)
            if monster_errors:
                return monster_errors
            validated["model"] = model
            return []

        outcome = await generate_validated_json(
            self._llm,
            prompt=full_prompt,
            model=self._settings.model_for("builders"),
            temperature=0.3,
            num_predict=1200,
            validate=_validate,
        )
        if outcome.data is None or "model" not in validated:
            logger.info("MonsterBuilder validation failed: %s", outcome.errors)
            return MonsterBuildResult(
                False, None, outcome.errors or ["LLM returned no valid JSON object"],
                attempts=outcome.attempts,
            )

        model = validated["model"]
        if elite:
            model = self._apply_elite(model)
        return MonsterBuildResult(True, model, outcome.errors, attempts=outcome.attempts)

    @staticmethod
    def _apply_elite(model: MonsterModel) -> MonsterModel:
        """Elite template (Bestiary building rules): +2 AC/saves/attack/damage, HP x1.2."""
        return model.model_copy(
            update={
                "template": "elite",
                "hp": max(1, int(model.hp * 1.2)),
                "ac": model.ac + 2,
                "saves": model.saves.model_copy(
                    update={
                        "fortitude": model.saves.fortitude + 2,
                        "reflex": model.saves.reflex + 2,
                        "will": model.saves.will + 2,
                    }
                ),
                "strikes": [
                    s.model_copy(
                        update={
                            "attack_bonus": s.attack_bonus + 2,
                            "damage_bonus": s.damage_bonus + 2,
                        }
                    )
                    for s in model.strikes
                ],
            }
        )
