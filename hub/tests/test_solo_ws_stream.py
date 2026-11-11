# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_repo
from app.config import Settings, get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient

TEST_API_KEY = "pfg_test_key_12345"

WORLD_JSON = {
    "name": "SAMPLE WS WORLD",
    "premise": "A test valley.",
    "settlements": [
        {"name": "SAMPLE WS TOWN", "type": "town", "population": 100, "description": "Town."}
    ],
    "factions": [
        {"name": "SAMPLE WS GUILD", "goal": "Protect town.", "attitude": "friendly", "relationships": []}
    ],
    "locations": [
        {"name": "SAMPLE WS CAVE", "type": "dungeon", "description": "Cave."}
    ],
    "quests": [
        {"name": "Sample WS Quest", "giver": "SAMPLE ELDER", "objective": "Explore cave", "reward": "10 gold"}
    ],
    "hooks": ["A hook."],
}

NPC_JSON = {
    "name": "SAMPLE WS HERO",
    "level": 1,
    "ancestry": "Human",
    "heritage": None,
    "background": "Warrior",
    "class": "Fighter",
    "key_ability": "str",
    "ability_scores": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
    "skills": [{"name": "Athletics", "rank": "trained", "modifier": 5}],
    "feats": [{"name": "Sudden Charge", "level": 1, "type": "class"}],
    "formulas": [],
    "equipment": [{"name": "Longsword", "quantity": 1, "bulk": "1"}],
    "personality": "Brave.",
    "hooks": ["Glory."],
}

MONSTER_JSON = {
    "name": "SAMPLE WS GOBLIN",
    "level": 1,
    "creature_type": "humanoid",
    "traits": ["goblin"],
    "hp": 12,
    "ac": 14,
    "perception": 5,
    "saves": {"fortitude": 4, "reflex": 6, "will": 2},
    "strikes": [
        {"name": "Dogslicer", "attack_bonus": 5, "damage": "1d6", "damage_type": "slashing", "damage_bonus": 1}
    ],
    "abilities": [],
    "tactics": "Swarm.",
    "loot_table": ["Coins."],
}

OUTCOME_JSON = {
    "kind": "other",
    "target": None,
    "skill": None,
    "location": None,
    "quest_update": None,
    "narration_hint": "You investigate the surroundings.",
    "choices": ["Look around", "Move on", "Rest a moment"],
}


@pytest.fixture
def ws_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app import main

    async def fake_generate(self, prompt: str = "", **kwargs):
        if "world builder" in prompt:
            return json.dumps(WORLD_JSON)
        if "NPC Compiler" in prompt:
            return json.dumps(NPC_JSON)
        if "monster designer" in prompt:
            return json.dumps(MONSTER_JSON)
        if "SOLO TURN OUTCOME" in prompt:
            return json.dumps(OUTCOME_JSON)
        if "Opening location" in prompt:
            return "You arrive at SAMPLE WS TOWN. The adventure begins."
        return "The shadows shift. What do you do next?"

    async def fake_stream(self, *args, **kwargs):
        yield "Fake stream chunk."

    async def fake_chat(self, *, messages, model=None, tools=None, **kwargs):
        return {"role": "assistant", "content": json.dumps(OUTCOME_JSON), "tool_calls": []}

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)
    monkeypatch.setattr(OllamaClient, "stream", fake_stream)
    monkeypatch.setattr(OllamaClient, "chat", fake_chat)

    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    main.app.dependency_overrides[get_repo] = lambda: repo
    try:
        client = TestClient(main.app)
        client.headers["X-API-Key"] = TEST_API_KEY
        yield client
    finally:
        main.app.dependency_overrides.pop(get_repo, None)


