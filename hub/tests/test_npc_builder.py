# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for the rewritten NPCCompilerAgent (LLM + Pydantic, template fallback)."""

import json
from pathlib import Path

import pytest

from app.agents.npc_compiler import (
    NPCCompilerAgent,
    create_npc_tool,
    save_npc_to_db_tool,
)
from app.db.repository import CampaignRepository

VALID_NPC = {
    "name": "SAMPLE MERCHANT",
    "level": 5,
    "ancestry": "Dwarf",
    "heritage": None,
    "background": "Merchant",
    "class": "Alchemist",
    "key_ability": "int",
    "ability_scores": {"str": 12, "dex": 14, "con": 13, "int": 16, "wis": 10, "cha": 8},
    "ac": 20,
    "hp": 45,
    "perception": 12,
    "saves": {"fortitude": 11, "reflex": 12, "will": 9},
    "class_dc": 20,
    "spell_dc": None,
    "skills": [{"name": "Crafting", "rank": "expert", "modifier": 12}],
    "feats": [{"name": "Quick Bomber", "level": 1, "type": "class"}],
    "formulas": ["Lesser Acid Flask"],
    "equipment": [{"name": "Alchemist's Tools", "quantity": 1, "bulk": "2"}],
    "personality": "Gruff, secretly proud of his craft",
    "hooks": ["Needs a rare reagent from the lodge"],
}


class _SeqFakeLlm:
    def __init__(self, payloads: list[str]):
        self._payloads = list(payloads)
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        idx = min(self.calls - 1, len(self._payloads) - 1)
        return self._payloads[idx]


class _RaisingLlm:
    async def generate(self, **kwargs):
        raise RuntimeError("connection refused")


def _agent(payloads, tmp_path: Path) -> NPCCompilerAgent:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    return NPCCompilerAgent(repo, llm=_SeqFakeLlm(payloads))


