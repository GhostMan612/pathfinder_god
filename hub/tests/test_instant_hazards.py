# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Instant-resolution trap carve-out tests.

A one-roll trap resolves from ``pending`` straight to a terminal state without
taking the campaign's single active-encounter slot. Synthetic data only; no
model or Ollama call is made.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.encounter_state import EncounterStateError, validate_transition
from app.db.repository import CampaignRepository


def _repo(tmp_path: Path) -> CampaignRepository:
    return CampaignRepository(str(tmp_path / "campaign.db"))


def _campaign_with_trap(repo: CampaignRepository):
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town = repo.upsert_location(
        campaign.id, "SAMPLE TOWN", type_="settlement"
    )
    repo.set_current_location(campaign.id, town)
    return campaign, town


def test_instant_resolution_is_trap_pending_only() -> None:
    assert (
        validate_transition(
            "pending", "resolved", kind="trap", instant=True
        )
        == "resolved"
    )
    assert (
        validate_transition("pending", "failed", kind="trap", instant=True)
        == "failed"
    )

    with pytest.raises(EncounterStateError, match="requires an encounter kind"):
        validate_transition("pending", "resolved", instant=True)
    with pytest.raises(EncounterStateError, match="not available for 'door'"):
        validate_transition(
            "pending", "resolved", kind="door", instant=True
        )
    with pytest.raises(EncounterStateError, match="only available from"):
        validate_transition(
            "active", "resolved", kind="trap", instant=True
        )
    with pytest.raises(EncounterStateError, match="only available from"):
        validate_transition(
            "pending", "active", kind="trap", instant=True
        )
    # The normal matrix is unchanged when the carve-out is not requested.
    with pytest.raises(EncounterStateError):
        validate_transition("pending", "resolved", kind="trap")


def test_instant_trap_resolves_while_a_battle_is_active(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign, town = _campaign_with_trap(repo)
    battle = repo.create_encounter(
        campaign.id, "battle", status="active", summary="SAMPLE BATTLE"
    )
    trap = repo.create_encounter(
        campaign.id, "trap", summary="SAMPLE TRAP"
    )
    assert trap.location_id == town

    resolved = repo.transition_encounter(
        campaign.id,
        trap.id,
        "resolved",
        summary="SAMPLE TRAP AVOIDED",
        instant=True,
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None
    # The trap never occupied the active slot; the battle still owns it.
    assert repo.get_active_encounter(campaign.id).id == battle.id

    events = repo.list_events(campaign.id, encounter_id=trap.id)
    assert [event.kind for event in events] == [
        "encounter_created",
        "hazard_resolved",
    ]
    assert events[1].data == {
        "kind": "trap",
        "from": "pending",
        "to": "resolved",
        "instant": True,
    }
    assert events[1].location_id == town


def test_trap_cannot_skip_active_without_the_carve_out(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    campaign, _town = _campaign_with_trap(repo)
    trap = repo.create_encounter(campaign.id, "trap")

    with pytest.raises(EncounterStateError):
        repo.transition_encounter(campaign.id, trap.id, "resolved")
    assert repo.get_encounter(campaign.id, trap.id).status == "pending"
    assert [
        event.kind
        for event in repo.list_events(campaign.id, encounter_id=trap.id)
    ] == ["encounter_created"]


def test_instant_trap_api_keeps_the_active_encounter(
    authenticated_client, rules_db_dir: Path
) -> None:
    from app.api.deps import get_repo

    get_repo.cache_clear()
    repo = CampaignRepository(str(rules_db_dir / "campaign.db"))
    campaign, town = _campaign_with_trap(repo)
    battle = repo.create_encounter(campaign.id, "battle", status="active")
    trap = repo.create_encounter(campaign.id, "trap", summary="SAMPLE TRAP")

    denied = authenticated_client.post(
        f"/campaign/{campaign.id}/encounters/{trap.id}/transition",
        json={"status": "resolved"},
    )
    assert denied.status_code == 400, denied.text

    resolved = authenticated_client.post(
        f"/campaign/{campaign.id}/encounters/{trap.id}/transition",
        json={
            "status": "resolved",
            "summary": "SAMPLE TRAP AVOIDED",
            "instant": True,
        },
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["status"] == "resolved"
    assert body["location_id"] == town

    state = authenticated_client.get(f"/campaign/{campaign.id}/state")
    assert state.status_code == 200, state.text
    assert state.json()["active_encounter"]["id"] == battle.id

    events = authenticated_client.get(
        f"/campaign/{campaign.id}/events",
        params={"encounter_id": trap.id},
    )
    assert events.status_code == 200, events.text
    assert [event["kind"] for event in events.json()["events"]] == [
        "encounter_created",
        "hazard_resolved",
    ]

    door = repo.create_encounter(campaign.id, "door")
    rejected = authenticated_client.post(
        f"/campaign/{campaign.id}/encounters/{door.id}/transition",
        json={"status": "resolved", "instant": True},
    )
    assert rejected.status_code == 400, rejected.text