def test_ws_turn_produces_identical_state_to_rest(ws_client: TestClient) -> None:
    res_a = ws_client.post(
        "/campaign/create",
        json={"name": "CAMPAIGN REST", "premise": "Test premise", "hero_prompt": "A fighter"},
    )
    assert res_a.status_code == 200
    cid_rest = res_a.json()["campaign_id"]

    res_b = ws_client.post(
        "/campaign/create",
        json={"name": "CAMPAIGN WS", "premise": "Test premise", "hero_prompt": "A fighter"},
    )
    assert res_b.status_code == 200
    cid_ws = res_b.json()["campaign_id"]

    rest_turn_res = ws_client.post(
        f"/campaign/{cid_rest}/turn",
        json={"action": "I look around carefully", "seed": 42},
    )
    assert rest_turn_res.status_code == 200
    rest_data = rest_turn_res.json()

    events = []
    with ws_client.websocket_connect("/stream", headers={"X-API-Key": TEST_API_KEY}) as ws:
        ws.send_json(
            {
                "type": "turn",
                "campaign_id": cid_ws,
                "action": "I look around carefully",
                "seed": 42,
            }
        )
        while True:
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") in ("end", "error"):
                break

    event_types = [e["type"] for e in events]
    assert "start" in event_types
    assert "conditions" in event_types
    assert "narration" in event_types
    assert "end" in event_types

    end_event = next(e for e in events if e["type"] == "end")
    ws_result = end_event["result"]

    assert ws_result["turn_num"] == rest_data["turn_num"]
    assert ws_result["phase"] == rest_data["phase"]
    assert ws_result["round"] == rest_data["round"]
    assert ws_result["kind"] == rest_data["kind"]
    assert ws_result["seed"] == rest_data["seed"]
    assert ws_result["dice_rolls"] == rest_data["dice_rolls"]
    assert ws_result["hp_changes"] == rest_data["hp_changes"]
    assert ws_result["narration"] == rest_data["narration"]

    narration_chunks = [e["text"] for e in events if e["type"] == "narration"]
    assert "".join(narration_chunks) == ws_result["narration"]

    state_rest = ws_client.get(f"/campaign/{cid_rest}/state").json()
    state_ws = ws_client.get(f"/campaign/{cid_ws}/state").json()

    assert state_rest["phase"] == state_ws["phase"]
    assert state_rest["round"] == state_ws["round"]
    assert len(state_rest["recent_turns"]) == len(state_ws["recent_turns"])
    assert state_rest["recent_turns"][0]["narration"] == state_ws["recent_turns"][0]["narration"]


def test_ws_combat_turn_streams_dice_and_hp(ws_client: TestClient) -> None:
    res = ws_client.post(
        "/campaign/create",
        json={"name": "COMBAT WS", "premise": "Test", "hero_prompt": "Hero"},
    )
    assert res.status_code == 200
    cid = res.json()["campaign_id"]

    start_res = ws_client.post(
        f"/campaign/{cid}/combat/start",
        json={"monster_names": ["SAMPLE WS GOBLIN"], "seed": 7},
    )
    assert start_res.status_code == 200
    assert start_res.json()["phase"] == "combat"

    events = []
    with ws_client.websocket_connect("/stream", headers={"X-API-Key": TEST_API_KEY}) as ws:
        ws.send_json(
            {
                "campaign_id": cid,
                "action": "I strike the SAMPLE WS GOBLIN",
                "seed": 100,
            }
        )
        while True:
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") in ("end", "error"):
                break

    event_types = [e["type"] for e in events]
    assert "start" in event_types
    assert "dice" in event_types
    assert "hp" in event_types
    assert "conditions" in event_types
    assert "narration" in event_types
    assert "end" in event_types

    dice_event = next(e for e in events if e["type"] == "dice")
    assert len(dice_event["dice_rolls"]) > 0

    hp_event = next(e for e in events if e["type"] == "hp")
    assert len(hp_event["hp_changes"]) > 0

    end_event = next(e for e in events if e["type"] == "end")
    assert end_event["result"]["kind"] == "attack"


def test_ws_turn_missing_campaign_returns_error(ws_client: TestClient) -> None:
    events = []
    with ws_client.websocket_connect("/stream", headers={"X-API-Key": TEST_API_KEY}) as ws:
        ws.send_json(
            {
                "type": "turn",
                "campaign_id": 99999,
                "action": "I look around",
            }
        )
        msg = ws.receive_json()
        events.append(msg)

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "no campaign 99999" in events[0]["message"]


def test_ws_turn_auth_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    raw_key = "secret_key_test_123"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

    auth_settings = Settings(
        data_dir=tmp_path,
        campaign_state_path=tmp_path / "campaign_state.json",
        api_key_sha256=hashed_key,
    )
    repo = CampaignRepository(str(tmp_path / "campaign_auth.db"))
    main.app.dependency_overrides[get_repo] = lambda: repo
    main.app.dependency_overrides[get_settings] = lambda: auth_settings
    try:
        client = TestClient(main.app)

        with client.websocket_connect("/stream") as ws:
            ws.send_json(
                {
                    "type": "turn",
                    "campaign_id": 1,
                    "action": "I look around",
                }
            )
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["message"] == "Unauthorized."
    finally:
        main.app.dependency_overrides.pop(get_repo, None)
        main.app.dependency_overrides.pop(get_settings, None)
