# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for WorldBuilderAgent (LLM + Pydantic, non-empty/bounded world)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.world_builder import WorldBuilderAgent
from app.db.repository import CampaignRepository

VALID_WORLD = {
    "name": "SAMPLE VALE",
    "premise": "A quiet valley hides a sealed crypt, and three factions want its key.",
    "settlements": [
        {
            "name": "SAMPLE CROSSING",
            "type": "town",
            "population": 800,
            "description": "A market town where the roads meet.",
        }
    ],
    "factions": [
        {
            "name": "SAMPLE WARDENS",
            "goal": "Keep the crypt sealed",
            "attitude": "friendly",
            "relationships": ["Distrust the SAMPLE COINLORDS"],
        }
    ],
    "locations": [
        {
            "name": "SAMPLE CRYPT",
            "type": "dungeon",
            "description": "A sealed crypt beneath the hills.",
        }
    ],
    "quests": [
        {
            "name": "SAMPLE SEAL",
            "giver": "SAMPLE ELDER",
            "objective": "Find the crypt key before the coinlords do",
            "reward": "A warded strongbox",
        }
    ],
    "hooks": ["A courier arrives with a torn map"],
}


class _SeqFakeLlm:
    def __init__(self, payloads: list[str]):
        self._payloads = list(payloads)
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        idx = min(self.calls - 1, len(self._payloads) - 1)
        return self._payloads[idx]


def _agent(payloads) -> WorldBuilderAgent:
    return WorldBuilderAgent(_SeqFakeLlm(payloads))


class TestWorldBuild:
    @pytest.mark.asyncio
    async def test_valid_world(self):
        result = await _agent([json.dumps(VALID_WORLD)]).build("a valley with a sealed crypt")
        assert result.valid is True
        assert result.attempts == 1
        world = result.world
        assert world is not None
        assert world.name == "SAMPLE VALE"
        assert len(world.settlements) == 1
        assert len(world.factions) == 1
        assert len(world.locations) == 1
        assert len(world.quests) == 1

    @pytest.mark.asyncio
    async def test_garbage_then_valid_retries(self):
        agent = _agent(["not json", json.dumps(VALID_WORLD)])
        result = await agent.build("a valley")
        assert result.valid is True
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_empty_settlements_rejected(self):
        bad = dict(VALID_WORLD, settlements=[])
        result = await _agent([json.dumps(bad)]).build("a valley")
        assert result.valid is False
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_empty_quests_rejected(self):
        bad = dict(VALID_WORLD, quests=[])
        result = await _agent([json.dumps(bad)]).build("a valley")
        assert result.valid is False

    @pytest.mark.asyncio
    async def test_missing_premise_rejected(self):
        bad = {k: v for k, v in VALID_WORLD.items() if k != "premise"}
        result = await _agent([json.dumps(bad)]).build("a valley")
        assert result.valid is False


class TestWorldEndpoint:
    def test_generate_world_endpoint_persists(self, tmp_path: Path, monkeypatch):
        from app.api.deps import get_repo
        from app.llm.ollama_client import OllamaClient
        from app.main import create_app

        async def fake_generate(self, **kwargs):
            return json.dumps(VALID_WORLD)

        monkeypatch.setattr(OllamaClient, "generate", fake_generate)
        repo = CampaignRepository(str(tmp_path / "campaign.db"))
        app = create_app()
        app.dependency_overrides[get_repo] = lambda: repo
        try:
            client = TestClient(app, raise_server_exceptions=False)
            r = client.post(
                "/generate/world",
                json={"prompt": "a valley with a sealed crypt", "campaign_id": 3},
            )
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["valid"] is True
        assert body["world"]["name"] == "SAMPLE VALE"
        assert body["persisted"] == {"locations": 2, "quests": 1, "npcs": 0}
        location_names = {loc.name for loc in repo.get_locations(3)}
        assert "SAMPLE CROSSING" in location_names
        assert "SAMPLE CRYPT" in location_names
        assert repo.get_active_quests(3)[0].name == "SAMPLE SEAL"
        assert repo.get_locations(1) == []
