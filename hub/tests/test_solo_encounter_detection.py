# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Deterministic turn-action encounter detection for the solo loop.

These tests cover the Slice 1 boundary: a plain campaign turn like "I open
the door" creates and activates the encounter through the campaign
repository, without a REST route or an LLM decision. Instant trap attempts
still roll through the shared skill-check dice stream. Synthetic names only;
the LLM is faked and no Ollama is contacted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.solo_loop import SoloLoop, detect_encounter_action
from app.api.campaign import TurnResponse
from app.db.repository import CampaignRepository

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
    """Small prompt-marker fake; fail=True simulates Ollama being down."""

    def __init__(self, *, fail: bool = False, outcome: dict | None = None):
        self.fail = fail
        self.outcome = outcome if outcome is not None else OUTCOME_JSON

    async def generate(self, prompt: str = "", **kwargs):
        if self.fail:
            raise RuntimeError("Ollama down")
        if "SOLO TURN OUTCOME" in prompt:
            return json.dumps(self.outcome)
        return "SAMPLE NARRATION. What do you do?"

    async def close(self) -> None:
        return None


def _setup(tmp_path: Path, *, llm: FakeLLM | None = None):
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town = repo.upsert_location(campaign.id, "SAMPLE TOWN", type_="settlement")
    repo.set_current_location(campaign.id, town)
    loop = SoloLoop(repo, llm=llm if llm is not None else FakeLLM())
    return repo, campaign, town, loop


# ── Pure detection ────────────────────────────────────────────

@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("I open the door", ("door", "door")),
        ("I knock on the door", ("door", "door")),
        ("I enter the portal", ("door", "portal")),
        ("I open the chest", ("loot", "chest")),
        ("I search the chest", ("loot", "chest")),
        ("I pry the coffer", ("loot", "coffer")),
        ("I searched the chest", ("loot", "chest")),
        ("I disarm the trap", ("trap", "trap")),
        ("I step on the tripwire", ("trap", "tripwire")),
        ("I am stepping on the tripwire", ("trap", "tripwire")),
        ("I talk to the merchant", ("npc", "merchant")),
        ("I greet SAMPLE MERCHANT", ("npc", "SAMPLE MERCHANT")),
        ("I ask the guard about the gate", ("npc", "guard")),
        ("I am talking to the merchant", ("npc", "merchant")),
    ],
)
def test_detect_encounter_action_maps_verbs(action, expected) -> None:
    assert detect_encounter_action(action) == expected


@pytest.mark.parametrize(
    "action",
    [
        "I look around",
        "I search the room",
        "I attack the goblin",
        "I rest for the night",
        "I ask a question",
        "I move to the cave",
    ],
)
def test_detect_encounter_action_ignores_plain_actions(action) -> None:
    assert detect_encounter_action(action) is None


# ── Turn integration ──────────────────────────────────────────

async def test_turn_creates_and_activates_door_encounter(tmp_path: Path) -> None:
    repo, campaign, town, loop = _setup(tmp_path)

    result = await loop.take_turn(campaign.id, "I open the door", seed=7)

    assert result.encounter is not None
    assert result.encounter["kind"] == "door"
    assert result.encounter["status"] == "active"
    assert result.encounter["location_id"] == town
    assert result.to_dict()["encounter"] == result.encounter
    assert repo.get_active_encounter(campaign.id).id == result.encounter["id"]
    events = repo.list_events(
        campaign.id, encounter_id=result.encounter["id"]
    )
    assert [event.kind for event in events] == [
        "encounter_created",
        "encounter_transition",
    ]


async def test_turn_keeps_door_pending_when_battle_is_active(
    tmp_path: Path,
) -> None:
    repo, campaign, _town, loop = _setup(
        tmp_path, llm=FakeLLM(fail=True)
    )
    battle = repo.create_encounter(
        campaign.id, "battle", status="active", summary="SAMPLE BATTLE"
    )

    result = await loop.take_turn(campaign.id, "I open the door", seed=8)

    assert result.encounter is not None
    assert result.encounter["kind"] == "door"
    assert result.encounter["status"] == "pending"
    assert repo.get_active_encounter(campaign.id).id == battle.id
    assert "pending" in result.narration.lower()


