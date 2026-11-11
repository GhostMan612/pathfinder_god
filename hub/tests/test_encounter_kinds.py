# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Per-kind encounter state shapes and deterministic resolvers.

Phase 1 item 1 gives door, trap, NPC, and loot encounters real state instead
of a generic target string. The lifecycle matrix itself is unchanged; these
tests pin the kind-specific defaults, the second-turn resolution, and the
repository side effects (key lookup, trap damage, NPC disposition, item claim).
Synthetic names only; the LLM is faked.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.agents.solo_loop import SoloLoop
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


def _active_encounter(repo, campaign, town, kind, state):
    return repo.create_encounter(
        campaign.id,
        kind,
        status="active",
        summary=f"SAMPLE {kind.upper()}",
        state=state,
        location_id=town,
    )


# ── Door ──────────────────────────────────────────────────────

async def test_door_state_has_the_v1_shape(tmp_path: Path) -> None:
    _repo, campaign, _town, loop = _setup(tmp_path)

    result = await loop.take_turn(campaign.id, "I open the door", seed=11)

    assert result.encounter is not None
    state = result.encounter["state"]
    assert state["locked"] is False
    assert state["key"] is None
    assert state["barred"] is False
    assert state["dc"] is None


async def test_locked_door_with_key_resolves_without_a_roll(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_item(
        campaign.id,
        "SAMPLE IRON KEY",
        type_="other",
        location_name="SAMPLE TOWN",
    )
    _active_encounter(
        repo,
        campaign,
        town,
        "door",
        {
            "locked": True,
            "key": "SAMPLE IRON KEY",
            "barred": False,
            "dc": 20,
        },
    )

    result = await loop.take_turn(campaign.id, "I open the door", seed=12)

    assert result.encounter is not None
    assert result.encounter["status"] == "resolved"
    assert result.encounter["state"]["locked"] is False
    assert result.encounter["state"]["barred"] is False
    assert result.dice_rolls == []


async def test_locked_door_without_key_rolls_and_can_fail(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    _active_encounter(
        repo,
        campaign,
        town,
        "door",
        {"locked": True, "key": None, "barred": False, "dc": 100},
    )

    result = await loop.take_turn(campaign.id, "I open the door", seed=13)

    assert result.encounter is not None
    assert result.encounter["status"] == "failed"
    assert result.encounter["state"]["locked"] is True
    assert result.dice_rolls[0]["notation"] == "d20"


async def test_locked_door_key_can_come_from_party_equipment(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_party_member(
        campaign.id,
        "SAMPLE HERO",
        stats={"equipment": [{"name": "SAMPLE BRASS KEY"}]},
    )
    _active_encounter(
        repo,
        campaign,
        town,
        "door",
        {
            "locked": True,
            "key": "SAMPLE BRASS KEY",
            "barred": False,
            "dc": 20,
        },
    )

    result = await loop.take_turn(campaign.id, "I unlock the door", seed=14)

    assert result.encounter is not None
    assert result.encounter["status"] == "resolved"
    assert result.dice_rolls == []


# ── Trap ──────────────────────────────────────────────────────

async def test_instant_trap_failure_rolls_damage_into_hp_changes(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_combatant(
        campaign.id,
        "SAMPLE HERO",
        kind="hero",
        hp=20,
        max_hp=20,
    )
    repo.create_encounter(
        campaign.id,
        "trap",
        status="pending",
        summary="SAMPLE TRAP",
        state={"dc": 100, "damage": "1d6", "armed": True},
        location_id=town,
    )

    result = await loop.take_turn(campaign.id, "I disarm the trap", seed=15)

    assert result.encounter is not None
    assert result.encounter["status"] == "failed"
    assert result.encounter["state"]["armed"] is False
    assert [d["notation"] for d in result.dice_rolls[:2]] == ["d20", "1d6"]
    assert len(result.hp_changes) == 1
    assert result.hp_changes[0]["damage"] >= 1
    hero = repo.get_combatant_by_name(campaign.id, "SAMPLE HERO")
    assert hero is not None
    assert hero.hp < 20


async def test_instant_trap_success_does_not_damage_the_hero(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_combatant(
        campaign.id,
        "SAMPLE HERO",
        kind="hero",
        hp=20,
        max_hp=20,
    )
    repo.create_encounter(
        campaign.id,
        "trap",
        status="pending",
        summary="SAMPLE TRAP",
        state={"dc": 0, "damage": "1d6", "armed": True},
        location_id=town,
    )

    result = await loop.take_turn(campaign.id, "I disarm the trap", seed=16)

    assert result.encounter is not None
    assert result.encounter["status"] == "resolved"
    assert result.encounter["state"]["armed"] is False
    assert result.hp_changes == []


async def test_active_trap_waits_on_begin_but_resolves_on_continue(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    _active_encounter(
        repo,
        campaign,
        town,
        "trap",
        {"dc": 1, "damage": "1d6", "armed": True},
    )

    waiting = await loop.take_turn(
        campaign.id, "I begin disarming the trap", seed=17
    )
    assert waiting.encounter is not None
    assert waiting.encounter["status"] == "active"
    assert waiting.dice_rolls == []

    done = await loop.take_turn(
        campaign.id, "I continue disarming the trap", seed=18
    )
    assert done.encounter is not None
    assert done.encounter["status"] == "resolved"
    assert done.encounter["state"]["armed"] is False
    assert done.dice_rolls[0]["notation"] == "d20"


# ── NPC ───────────────────────────────────────────────────────

async def test_npc_state_links_the_npcs_table_row(tmp_path: Path) -> None:
    repo, campaign, _town, loop = _setup(tmp_path)
    npc_id = repo.upsert_npc(
        campaign.id, "SAMPLE MERCHANT", disposition="wary"
    )

    result = await loop.take_turn(
        campaign.id, "I talk to the merchant", seed=19
    )

    assert result.encounter is not None
    assert result.encounter["status"] == "active"
    state = result.encounter["state"]
    assert state["npc_id"] == npc_id
    assert state["npc_name"] == "SAMPLE MERCHANT"
    assert state["disposition"] == "wary"
    assert state["topic"]
    assert repo.get_npc(campaign.id, "SAMPLE MERCHANT").disposition == "wary"


async def test_friendly_npc_resolution_updates_disposition(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_npc(campaign.id, "SAMPLE MERCHANT", disposition="friendly")
    _active_encounter(
        repo,
        campaign,
        town,
        "npc",
        {
            "npc_id": None,
            "npc_name": "SAMPLE MERCHANT",
            "disposition": "friendly",
            "topic": "trade",
        },
    )

    result = await loop.take_turn(
        campaign.id, "I talk to the merchant", seed=20
    )

    assert result.encounter is not None
    assert result.encounter["status"] == "resolved"
    assert result.encounter["state"]["disposition"] == "friendly"
    assert repo.get_npc(campaign.id, "SAMPLE MERCHANT").disposition == "friendly"


async def test_hostile_npc_resolution_fails_and_persists(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_npc(campaign.id, "SAMPLE GUARD", disposition="hostile")
    _active_encounter(
        repo,
        campaign,
        town,
        "npc",
        {
            "npc_id": None,
            "npc_name": "SAMPLE GUARD",
            "disposition": "hostile",
            "topic": None,
        },
    )

    result = await loop.take_turn(
        campaign.id, "I talk to the guard", seed=21
    )

    assert result.encounter is not None
    assert result.encounter["status"] == "failed"
    assert result.encounter["state"]["disposition"] == "hostile"
    assert repo.get_npc(campaign.id, "SAMPLE GUARD").disposition == "hostile"


async def test_npc_persuasion_rolls_a_check_and_updates_disposition(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_npc(campaign.id, "SAMPLE MERCHANT", disposition="wary")
    _active_encounter(
        repo,
        campaign,
        town,
        "npc",
        {
            "npc_id": None,
            "npc_name": "SAMPLE MERCHANT",
            "disposition": "wary",
            "topic": "trade",
        },
    )

    result = await loop.take_turn(
        campaign.id, "I persuade the merchant", seed=22
    )

    assert result.encounter is not None
    assert result.encounter["status"] in {"resolved", "failed"}
    assert result.dice_rolls[0]["notation"] == "d20"
    npc = repo.get_npc(campaign.id, "SAMPLE MERCHANT")
    assert npc is not None
    assert npc.disposition == result.encounter["state"]["disposition"]


# ── Loot ──────────────────────────────────────────────────────

async def test_loot_state_defaults_and_first_search_activates(
    tmp_path: Path,
) -> None:
    _repo, campaign, _town, loop = _setup(tmp_path)

    result = await loop.take_turn(campaign.id, "I search the chest", seed=23)

    assert result.encounter is not None
    assert result.encounter["status"] == "active"
    assert result.encounter["state"]["items"] == []
    assert result.encounter["state"]["claimed"] is False


async def test_active_loot_claim_inserts_validated_items(
    tmp_path: Path,
) -> None:
    repo, campaign, town, loop = _setup(tmp_path)
    repo.upsert_party_member(campaign.id, "SAMPLE HERO")
    _active_encounter(
        repo,
        campaign,
        town,
        "loot",
        {
            "items": [
                {
                    "name": "SAMPLE SWORD",
                    "item_type": "weapon",
                    "level": 1,
                    "traits": ["magical"],
                    "description": "A sample blade.",
                },
                {
                    "name": "SAMPLE POTION",
                    "item_type": "consumable",
                    "level": 1,
                    "traits": [],
                },
            ],
            "claimed": False,
        },
    )

    result = await loop.take_turn(campaign.id, "I search the chest", seed=24)

    assert result.encounter is not None
    assert result.encounter["status"] == "resolved"
    assert result.encounter["state"]["claimed"] is True
    rows = repo.get_items(campaign.id)
    assert {row["name"] for row in rows} == {"SAMPLE SWORD", "SAMPLE POTION"}
    assert all(row["location_id"] == town for row in rows)
    assert all("Claimed by SAMPLE HERO" in (row["notes"] or "") for row in rows)


async def test_encounter_state_round_trips_through_the_repository(
    tmp_path: Path,
) -> None:
    repo, campaign, town, _loop = _setup(tmp_path)
    authored = {
        "locked": True,
        "key": "SAMPLE IRON KEY",
        "barred": True,
        "dc": 22,
    }
    encounter = repo.create_encounter(
        campaign.id,
        "door",
        status="pending",
        summary="SAMPLE DOOR",
        state=authored,
        location_id=town,
    )

    active = repo.transition_encounter(
        campaign.id, encounter.id, "active", state=authored
    )
    resolved = repo.transition_encounter(
        campaign.id, encounter.id, "resolved", state=authored
    )

    assert active.state == authored
    assert resolved.state == authored
    assert resolved.status == "resolved"
