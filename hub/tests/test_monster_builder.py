# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for MonsterBuilderAgent (LLM + Pydantic + PF2e sanity checks).

A boss is the same builder with the elite template, not a separate file.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.monster_builder import MonsterBuilderAgent

VALID_MONSTER = {
    "name": "SAMPLE GRAVEHOUND",
    "level": 5,
    "creature_type": "undead",
    "traits": ["undead", "evil"],
    "hp": 60,
    "ac": 21,
    "perception": 10,
    "saves": {"fortitude": 10, "reflex": 8, "will": 11},
    "strikes": [
        {"name": "Jaws", "attack_bonus": 12, "damage": "1d8+4", "damage_type": "piercing"}
    ],
    "abilities": ["Grave Chill"],
    "tactics": "It stalks the party through the fog, then lunges.",
    "loot_table": ["Cracked soul gem"],
}


class _SeqFakeLlm:
    def __init__(self, payloads: list[str]):
        self._payloads = list(payloads)
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        idx = min(self.calls - 1, len(self._payloads) - 1)
        return self._payloads[idx]


def _agent(payloads) -> MonsterBuilderAgent:
    return MonsterBuilderAgent(_SeqFakeLlm(payloads))


class TestMonsterBuild:
    @pytest.mark.asyncio
    async def test_valid_monster(self):
        result = await _agent([json.dumps(VALID_MONSTER)]).build("undead hound")
        assert result.valid is True
        assert result.attempts == 1
        monster = result.monster
        assert monster is not None
        assert monster.name == "SAMPLE GRAVEHOUND"
        assert monster.level == 5
        assert monster.hp == 60
        assert monster.strikes[0].damage == "1d8+4"

    @pytest.mark.asyncio
    async def test_garbage_then_valid_retries(self):
        agent = _agent(["not json", json.dumps(VALID_MONSTER)])
        result = await agent.build("undead hound")
        assert result.valid is True
        assert result.attempts == 2
        assert result.monster is not None

    @pytest.mark.asyncio
    async def test_implausible_hp_rejected(self):
        bad = dict(VALID_MONSTER, hp=9999)
        result = await _agent([json.dumps(bad)]).build("undead hound")
        assert result.valid is False
        assert result.attempts == 3
        assert any("HP 9999" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_implausible_ac_rejected(self):
        bad = dict(VALID_MONSTER, ac=50)
        result = await _agent([json.dumps(bad)]).build("undead hound")
        assert result.valid is False
        assert any("AC 50" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_out_of_range_level_rejected(self):
        bad = dict(VALID_MONSTER, level=25)
        result = await _agent([json.dumps(bad)]).build("undead hound")
        assert result.valid is False

    @pytest.mark.asyncio
    async def test_bad_damage_dice_rejected(self):
        bad = dict(
            VALID_MONSTER,
            strikes=[{"name": "Jaws", "attack_bonus": 12, "damage": "2d3", "damage_type": "piercing"}],
        )
        result = await _agent([json.dumps(bad)]).build("undead hound")
        assert result.valid is False
        assert any("d3" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_requested_level_mismatch_rejected(self):
        result = await _agent([json.dumps(VALID_MONSTER)]).build("undead hound", level=3)
        assert result.valid is False
        assert any("Requested level 3" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_boss_elite_flag(self):
        result = await _agent([json.dumps(VALID_MONSTER)]).build(
            "undead hound", level=5, elite=True
        )
        assert result.valid is True
        monster = result.monster
        assert monster is not None
        assert monster.template == "elite"
        assert monster.ac == VALID_MONSTER["ac"] + 2
        assert monster.hp == int(VALID_MONSTER["hp"] * 1.2)
        assert monster.saves.fortitude == VALID_MONSTER["saves"]["fortitude"] + 2
        assert monster.strikes[0].attack_bonus == 12 + 2
        assert monster.strikes[0].damage == "1d8+6"

    @pytest.mark.asyncio
    async def test_llm_supplied_template_is_rejected(self):
        bad = dict(VALID_MONSTER, template="elite")
        result = await _agent([json.dumps(bad)]).build("undead hound", level=5)
        assert result.valid is False
        assert any("template 'normal'" in e for e in result.errors)


class TestMonsterEndpoints:
    def _client(self, tmp_path: Path, monkeypatch):
        from app.llm.ollama_client import OllamaClient
        from app.main import create_app

        async def fake_generate(self, **kwargs):
            return json.dumps(VALID_MONSTER)

        monkeypatch.setattr(OllamaClient, "generate", fake_generate)
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_generate_monster_endpoint(self, tmp_path: Path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        r = client.post("/generate/monster", json={"prompt": "undead hound", "level": 5})
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["valid"] is True
        assert body["monster"]["name"] == "SAMPLE GRAVEHOUND"
        assert body["monster"]["template"] == "normal"

    def test_generate_boss_endpoint_applies_elite(self, tmp_path: Path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        r = client.post("/generate/boss/statblock", json={"prompt": "undead hound", "level": 5})
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["valid"] is True
        assert body["monster"]["template"] == "elite"
        assert body["monster"]["ac"] == VALID_MONSTER["ac"] + 2
        assert body["monster"]["strikes"][0]["damage"] == "1d8+6"