async def test_instant_trap_resolves_without_the_active_slot(
    tmp_path: Path,
) -> None:
    repo, campaign, _town, loop = _setup(tmp_path)

    result = await loop.take_turn(campaign.id, "I disarm the trap", seed=1)

    assert result.encounter is not None
    assert result.encounter["kind"] == "trap"
    assert result.encounter["status"] in {"resolved", "failed"}
    assert repo.get_active_encounter(campaign.id) is None
    assert len(result.dice_rolls) == 1
    assert result.dice_rolls[0]["notation"] == "d20"
    kinds = [
        event.kind
        for event in repo.list_events(
            campaign.id, encounter_id=result.encounter["id"]
        )
    ]
    assert kinds[0] == "encounter_created"
    assert "hazard_resolved" in kinds


async def test_multi_turn_trap_activates_and_is_reused(tmp_path: Path) -> None:
    repo, campaign, _town, loop = _setup(tmp_path)

    first = await loop.take_turn(
        campaign.id, "I begin disarming the trap", seed=2
    )
    assert first.encounter is not None
    assert first.encounter["status"] == "active"
    assert first.dice_rolls == []

    second = await loop.take_turn(
        campaign.id, "I continue disarming the trap", seed=3
    )
    assert second.encounter is not None
    assert second.encounter["id"] == first.encounter["id"]
    assert second.encounter["status"] == "active"
    assert len(repo.list_encounters(campaign.id)) == 1


async def test_npc_detection_links_a_known_combatant(tmp_path: Path) -> None:
    repo, campaign, _town, loop = _setup(tmp_path)
    repo.upsert_combatant(
        campaign.id,
        "SAMPLE MERCHANT",
        kind="npc",
        hp=10,
        max_hp=10,
    )

    result = await loop.take_turn(
        campaign.id, "I talk to the merchant", seed=4
    )

    assert result.encounter is not None
    assert result.encounter["kind"] == "npc"
    assert result.encounter["state"]["npc_name"] == "SAMPLE MERCHANT"
    assert result.encounter["state"]["target"] == "SAMPLE MERCHANT"


async def test_search_loot_still_runs_the_skill_check(tmp_path: Path) -> None:
    repo, campaign, _town, loop = _setup(tmp_path)

    result = await loop.take_turn(campaign.id, "I search the chest", seed=5)

    assert result.encounter is not None
    assert result.encounter["kind"] == "loot"
    assert result.encounter["status"] == "active"
    # Detection runs first, then the normal "search" skill resolution still
    # rolls exactly one d20.
    assert len(result.dice_rolls) == 1


async def test_encounter_is_surfaced_as_a_stream_event(tmp_path: Path) -> None:
    _repo, campaign, _town, loop = _setup(tmp_path)
    events: list[dict] = []

    async def collect(event: dict) -> None:
        events.append(event)

    result = await loop.take_turn(
        campaign.id, "I open the door", seed=6, emit=collect
    )

    encounter_events = [
        event for event in events if event.get("type") == "encounter"
    ]
    assert encounter_events
    assert encounter_events[0]["encounter"]["kind"] == "door"
    assert encounter_events[0]["encounter"]["id"] == result.encounter["id"]
    end_events = [event for event in events if event.get("type") == "end"]
    assert end_events
    assert end_events[0]["result"]["encounter"]["kind"] == "door"


async def test_no_match_leaves_the_turn_unchanged(tmp_path: Path) -> None:
    repo, campaign, _town, loop = _setup(tmp_path)

    result = await loop.take_turn(campaign.id, "I look around", seed=9)

    assert result.encounter is None
    assert repo.list_encounters(campaign.id) == []


async def test_narration_includes_the_encounter_note(tmp_path: Path) -> None:
    _repo, campaign, _town, loop = _setup(
        tmp_path, llm=FakeLLM(fail=True)
    )

    result = await loop.take_turn(campaign.id, "I open the door", seed=10)

    assert "Door encounter active" in result.narration


async def test_llm_refinement_reruns_detection(
    tmp_path: Path, monkeypatch
) -> None:
    import app.agents.solo_loop as solo_loop_module

    calls: list[str] = []

    def fake_detect(action: str):
        calls.append(action)
        if len(calls) == 1:
            return None
        return "loot", "chest"

    monkeypatch.setattr(
        solo_loop_module, "detect_encounter_action", fake_detect
    )
    _repo, campaign, _town, loop = _setup(
        tmp_path, llm=FakeLLM(outcome={"kind": "skill"})
    )

    result = await loop.take_turn(
        campaign.id, "I examine the coffer", seed=11
    )

    assert len(calls) == 2
    assert result.encounter is not None
    assert result.encounter["kind"] == "loot"


def test_turn_response_exposes_the_encounter_field() -> None:
    assert "encounter" in TurnResponse.model_fields