class TestNpcLlmBuild:
    @pytest.mark.asyncio
    async def test_valid_llm_npc(self, tmp_path: Path):
        agent = _agent([json.dumps(VALID_NPC)], tmp_path)
        result = await agent.build("cranky level 5 Dwarven alchemist shopkeep")
        assert result.valid is True
        assert result.source == "llm"
        assert result.attempts == 1
        npc = result.npc
        assert npc is not None
        assert npc.name == "SAMPLE MERCHANT"
        assert npc.class_ == "Alchemist"
        assert npc.ability_scores["int"] == 16
        assert npc.ac == 20
        assert npc.hp == 45
        assert npc.saves == {"fortitude": 11, "reflex": 12, "will": 9}
        foundry = npc.to_foundry_json()
        assert foundry["system"]["details"]["class"] == "Alchemist"
        assert foundry["system"]["attributes"]["ac"]["value"] == 20
        assert foundry["system"]["saves"]["fortitude"] == 11

    @pytest.mark.asyncio
    async def test_garbage_then_valid_retries(self, tmp_path: Path):
        agent = _agent(["Behold! No JSON here.", json.dumps(VALID_NPC)], tmp_path)
        result = await agent.build("dwarven alchemist")
        assert result.valid is True
        assert result.source == "llm"
        assert result.attempts == 2
        assert result.npc is not None and result.npc.name == "SAMPLE MERCHANT"

    @pytest.mark.asyncio
    async def test_out_of_range_abilities_rejected_then_valid(self, tmp_path: Path):
        bad = dict(VALID_NPC, ability_scores=dict(VALID_NPC["ability_scores"], str=25))
        agent = _agent([json.dumps(bad), json.dumps(VALID_NPC)], tmp_path)
        result = await agent.build("dwarven alchemist")
        assert result.valid is True
        assert result.attempts == 2
        assert result.npc is not None
        assert result.npc.ability_scores["str"] == 12

    @pytest.mark.asyncio
    async def test_bad_rank_rejected(self, tmp_path: Path):
        bad = dict(
            VALID_NPC,
            skills=[{"name": "Crafting", "rank": "godlike", "modifier": 99}],
        )
        agent = _agent([json.dumps(bad)], tmp_path)
        result = await agent.build("dwarven alchemist")
        # Every retry returns the same invalid payload, so the LLM path fails
        # and the clearly-marked template fallback is used instead.
        assert result.source == "fallback"
        assert result.attempts == 3
        assert any("Schema validation failed" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_llm_down_uses_marked_template_fallback(self, tmp_path: Path):
        repo = CampaignRepository(str(tmp_path / "campaign.db"))
        agent = NPCCompilerAgent(repo, llm=_RaisingLlm())
        result = await agent.build("cranky level 5 Dwarven alchemist shopkeep")
        assert result.valid is True
        assert result.source == "fallback"
        assert result.attempts == 3
        assert result.npc is not None
        assert result.npc.ancestry == "Dwarf"
        assert result.npc.class_ == "Alchemist"
        assert "the Alchemist" in result.npc.name
        assert result.npc.ac is not None
        assert result.npc.hp is not None
        assert result.npc.saves is not None
        assert any("fallback" in e for e in result.errors)

        # The deterministic fallback must not pick a random name on each call.
        other = NPCCompilerAgent(repo, llm=_RaisingLlm())
        second = await other.build("cranky level 5 Dwarven alchemist shopkeep")
        assert second.npc is not None
        assert second.npc.name == result.npc.name

    @pytest.mark.asyncio
    async def test_create_npc_tool_returns_both_class_keys(
        self, tmp_path: Path, monkeypatch
    ):
        from app.llm.ollama_client import OllamaClient

        async def fake_generate(self, **kwargs):
            return json.dumps(VALID_NPC)

        monkeypatch.setattr(OllamaClient, "generate", fake_generate)
        repo = CampaignRepository(str(tmp_path / "campaign.db"))
        npc = await create_npc_tool("dwarven alchemist", repo)
        assert npc["class"] == "Alchemist"
        assert npc["class_"] == "Alchemist"
        assert npc["source"] == "llm"

    @pytest.mark.asyncio
    async def test_save_persists_via_repo(self, tmp_path: Path):
        agent = _agent([json.dumps(VALID_NPC)], tmp_path)
        result = await agent.build("dwarven alchemist")
        assert result.npc is not None
        npc_dict = dict(result.npc.__dict__)
        npc_dict["class"] = result.npc.class_
        saved = await save_npc_to_db_tool(npc_dict, agent.repo, campaign_id=5)
        assert saved.get("saved") is True
        npc = agent.repo.get_npc(5, "SAMPLE MERCHANT")
        assert npc is not None
        assert npc.level == 5
        assert npc.class_ == "Alchemist"
        assert agent.repo.get_npc(1, "SAMPLE MERCHANT") is None


class TestNpcEndpoint:
    def test_generate_npc_endpoint_persists(
        self, tmp_path: Path, monkeypatch, authenticated_client
    ):
        from app.api.deps import get_repo
        from app.llm.ollama_client import OllamaClient

        async def fake_generate(self, **kwargs):
            return json.dumps(VALID_NPC)

        monkeypatch.setattr(OllamaClient, "generate", fake_generate)
        repo = CampaignRepository(str(tmp_path / "campaign.db"))
        authenticated_client.app.dependency_overrides[get_repo] = lambda: repo
        try:
            r = authenticated_client.post(
                "/generate/npc",
                json={"concept": "dwarven alchemist shopkeep", "campaign_id": 2},
            )
        finally:
            authenticated_client.app.dependency_overrides.pop(get_repo, None)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["valid"] is True
        assert body["npc"]["name"] == "SAMPLE MERCHANT"
        assert body["npc"]["class"] == "Alchemist"
        assert body["source"] == "llm"
        assert isinstance(body["npc_id"], int)
        assert repo.get_npc(2, "SAMPLE MERCHANT") is not None
        assert repo.get_npc(1, "SAMPLE MERCHANT") is None

    def test_generate_npc_requires_auth(self, client, tmp_path: Path):
        r = client.post(
            "/generate/npc",
            json={"concept": "dwarven alchemist shopkeep", "campaign_id": 2},
        )
        assert r.status_code == 401
