# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Encounter lifecycle tests: transition matrix, persistence, and battle wiring.

These tests use no LLM. The first battle type is exercised through the real
SoloLoop with its deterministic fallback roster, so the state machine is proven
without Ollama or a live model.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.encounter_state import (
    ENCOUNTER_KINDS,
    ENCOUNTER_STATUSES,
    TERMINAL_STATUSES,
    EncounterStateError,
    is_terminal,
    validate_kind,
    validate_status,
    validate_transition,
)
from app.agents.solo_loop import SoloLoop
from app.db.repository import CampaignRepository


def _repo(tmp_path: Path) -> CampaignRepository:
    return CampaignRepository(str(tmp_path / "campaign.db"))


def test_transition_matrix_accepts_only_declared_edges() -> None:
    assert validate_transition("pending", "active") == "active"
    assert validate_transition("pending", "abandoned") == "abandoned"
    assert validate_transition("active", "resolved") == "resolved"
    assert validate_transition("active", "failed") == "failed"
    assert validate_transition("active", "abandoned") == "abandoned"

    for current, target in (
        ("pending", "resolved"),
        ("pending", "failed"),
        ("active", "pending"),
        ("resolved", "active"),
        ("failed", "resolved"),
        ("abandoned", "active"),
    ):
        with pytest.raises(EncounterStateError):
            validate_transition(current, target)

    assert TERMINAL_STATUSES == {"resolved", "failed", "abandoned"}
    assert all(is_terminal(status) for status in TERMINAL_STATUSES)
    assert not is_terminal("pending")
    assert not is_terminal("active")


def test_unknown_kinds_and_statuses_are_rejected() -> None:
    assert validate_kind("battle") == "battle"
    assert validate_status("active") == "active"
    assert set(ENCOUNTER_KINDS) == {"battle", "loot", "door", "trap", "npc"}
    assert set(ENCOUNTER_STATUSES) == {
        "pending",
        "active",
        "resolved",
        "failed",
        "abandoned",
    }
    with pytest.raises(EncounterStateError, match="unknown encounter kind"):
        validate_kind("campaign")
    with pytest.raises(EncounterStateError, match="unknown encounter status"):
        validate_status("running")


