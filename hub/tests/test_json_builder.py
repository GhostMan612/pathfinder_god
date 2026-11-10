# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for the shared JSON retry helper (app.agents.json_builder)."""

import json

import pytest

from app.agents.json_builder import generate_validated_json


class _SeqFakeLlm:
    """Fake LLM returning a scripted sequence of replies (then repeating the last)."""

    def __init__(self, payloads: list[str]):
        self._payloads = list(payloads)
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        idx = min(self.calls - 1, len(self._payloads) - 1)
        return self._payloads[idx]


class _RaisingLlm:
    def __init__(self, failures: int = 99):
        self._failures = failures
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        if self.calls <= self._failures:
            raise RuntimeError("connection refused")
        return json.dumps({"ok": True})


def _no_validate(data):
    return []


class TestJsonBuilder:
    @pytest.mark.asyncio
    async def test_valid_first_try(self):
        llm = _SeqFakeLlm([json.dumps({"name": "SAMPLE"})])
        outcome = await generate_validated_json(
            llm, prompt="p", model="m", temperature=0.3, num_predict=100, validate=_no_validate
        )
        assert outcome.data == {"name": "SAMPLE"}
        assert outcome.attempts == 1
        assert outcome.errors == []

    @pytest.mark.asyncio
    async def test_garbage_then_valid_retries(self):
        llm = _SeqFakeLlm(["Behold! No JSON here.", json.dumps({"name": "SAMPLE"})])
        outcome = await generate_validated_json(
            llm, prompt="p", model="m", temperature=0.3, num_predict=100, validate=_no_validate
        )
        assert outcome.data == {"name": "SAMPLE"}
        assert outcome.attempts == 2
        assert any("no valid JSON" in e for e in outcome.errors)

    @pytest.mark.asyncio
    async def test_validation_error_fed_back_then_valid(self):
        def _validate(data):
            if data.get("level") != 3:
                return ["level must be 3"]
            return []

        llm = _SeqFakeLlm([json.dumps({"level": 9}), json.dumps({"level": 3})])
        outcome = await generate_validated_json(
            llm, prompt="p", model="m", temperature=0.3, num_predict=100, validate=_validate
        )
        assert outcome.data == {"level": 3}
        assert outcome.attempts == 2
        assert any("level must be 3" in e for e in outcome.errors)

    @pytest.mark.asyncio
    async def test_llm_exception_retries_then_succeeds(self):
        llm = _RaisingLlm(failures=2)
        outcome = await generate_validated_json(
            llm, prompt="p", model="m", temperature=0.3, num_predict=100, validate=_no_validate
        )
        assert outcome.data == {"ok": True}
        assert outcome.attempts == 3

    @pytest.mark.asyncio
    async def test_all_attempts_fail_returns_none(self):
        llm = _RaisingLlm()
        outcome = await generate_validated_json(
            llm, prompt="p", model="m", temperature=0.3, num_predict=100, validate=_no_validate
        )
        assert outcome.data is None
        assert outcome.attempts == 3
        assert len(outcome.errors) == 3
        assert all("LLM generation failed" in e for e in outcome.errors)


# ──────────────────────────────────────────────────────────────
# Retry integration: character / loot / map builders recover on retry
# ──────────────────────────────────────────────────────────────

VALID_CHARACTER = {
    "name": "Valeros",
    "ancestry": "Human",
    "heritage": "",
    "background": "Guard",
    "character_class": "Fighter",
    "level": 1,
    "abilities": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 12, "cha": 10},
    "proficiencies": {
        "skills": {"athletics": 1, "stealth": 1, "arcana": 1},
        "defenses": {"martialWeapons": 1},
        "classProfs": {},
    },
}


class TestBuilderRetryIntegration:
    @pytest.mark.asyncio
    async def test_character_recovers_after_garbage(self):
        from app.agents.character_builder import CharacterBuilderAgent
        from app.agents.rules_lawyer import RulesLawyerAgent

        llm = _SeqFakeLlm(["not json", json.dumps(VALID_CHARACTER)])
        agent = CharacterBuilderAgent(llm, RulesLawyerAgent(None))
        result = await agent.build("human fighter")
        assert result.valid is True
        assert result.character is not None
        assert result.character.name == "Valeros"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_loot_recovers_after_garbage(self):
        from app.agents.loot_generator import LootGeneratorAgent
        from app.agents.rules_lawyer import RulesLawyerAgent

        valid_loot = {
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
        llm = _SeqFakeLlm(["not json", json.dumps(valid_loot)])

        class _StubLawyer:
            async def calculate_dc(self, level, rarity="common", proficiency="trained"):
                return await RulesLawyerAgent.calculate_dc(None, level, rarity, proficiency)

        agent = LootGeneratorAgent(llm, _StubLawyer())
        result = await agent.build("gothic weapon")
        assert result.valid is True
        assert result.item is not None
        assert result.item.name == "Widow's Caress"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_map_recovers_after_garbage(self):
        from app.agents.map_maker import MapMakerAgent

        layout_json = json.dumps(
            {
                "width": 10,
                "height": 8,
                "rooms": [{"x": 1, "y": 1, "w": 4, "h": 3, "name": "Tavern"}],
                "secret_features": [
                    {"x": 6, "y": 2, "w": 1, "h": 1, "type": "trap", "name": "Pit"}
                ],
            }
        )
        llm = _SeqFakeLlm(["not json", layout_json])
        agent = MapMakerAgent(llm)
        result = await agent.build("A tavern with a pit trap")
        assert result.valid is True
        assert result.layout is not None
        assert result.layout.width == 10
        assert result.attempts == 2
