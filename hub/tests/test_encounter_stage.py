# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Encounter activation attaches the 3D stage scene and emits one WS frame.

The scene is the same deterministic map scene the map generator persists under
``state.map.scene``; activation mirrors it to ``state.scene`` and announces
``type: "encounter_stage"``. No LLM and no second map path are involved.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from app.agents.encounter_stage import stage_scene_for_location
from app.agents.solo_loop import SoloLoop
from app.db.repository import CampaignRepository
from app.llm.orchestrator import LLMOrchestrator

OUTCOME_JSON = {
    "kind": "other",
    "target": None,
    "skill": None,
    "location": None,
    "quest_update": None,
    "narration_hint": "You look around carefully.",
    "choices": ["Look around", "Move on", "Rest a moment"],
}


class FakeLLM:
    async def generate(self, prompt: str = "", **kwargs):
        if "SOLO TURN OUTCOME" in prompt:
            return json.dumps(OUTCOME_JSON)
        return "SAMPLE NARRATION. What do you do?"

    async def close(self) -> None:
        return None


def _setup(tmp_path: Path):
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town = repo.upsert_location(campaign.id, "SAMPLE TOWN", type_="settlement")
    repo.set_current_location(campaign.id, town)
    loop = SoloLoop(repo, llm=FakeLLM())
    return repo, campaign, town, loop


async def test_activation_attaches_scene_to_state(tmp_path: Path) -> None:
    repo, campaign, _town, loop = _setup(tmp_path)

    result = await loop.take_turn(campaign.id, "I open the door", seed=31)

    assert result.encounter is not None
    stored = repo.get_encounter(campaign.id, result.encounter["id"])
    assert stored is not None
    assert isinstance(stored.state["scene"], dict)
    assert stored.state["scene"]["grid"]["w"] >= 1
    assert stored.state["map"]["scene"] == stored.state["scene"]
    assert stored.state["map"]["source"] == "encounter_stage"
    assert result.encounter["state"]["scene"] == stored.state["scene"]


async def test_activation_emits_one_encounter_stage_ws_event(
    tmp_path: Path,
) -> None:
    _repo, campaign, _town, loop = _setup(tmp_path)
    events: list[dict] = []

    async def collect(event: dict) -> None:
        events.append(event)

    result = await loop.take_turn(
        campaign.id, "I open the door", seed=32, emit=collect
    )

    stage_events = [e for e in events if e.get("type") == "encounter_stage"]
    assert len(stage_events) == 1
    stage = stage_events[0]
    assert result.encounter is not None
    assert stage["encounter_id"] == result.encounter["id"]
    assert stage["kind"] == "door"
    assert stage["scene"] == result.encounter["state"]["scene"]


async def test_existing_location_scene_is_reused(tmp_path: Path) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    existing = {
        "grid": {"w": 3, "h": 3, "tile_m": 1.0},
        "heightmap": [],
        "zones": [],
        "props": [],
        "lights": [],
        "fog": None,
        "walkable": [],
        "doors": [],
        "corridors": [],
        "spawn": None,
        "exit": None,
        "tokens": [],
        "connected": True,
    }
    repo.create_encounter(
        campaign.id,
        "loot",
        status="resolved",
        summary="SAMPLE CACHE",
        state={"map": {"scene": existing, "grid": existing["grid"]}},
        location_id=town,
    )

    result = await loop.take_turn(campaign.id, "I open the door", seed=33)

    assert result.encounter is not None
    assert result.encounter["state"]["scene"] == existing


async def test_no_scene_generation_is_deterministic(tmp_path: Path) -> None:
    repo, campaign, town, _loop = _setup(tmp_path)

    first = stage_scene_for_location(repo, campaign.id, town)
    second = stage_scene_for_location(repo, campaign.id, town)

    assert first is not None
    assert first == second
    assert first["grid"] == second["grid"]
    assert first["heightmap"] == second["heightmap"]
    assert first["tokens"] == second["tokens"]


async def test_gm_trigger_returns_a_stage_frame(tmp_path: Path) -> None:
    repo, campaign, _town, _loop = _setup(tmp_path)
    orchestrator = LLMOrchestrator(repo)

    result = await orchestrator.handle_tool_call(
        "trigger_door",
        {
            "summary": "SAMPLE IRON DOOR",
            "state": {"locked": False, "key": None, "barred": False, "dc": None},
        },
        campaign_id=campaign.id,
    )

    assert result["activated"] is True
    stage = result["stage"]
    assert stage is not None
    assert stage["type"] == "encounter_stage"
    assert stage["encounter_id"] == result["encounter"]["id"]
    assert stage["kind"] == "door"
    stored = repo.get_encounter(campaign.id, result["encounter"]["id"])
    assert stored is not None
    assert stored.state["scene"] == stage["scene"]


async def test_transition_tool_attaches_stage_on_pending_to_active(
    tmp_path: Path,
) -> None:
    repo, campaign, town, _loop = _setup(tmp_path)
    encounter = repo.create_encounter(
        campaign.id,
        "npc",
        summary="SAMPLE CONVERSATION",
        state={
            "npc_id": None,
            "npc_name": "SAMPLE MERCHANT",
            "disposition": "wary",
            "topic": None,
        },
        location_id=town,
    )
    orchestrator = LLMOrchestrator(repo)

    result = await orchestrator.handle_tool_call(
        "transition_encounter",
        {"encounter_id": encounter.id, "status": "active"},
        campaign_id=campaign.id,
    )

    assert result["encounter"]["status"] == "active"
    assert result["stage"] is not None
    assert result["stage"]["kind"] == "npc"
    stored = repo.get_encounter(campaign.id, encounter.id)
    assert stored is not None
    assert stored.state["scene"]["grid"]["w"] >= 1


async def test_agentic_chat_queues_the_stage_for_the_stream(
    tmp_path: Path,
) -> None:
    repo, campaign, _town, _loop = _setup(tmp_path)
    orchestrator = LLMOrchestrator(repo)
    orchestrator.ollama.chat = AsyncMock(
        side_effect=[
            {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "trigger_door",
                            "arguments": json.dumps(
                                {"summary": "SAMPLE IRON DOOR"}
                            ),
                        }
                    }
                ],
            },
            {"content": "The iron door waits."},
        ]
    )

    answer = await orchestrator._agentic_chat(
        "SAMPLE DOOR PROMPT",
        "system",
        "SAMPLE DOOR PROMPT",
        "2e",
        [],
        campaign_id=campaign.id,
    )

    assert answer == "The iron door waits."
    stage = orchestrator.take_stage_event()
    assert stage is not None
    assert stage["type"] == "encounter_stage"
    assert stage["kind"] == "door"
    assert orchestrator.take_stage_event() is None


async def test_instant_trap_does_not_emit_a_stage(tmp_path: Path) -> None:
    _repo, campaign, _town, loop = _setup(tmp_path)
    events: list[dict] = []

    async def collect(event: dict) -> None:
        events.append(event)

    result = await loop.take_turn(
        campaign.id, "I disarm the trap", seed=34, emit=collect
    )

    assert result.encounter is not None
    assert result.encounter["status"] in {"resolved", "failed"}
    assert not [e for e in events if e.get("type") == "encounter_stage"]
    assert "scene" not in result.encounter["state"]