def test_repository_round_trips_encounter_state_and_terminal_time(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    encounter = repo.create_encounter(
        campaign.id,
        "battle",
        summary="SAMPLE BATTLE",
        state={"round": 1, "combatant_ids": [3, 4]},
        seed=17,
    )
    assert encounter.status == "pending"
    assert encounter.state == {"round": 1, "combatant_ids": [3, 4]}
    assert repo.get_active_encounter(campaign.id) is None

    active = repo.transition_encounter(
        campaign.id,
        encounter.id,
        "active",
        state={"round": 1, "combatant_ids": [3, 4], "active_combatant_id": 3},
    )
    assert active.status == "active"
    assert active.resolved_at is None
    assert repo.get_active_encounter(campaign.id).id == encounter.id

    resolved = repo.transition_encounter(
        campaign.id, encounter.id, "resolved", summary="SAMPLE VICTORY"
    )
    assert resolved.status == "resolved"
    assert resolved.summary == "SAMPLE VICTORY"
    assert resolved.resolved_at is not None
    assert repo.get_active_encounter(campaign.id) is None

    listed = repo.list_encounters(campaign.id)
    assert [item.id for item in listed] == [encounter.id]
    assert listed[0].status == "resolved"

    with pytest.raises(EncounterStateError):
        repo.transition_encounter(campaign.id, encounter.id, "active")


def test_only_one_active_encounter_per_campaign_is_allowed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    first = repo.create_encounter(campaign.id, "door", status="active")
    assert first.status == "active"

    with pytest.raises(ValueError, match="already has an active encounter"):
        repo.create_encounter(campaign.id, "trap", status="active")

    pending = repo.create_encounter(campaign.id, "loot")
    with pytest.raises(ValueError, match="already has an active encounter"):
        repo.transition_encounter(campaign.id, pending.id, "active")
    # The failed transition is rolled back, not partially applied.
    assert repo.get_encounter(campaign.id, pending.id).status == "pending"
    assert repo.get_active_encounter(campaign.id).id == first.id


async def test_start_combat_creates_an_active_battle_encounter(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    loop = SoloLoop(repo)

    started = await loop.start_combat(campaign.id, seed=3)
    assert started.encounter_id is not None

    encounter = repo.get_encounter(campaign.id, started.encounter_id)
    assert encounter is not None
    assert encounter.kind == "battle"
    assert encounter.status == "active"
    assert encounter.seed == 3
    assert encounter.state["combatant_ids"] == [
        c["id"] for c in started.combatants
    ]
    assert encounter.state["round"] == 1

    state = loop.get_state(campaign.id)
    assert state["active_encounter"]["id"] == started.encounter_id
    assert state["active_encounter"]["kind"] == "battle"


async def test_end_combat_resolves_the_active_battle(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    loop = SoloLoop(repo)
    started = await loop.start_combat(campaign.id, seed=3)

    await loop.end_combat(campaign.id)

    encounter = repo.get_encounter(campaign.id, started.encounter_id)
    assert encounter is not None
    assert encounter.status == "resolved"
    assert encounter.resolved_at is not None
    assert repo.get_active_encounter(campaign.id) is None
    assert loop.get_state(campaign.id)["active_encounter"] is None


async def test_starting_a_new_battle_abandons_the_previous_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    loop = SoloLoop(repo)
    first = await loop.start_combat(campaign.id, seed=3)
    second = await loop.start_combat(campaign.id, seed=4)

    old = repo.get_encounter(campaign.id, first.encounter_id)
    new = repo.get_encounter(campaign.id, second.encounter_id)
    assert old is not None and old.status == "abandoned"
    assert new is not None and new.status == "active"
    assert repo.get_active_encounter(campaign.id).id == second.encounter_id


async def test_victory_resolves_battle_and_returns_to_exploration(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    loop = SoloLoop(repo)
    started = await loop.start_combat(campaign.id, seed=3)

    for combatant in repo.get_combatants(campaign.id):
        if combatant.kind == "monster":
            repo.update_combatant(combatant.id, is_active=False)

    ended = await loop.end_turn(campaign.id)
    assert ended["phase"] == "exploration"
    encounter = repo.get_encounter(campaign.id, started.encounter_id)
    assert encounter is not None
    assert encounter.status == "resolved"
    assert repo.get_active_encounter(campaign.id) is None


async def test_end_turn_keeps_battle_active_while_monsters_remain(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    loop = SoloLoop(repo)
    started = await loop.start_combat(campaign.id, seed=3)

    ended = await loop.end_turn(campaign.id)
    assert ended["phase"] == "combat"
    encounter = repo.get_encounter(campaign.id, started.encounter_id)
    assert encounter is not None and encounter.status == "active"


def test_api_lists_and_fetches_encounters(
    authenticated_client, rules_db_dir: Path
) -> None:
    # Build the campaign directly so this API test never contacts a model.
    # The combat route with no theme/monster names uses the deterministic
    # fallback roster.
    from app.api.deps import get_repo

    get_repo.cache_clear()
    repo = CampaignRepository(str(rules_db_dir / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    cid = campaign.id

    started = authenticated_client.post(
        f"/campaign/{cid}/combat/start", json={"seed": 3}
    )
    assert started.status_code == 200, started.text
    encounter_id = started.json()["encounter_id"]
    assert encounter_id is not None

    state = authenticated_client.get(f"/campaign/{cid}/state")
    assert state.status_code == 200, state.text
    assert state.json()["active_encounter"]["id"] == encounter_id

    listed = authenticated_client.get(f"/campaign/{cid}/encounters")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["encounters"]] == [encounter_id]

    detail = authenticated_client.get(
        f"/campaign/{cid}/encounters/{encounter_id}"
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["kind"] == "battle"
    assert detail.json()["status"] == "active"

    missing = authenticated_client.get(f"/campaign/{cid}/encounters/99999")
    assert missing.status_code == 404
