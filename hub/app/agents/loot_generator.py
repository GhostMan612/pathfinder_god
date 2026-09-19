# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Loot Generator Agent — LLM concept + deterministic PF2e crafting validation.

Two-stage pipeline:
1. LLM dreams up a thematic magic item from a natural prompt.
2. Deterministic tables validate item level, fundamental rune pricing,
   and damage-dice scaling; the RulesLawyer prices the Craft check DC.
Only fully-valid items reach the Spoke.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

POTENCY_RUNES: dict[int, tuple[int, int]] = {
    0: (0, 0),
    1: (2, 35),
    2: (10, 935),
    3: (16, 8975),
}

STRIKING_RUNES: dict[int, tuple[int, int]] = {
    0: (0, 0),
    1: (4, 65),
    2: (12, 1065),
    3: (19, 31000),
}

DAMAGE_RE = re.compile(r"^\s*(\d+)\s*d\s*(\d+)\s*$")


class LootItemModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    item_type: Literal["weapon", "armor", "worn", "consumable", "treasure", "ammunition"] = "weapon"
    level: int = Field(..., ge=1, le=20)
    price_gp: float = Field(..., ge=0)
    damage: str = ""
    damage_type: str = ""
    potency_rune: int = Field(default=0, ge=0, le=3)
    striking_rune: int = Field(default=0, ge=0, le=3)
    property_runes: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    rarity: Literal["common", "uncommon", "rare", "unique"] = "common"
    description: str = ""


@dataclass
class LootBuildResult:
    valid: bool
    item: LootItemModel | None
    craft_dc: int | None
    craft_dc_breakdown: str
    errors: list[str]


SYSTEM_PROMPT = """You are a Pathfinder 2e treasure vault curator.
Output ONLY a JSON object matching this schema exactly. No markdown, no commentary.

Required fields:
- name: evocative item name (string)
- item_type: one of weapon, armor, worn, consumable, treasure, ammunition
- level: integer 1-20 (item level, NOT character level)
- price_gp: number, total market price in gold pieces (must cover all runes)
- damage: weapon damage dice as NdM (e.g. "1d8"); empty string for non-weapons
- damage_type: e.g. "slashing", "fire"; empty string for non-weapons
- potency_rune: 0-3 (+1 needs item level 2+, +2 needs 10+, +3 needs 16+)
- striking_rune: 0-3 (striking needs level 4+, greater 12+, major 19+; requires potency 1+)
- property_runes: array of strings (each requires potency 1+)
- traits: array of strings (e.g. ["magical", "evocation"])
- rarity: one of common, uncommon, rare, unique
- description: one-sentence flavor plus mechanics

Rules:
- Damage dice count must equal 1 + striking_rune for weapons
- Rune prices: +1 potency 35gp, +2 935gp, +3 8975gp; striking 65gp, greater striking 1065gp, major striking 31000gp
- price_gp must be >= the sum of all etched rune prices
"""


class LootGeneratorAgent:
    def __init__(self, llm: OllamaClient, lawyer: Any):
        self._llm = llm
        self._lawyer = lawyer
        self._settings = get_settings()

    async def build(self, prompt: str) -> LootBuildResult:
        full_prompt = SYSTEM_PROMPT + "\n\nUser request: " + prompt.strip()
        try:
            raw = await self._llm.generate(
                prompt=full_prompt,
                model=self._settings.ollama_model,
                temperature=0.4,
                num_predict=700,
            )
        except Exception as e:
            logger.error(f"LootGenerator LLM failed: {e}")
            return LootBuildResult(False, None, None, "", [f"LLM generation failed: {e}"])

        data = self._extract_json(raw)
        if data is None:
            return LootBuildResult(False, None, None, "", ["LLM returned no valid JSON object"])

        try:
            item = LootItemModel.model_validate(data)
        except Exception as e:
            logger.warning(f"LootGenerator schema validation failed: {e}")
            return LootBuildResult(False, None, None, "", [f"Schema validation failed: {e}"])

        errors = self._validate_crafting(item)
        if errors:
            logger.info(f"LootGenerator validation failed: {errors}")
            return LootBuildResult(False, None, None, "", errors)

        dc = await self._lawyer.calculate_dc(item.level, item.rarity)
        return LootBuildResult(True, item, dc.dc, dc.breakdown, [])

    def _extract_json(self, text: str) -> dict | None:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    def _validate_crafting(self, item: LootItemModel) -> list[str]:
        errors: list[str] = []

        potency_min, potency_price = POTENCY_RUNES[item.potency_rune]
        if item.level < potency_min:
            errors.append(
                f"Potency +{item.potency_rune} needs item level {potency_min}+ (got {item.level})"
            )

        striking_min, striking_price = STRIKING_RUNES[item.striking_rune]
        if item.level < striking_min:
            errors.append(
                f"Striking rank {item.striking_rune} needs item level {striking_min}+ (got {item.level})"
            )
        if item.striking_rune > 0 and item.potency_rune < 1:
            errors.append("Striking runes require a potency rune (+1 or better)")

        if item.property_runes and item.potency_rune < 1:
            errors.append("Property runes require a potency rune (+1 or better)")

        rune_floor = potency_price + striking_price
        if item.price_gp < rune_floor:
            errors.append(
                f"Price {item.price_gp}gp below rune floor {rune_floor}gp "
                f"(potency {potency_price}gp + striking {striking_price}gp)"
            )

        if item.item_type == "weapon":
            match = DAMAGE_RE.match(item.damage or "")
            if not match:
                errors.append(f"Weapon needs damage dice like '1d8' (got '{item.damage}')")
            else:
                dice_count = int(match.group(1))
                expected = 1 + item.striking_rune
                if dice_count != expected:
                    errors.append(
                        f"Damage {item.damage} has {dice_count} dice, "
                        f"striking rank {item.striking_rune} needs {expected}"
                    )
        elif item.damage:
            if not DAMAGE_RE.match(item.damage):
                errors.append(f"Damage '{item.damage}' is not NdM notation")

        return errors
