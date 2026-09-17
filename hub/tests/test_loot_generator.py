# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for LootGeneratorAgent deterministic PF2e crafting validation."""

import json

import pytest

from app.agents.loot_generator import LootGeneratorAgent
from app.agents.rules_lawyer import RulesLawyerAgent


VALID_LOOT = {
    "name": "Widow's Caress",
    "item_type": "weapon",
    "level": 4,
    "price_gp": 150,
    "damage": "2d8",
    "damage_type": "slashing",
    "potency_rune": 1,
    "striking_rune": 1,
    "property_runes": [],
    "traits": ["magical", "evocation"],
    "rarity": "common",
    "description": "A gothic shotel that weeps cold mist.",
}


class _FakeLlm:
    def __init__(self, payload: str):
        self._payload = payload

    async def generate(self, **kwargs):
        return self._payload


class _StubLawyer:
    async def calculate_dc(self, level, rarity="common", proficiency="trained"):
        return await RulesLawyerAgent.calculate_dc(None, level, rarity, proficiency)


def _agent(payload: dict | str) -> LootGeneratorAgent:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return LootGeneratorAgent(_FakeLlm(raw), _StubLawyer())


class TestValidLoot:
    @pytest.mark.asyncio
    async def test_valid_gothic_weapon(self):
        result = await _agent(VALID_LOOT).build("gothic weapon for level 4 alchemist")
        assert result.valid is True
        assert result.item is not None
        assert result.item.name == "Widow's Caress"
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_craft_dc_matches_level_table(self):
        result = await _agent(VALID_LOOT).build("gothic weapon")
        expected = await RulesLawyerAgent.calculate_dc(None, 4, "common")
        assert result.craft_dc == expected.dc
        assert "Level 4" in result.craft_dc_breakdown


class TestRuneValidation:
    @pytest.mark.asyncio
    async def test_potency_above_level_rejected(self):
        bad = dict(VALID_LOOT, potency_rune=3)
        result = await _agent(bad).build("overpowered loot")
        assert result.valid is False
        assert any("Potency +3" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_striking_without_potency_rejected(self):
        bad = dict(VALID_LOOT, potency_rune=0)
        result = await _agent(bad).build("striking without potency")
        assert result.valid is False
        assert any("potency rune" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_property_without_potency_rejected(self):
        bad = dict(VALID_LOOT, potency_rune=0, striking_rune=0, damage="1d8", property_runes=["flaming"])
        result = await _agent(bad).build("flaming blade, no potency")
        assert result.valid is False
        assert any("Property runes" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_price_below_rune_floor_rejected(self):
        bad = dict(VALID_LOOT, price_gp=10)
        result = await _agent(bad).build("too cheap")
        assert result.valid is False
        assert any("rune floor 100gp" in e for e in result.errors)


class TestDamageScaling:
    @pytest.mark.asyncio
    async def test_dice_count_must_match_striking(self):
        bad = dict(VALID_LOOT, damage="1d8")
        result = await _agent(bad).build("wrong dice")
        assert result.valid is False
        assert any("striking rank 1 needs 2" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_greater_striking_needs_three_dice(self):
        bad = dict(
            VALID_LOOT,
            level=12,
            potency_rune=2,
            striking_rune=2,
            damage="2d8",
            price_gp=2500,
        )
        result = await _agent(bad).build("greater striking miscount")
        assert result.valid is False
        assert any("needs 3" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_non_weapon_skips_dice_scaling(self):
        trinket = dict(
            VALID_LOOT,
            item_type="treasure",
            damage="",
            damage_type="",
            potency_rune=0,
            striking_rune=0,
            price_gp=50,
        )
        result = await _agent(trinket).build("a jeweled idol")
        assert result.valid is True


class TestMalformedLlm:
    @pytest.mark.asyncio
    async def test_garbage_rejected(self):
        result = await _agent("Behold! No JSON here.").build("loot me")
        assert result.valid is False
        assert any("no valid JSON" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_out_of_range_level_rejected(self):
        bad = dict(VALID_LOOT, level=25)
        result = await _agent(bad).build("godslayer")
        assert result.valid is False
