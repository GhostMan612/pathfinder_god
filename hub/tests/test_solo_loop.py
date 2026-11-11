# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for the solo campaign loop: create campaign, turns, combat
lifecycle, quest completion, and the LLM-down fallback. Synthetic names
only; the LLM is always faked — no Ollama is contacted.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.solo_loop import (
    SoloLoop,
    _hero_ac_from_stats,
    classify_action,
    hero_default_ac,
)
from app.api.deps import get_repo
from app.main import app
from app.db.repository import CampaignRepository

TEST_API_KEY = "pfg_test_key_12345"

WORLD_JSON = {
    "name": "SAMPLE WORLD",
    "premise": "A quiet valley hides an old evil.",
    "settlements": [
        {"name": "SAMPLE TOWN", "type": "town", "population": 100, "description": "A quiet town."}
    ],
    "factions": [
        {"name": "SAMPLE GUILD", "goal": "Protect the town.", "attitude": "friendly", "relationships": []}
    ],
    "locations": [
        {"name": "SAMPLE CAVE", "type": "dungeon", "description": "A dark cave."}
    ],
    "quests": [
        {"name": "Rescue the Miller", "giver": "SAMPLE ELDER", "objective": "Find the missing miller", "reward": "50 gold"}
    ],
    "hooks": ["A stranger arrives."],
}

NPC_JSON = {
    "name": "SAMPLE HERO",
    "level": 1,
    "ancestry": "Human",
    "heritage": None,
    "background": "Farmer",
    "class": "Fighter",
    "key_ability": "str",
    "ability_scores": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
    "skills": [{"name": "Athletics", "rank": "trained", "modifier": 5}],
    "feats": [{"name": "Sudden Charge", "level": 1, "type": "class"}],
    "formulas": [],
    "equipment": [{"name": "Longsword", "quantity": 1, "bulk": "1"}],
    "personality": "Brave.",
    "hooks": ["Seeks glory."],
}

MONSTER_JSON = {
    "name": "SAMPLE GOBLIN",
    "level": 1,
    "creature_type": "humanoid",
    "traits": ["goblin"],
    "hp": 12,
    "ac": 16,
    "perception": 5,
    "saves": {"fortitude": 4, "reflex": 6, "will": 2},
    "strikes": [
        {"name": "Dogslicer", "attack_bonus": 6, "damage": "1d6", "damage_type": "slashing", "damage_bonus": 1}
    ],
    "abilities": [],
    "tactics": "Swarm.",
    "loot_table": ["A shiny coin."],
}

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
    """Dispatches canned replies by prompt marker; fail=True simulates Ollama down."""

    def __init__(self, *, fail: bool = False, outcome: dict | None = None):
        self.fail = fail
        self.outcome = outcome if outcome is not None else OUTCOME_JSON

    async def generate(self, prompt: str = "", **kwargs):
        if self.fail:
            raise RuntimeError("Ollama down")
        if "world builder" in prompt:
            return json.dumps(WORLD_JSON)
        if "NPC Compiler" in prompt:
            return json.dumps(NPC_JSON)
        if "monster designer" in prompt:
            return json.dumps(MONSTER_JSON)
        if "SOLO TURN OUTCOME" in prompt:
            return json.dumps(self.outcome)
        if "Opening location" in prompt:
            return "You arrive in SAMPLE TOWN as the campaign begins. What do you do?"
        return "The torches flicker as you press on. What do you do?"

    async def close(self):
        return None


def _make_loop(db_path: Path, llm=None) -> SoloLoop:
    repo = CampaignRepository(str(db_path))
    return SoloLoop(repo, llm=llm if llm is not None else FakeLLM())


# ── Classification ────────────────────────────────────────────

def test_classify_action_keywords():
    assert classify_action("I attack the goblin") == "attack"
    assert classify_action("I search the room") == "skill"
    assert classify_action("I move to the cave") == "move"
    assert classify_action("I talk to the elder") == "talk"
    assert classify_action("We rest for the night") == "rest"
    assert classify_action("I look around") == "other"


# ── Campaign creation ─────────────────────────────────────────

async def test_create_campaign_uses_world_and_hero(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    result = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    assert result["campaign_id"] >= 1
    assert result["location"] == "SAMPLE TOWN"
    assert result["quest"] == "Rescue the Miller"
    assert result["hero"] == "SAMPLE HERO"
    assert result["source"] == "llm"
    assert "SAMPLE TOWN" in result["opening_narration"]
    state = loop.repo.get_solo_state(result["campaign_id"])
    assert state is not None and state.phase == "exploration" and state.round_num == 1
    party = loop.repo.get_party(result["campaign_id"])
    assert [p["name"] for p in party] == ["SAMPLE HERO"]
    quests = loop.repo.get_quests(result["campaign_id"])
    assert [q.name for q in quests] == ["Rescue the Miller"]


async def test_create_campaign_llm_down_uses_defaults(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db", llm=FakeLLM(fail=True))
    result = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    # World build failed -> default location + quest; hero fell back to the
    # NPC template (its own marked fallback), so the party is still built.
    assert result["location"] == "Trailhead Village"
    assert result["quest"] == "First Steps"
    assert result["source"] == "fallback"
    assert "Trailhead Village" in result["opening_narration"]
    assert loop.repo.get_party(result["campaign_id"])


# ── Turns ─────────────────────────────────────────────────────

async def test_turn_in_exploration_persists_and_returns_choices(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    cid = created["campaign_id"]
    result = await loop.take_turn(cid, "I look around the town square")
    assert result.turn_num == 1
    assert result.phase == "exploration"
    assert result.location == "SAMPLE TOWN"
    assert len(result.choices) == 3
    assert result.narration
    turns = loop.repo.get_recent_turns(cid)
    assert len(turns) == 1
    assert turns[0].action == "I look around the town square"
    assert turns[0].narration == result.narration


async def test_turn_is_deterministic_for_a_fixed_seed(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    cid = created["campaign_id"]
    first = await loop.take_turn(cid, "I search the room for traps", seed=42)
    # A second, identical campaign replayed with the same seed rolls the same dice.
    loop2 = _make_loop(tmp_path / "campaign2.db")
    created2 = await loop2.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    second = await loop2.take_turn(created2["campaign_id"], "I search the room for traps", seed=42)
    assert first.dice_rolls == second.dice_rolls
    assert first.dice_rolls[0]["notation"] == "d20"


async def test_turn_with_llm_down_still_resolves_deterministically(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db", llm=FakeLLM(fail=True))
    created = await loop.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    cid = created["campaign_id"]
    result = await loop.take_turn(cid, "I search the room for traps", seed=7)
    assert result.source == "fallback"
    assert result.dice_rolls  # dice are code, never the LLM
    assert result.narration  # template narration, not invented dice
    assert result.choices


async def test_turn_on_missing_campaign_raises(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    with pytest.raises(ValueError, match="no campaign 999"):
        await loop.take_turn(999, "I look around")


# ── Combat ────────────────────────────────────────────────────

async def test_start_combat_builds_hero_and_monster_and_initiative(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    started = await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    assert started.phase == "combat"
    assert started.round == 1
    names = [c["name"] for c in started.combatants]
    assert "SAMPLE HERO" in names and "SAMPLE GOBLIN" in names
    goblin = next(c for c in started.combatants if c["name"] == "SAMPLE GOBLIN")
    assert goblin["hp"] == 12 and goblin["ac"] == 16  # from the monster builder, not a guess
    initiatives = [c["initiative"] for c in started.combatants]
    assert initiatives == sorted(initiatives, reverse=True)
    assert started.active_combatant == started.combatants[0]["name"]
    state = loop.repo.get_solo_state(cid)
    assert state.phase == "combat"
    # The legacy mirror is kept current for the spoke.
    assert "SAMPLE GOBLIN" in loop.repo.get_combat_json(cid)


def test_hero_ac_uses_valid_sheet_values_and_safe_fallbacks() -> None:
    assert hero_default_ac(1) == 15
    assert hero_default_ac(5) == 19
    assert _hero_ac_from_stats({"ac": 21}, 5) == 21
    assert _hero_ac_from_stats({"armor_class": 23}, 5) == 23
    assert _hero_ac_from_stats({"derived": {"ac": 25}}, 5) == 25
    assert _hero_ac_from_stats({"derived": '{"armorClass": 27}'}, 5) == 27
    for invalid in (None, True, "21", 0, -1, 999):
        assert _hero_ac_from_stats({"ac": invalid}, 5) == 19
    assert _hero_ac_from_stats({"derived": "{not-json"}, 1) == 15


async def test_authenticated_party_sheet_ac_reaches_combat(
    tmp_path: Path, authenticated_client: TestClient
) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    app.dependency_overrides[get_repo] = lambda: loop.repo
    try:
        response = authenticated_client.post(
            "/campaign/party",
            params={"campaign_id": cid},
            json={
                "name": "SAMPLE SHEET HERO",
                "level": 5,
                "stats": {"derived": {"ac": 24}, "max_hp": 42},
            },
        )
        assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.pop(get_repo, None)
    started = await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    hero = next(c for c in started.combatants if c["name"] == "SAMPLE SHEET HERO")
    assert hero["ac"] == 24 and hero["max_hp"] == 42

    # The next sheet update may correct AC while HP/conditions persist.
    loop.repo.update_combatant(hero["id"], hp=17, conditions=[{"name": "Wounded", "value": 1}])
    loop.repo.upsert_party_member(
        cid, "SAMPLE SHEET HERO", level=5, stats={"derived": {"ac": 28}, "max_hp": 42}
    )
    await loop.end_combat(cid)
    again = await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=4)
    refreshed = next(c for c in again.combatants if c["name"] == "SAMPLE SHEET HERO")
    assert refreshed["ac"] == 28 and refreshed["hp"] == 17
    assert any(condition["name"] == "Wounded" for condition in refreshed["conditions"])


async def test_hero_ac_without_sheet_scales_as_house_default(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    loop.repo.upsert_party_member(cid, "SAMPLE PLAIN HERO", level=5)
    started = await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    heroes = {c["name"]: c for c in started.combatants if c["kind"] == "hero"}
    assert heroes["SAMPLE PLAIN HERO"]["ac"] == 19
    assert heroes["SAMPLE HERO"]["ac"] == 15


async def test_attack_turn_changes_hp_deterministically(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    before = loop.repo.get_combatant_by_name(cid, "SAMPLE GOBLIN")
    assert before is not None and before.hp == 12
    result = await loop.take_turn(cid, "I attack the SAMPLE GOBLIN", seed=42)
    assert result.kind == "attack"
    assert result.hp_changes
    change = result.hp_changes[0]
    assert change["name"] == "SAMPLE GOBLIN"
    assert change["hp"] <= 12
    assert result.dice_rolls[0]["notation"] == "d20"
    after = loop.repo.get_combatant_by_name(cid, "SAMPLE GOBLIN")
    assert after is not None and after.hp == change["hp"]
    # Initiative advanced past the first combatant.
    assert result.active_combatant is not None


async def test_end_turn_advances_and_end_combat_returns_to_exploration(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    advanced = await loop.end_turn(cid)
    assert advanced["phase"] == "combat"
    ended = await loop.end_combat(cid)
    assert ended["phase"] == "exploration"
    assert ended["active_combatant"] is None
    state = loop.repo.get_solo_state(cid)
    assert state.phase == "exploration" and state.active_combatant_id is None


def test_repository_transaction_rolls_back_and_nests(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    # A failure inside rolls the whole unit back.
    with pytest.raises(RuntimeError, match="boom"), repo.transaction():
        repo.upsert_location(campaign.id, "SAMPLE TOWN", type_="settlement")
        raise RuntimeError("boom")
    assert repo.get_locations(campaign.id) == []
    # Success commits.
    with repo.transaction():
        repo.upsert_location(campaign.id, "SAMPLE TOWN", type_="settlement")
    assert [loc.name for loc in repo.get_locations(campaign.id)] == [
        "SAMPLE TOWN"
    ]
    # A nested transaction is a no-op: the outer rollback covers it.
    with pytest.raises(RuntimeError, match="boom"), repo.transaction():
        repo.upsert_location(campaign.id, "SAMPLE CAVE", type_="dungeon")
        with repo.transaction():
            repo.upsert_location(campaign.id, "SAMPLE KEEP", type_="settlement")
        raise RuntimeError("boom")
    assert [loc.name for loc in repo.get_locations(campaign.id)] == [
        "SAMPLE TOWN"
    ]


def test_repository_transactions_are_isolated_between_databases(tmp_path: Path) -> None:
    first = CampaignRepository(str(tmp_path / "first.db"))
    second = CampaignRepository(str(tmp_path / "second.db"))
    first_campaign = first.create_campaign("SAMPLE FIRST CAMPAIGN")
    second_campaign = second.create_campaign("SAMPLE SECOND CAMPAIGN")

    with first.transaction():
        first.upsert_location(first_campaign.id, "SAMPLE FIRST TOWN", type_="settlement")
        # The second repository must not reuse the first repository's
        # transaction connection, even when campaign ids happen to match.
        second.upsert_location(second_campaign.id, "SAMPLE SECOND TOWN", type_="settlement")

    assert [loc.name for loc in first.get_locations(first_campaign.id)] == [
        "SAMPLE FIRST TOWN"
    ]
    assert [loc.name for loc in second.get_locations(second_campaign.id)] == [
        "SAMPLE SECOND TOWN"
    ]


def test_repository_transaction_closes_connection_if_begin_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))

    class FailedBegin:
        closed = False

        def __init__(self) -> None:
            self.row_factory = None

        def execute(self, sql: str) -> None:
            if sql == "BEGIN IMMEDIATE":
                raise sqlite3.OperationalError("database is locked")

        def close(self) -> None:
            self.closed = True

    failed = FailedBegin()
    with monkeypatch.context() as patch:
        patch.setattr("app.db.repository.sqlite3.connect", lambda path: failed)
        with pytest.raises(sqlite3.OperationalError, match="locked"), repo.transaction():
            pytest.fail("transaction should not begin")
    assert failed.closed
    # A failed transaction must not leave a context lease behind.
    assert repo.create_campaign("SAMPLE AFTER FAILURE").name == "SAMPLE AFTER FAILURE"


async def test_repository_transaction_rejects_inherited_child_task(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")

    async def child_read() -> None:
        repo.get_locations(campaign.id)

    with repo.transaction():
        with pytest.raises(RuntimeError, match="different task or thread"):
            await asyncio.create_task(child_read())
        repo.upsert_location(campaign.id, "SAMPLE SAFE TOWN", type_="settlement")

    assert [loc.name for loc in repo.get_locations(campaign.id)] == [
        "SAMPLE SAFE TOWN"
    ]


async def test_start_combat_rolls_back_on_mid_setup_failure(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    first = await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    assert first.phase == "combat"
    first_encounter = loop.repo.get_active_encounter(cid)
    assert first_encounter is not None
    first_names = [c.name for c in loop.repo.get_combatants(cid, active_only=True)]

    # Fail the second start_combat after its writes have begun (the
    # abandon + new encounter + roster clear all happen before the
    # monster add). The whole unit must roll back: the first combat's
    # encounter, roster, and phase must be untouched.
    original_add = loop.repo.add_combatant

    def _failing_add(*args, **kwargs):
        raise RuntimeError("boom")

    loop.repo.add_combatant = _failing_add
    try:
        with pytest.raises(RuntimeError, match="boom"):
            await loop.start_combat(cid, monster_names=["SAMPLE ORC"], seed=4)
    finally:
        loop.repo.add_combatant = original_add

    assert loop.repo.get_solo_state(cid).phase == "combat"
    active = loop.repo.get_active_encounter(cid)
    assert active is not None and active.id == first_encounter.id
    assert [c.name for c in loop.repo.get_combatants(cid, active_only=True)] == first_names


async def test_end_combat_rolls_back_on_failure(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    first_encounter = loop.repo.get_active_encounter(cid)
    assert first_encounter is not None

    original_deactivate = loop.repo.deactivate_combatants

    def _failing_deactivate(*args, **kwargs):
        raise RuntimeError("boom")

    loop.repo.deactivate_combatants = _failing_deactivate
    try:
        with pytest.raises(RuntimeError, match="boom"):
            await loop.end_combat(cid)
    finally:
        loop.repo.deactivate_combatants = original_deactivate

    # The resolve + phase flip happened before the failure, so they must
    # have rolled back too: still in combat, encounter still active.
    assert loop.repo.get_solo_state(cid).phase == "combat"
    active = loop.repo.get_active_encounter(cid)
    assert active is not None and active.id == first_encounter.id


async def test_dying_combatant_recovers_on_their_turn(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    # Force the goblin to Dying 3 at 0 HP and make it the active combatant.
    goblin = loop.repo.get_combatant_by_name(cid, "SAMPLE GOBLIN")
    assert goblin is not None
    loop.repo.update_combatant(
        goblin.id, hp=0, conditions=[{"name": "Dying", "value": 3}]
    )
    loop.repo.update_solo_state(cid, active_combatant_id=goblin.id)
    # Seed 5 rolls a natural 20 on the recovery check: critical success,
    # Dying 3 -> 1 at the start of its turn, then the end-of-turn increment
    # (still at 0 HP) brings it back to 2. Net change proves the recovery
    # ran; a plain success would have netted back to 3.
    result = await loop.take_turn(cid, "I wait and watch", seed=5)
    after = loop.repo.get_combatant_by_name(cid, "SAMPLE GOBLIN")
    assert after is not None
    dying = [c for c in (after.conditions or []) if c["name"] == "Dying"]
    assert dying and dying[0]["value"] == 2
    assert after.is_active is True
    assert result.narration


# ── Quests ────────────────────────────────────────────────────

async def test_quest_objective_completed_by_validated_outcome(tmp_path: Path) -> None:
    outcome = dict(OUTCOME_JSON)
    outcome["quest_update"] = {
        "quest_name": "Rescue the Miller",
        "objective": "Find the missing miller",
        "completed": True,
    }
    loop = _make_loop(tmp_path / "campaign.db", llm=FakeLLM(outcome=outcome))
    created = await loop.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    cid = created["campaign_id"]
    result = await loop.take_turn(cid, "I find the missing miller in the cave")
    assert result.quest_updates
    update = result.quest_updates[0]
    assert update["quest"] == "Rescue the Miller"
    assert update["quest_completed"] is True
    quests = loop.repo.get_quests(cid)
    assert quests[0].status == "completed"


async def test_quest_update_for_unknown_quest_is_ignored(tmp_path: Path) -> None:
    outcome = dict(OUTCOME_JSON)
    outcome["quest_update"] = {
        "quest_name": "Slay the Dragon King",
        "objective": "Find the dragon",
        "completed": True,
    }
    loop = _make_loop(tmp_path / "campaign.db", llm=FakeLLM(outcome=outcome))
    created = await loop.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    cid = created["campaign_id"]
    result = await loop.take_turn(cid, "I slay the dragon king")
    assert result.quest_updates == []
    assert loop.repo.get_quests(cid)[0].status == "active"


# ── Orchestrator tools ────────────────────────────────────────

async def test_orchestrator_roll_dice_and_resolve_strike_tools(rules_db_dir, tmp_path: Path) -> None:
    from app.llm.orchestrator import LLMOrchestrator

    orch = LLMOrchestrator(CampaignRepository(str(tmp_path / "campaign.db")))
    rolled = await orch.handle_tool_call("roll_dice", {"notation": "1d6"}, campaign_id=1)
    assert 1 <= rolled["total"] <= 6
    assert rolled["notation"] == "1d6"
    struck = await orch.handle_tool_call(
        "resolve_strike",
        {"attack_roll": 18, "target_ac": 15, "damage_roll": 5, "target_hp": 10},
        campaign_id=1,
    )
    assert struck["outcome"] == "Success"
    assert struck["new_hp"] == 5


async def test_orchestrator_build_monster_tool_uses_fake_llm(rules_db_dir, tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import AsyncMock

    from app.llm.orchestrator import LLMOrchestrator

    orch = LLMOrchestrator(CampaignRepository(str(tmp_path / "campaign.db")))
    orch.npc_compiler.ollama.generate = AsyncMock(return_value=json.dumps(MONSTER_JSON))
    result = await orch.handle_tool_call(
        "build_monster", {"prompt": "a goblin", "level": 1}, campaign_id=1
    )
    assert result["valid"] is True
    assert result["monster"]["name"] == "SAMPLE GOBLIN"


async def test_stream_build_request_routes_through_tool_loop(rules_db_dir, tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    from app.llm.orchestrator import LLMOrchestrator

    orch = LLMOrchestrator(CampaignRepository(str(tmp_path / "campaign.db")))
    orch.ollama.chat = AsyncMock(
        return_value={"role": "assistant", "content": "Built the goblin.", "tool_calls": []}
    )
    chunks = []
    async for backend, chunk in orch.stream("build me a goblin monster", "2e"):
        chunks.append((backend, chunk))
    assert chunks
    assert "".join(c for _, c in chunks) == "Built the goblin."


# ── API endpoints ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _hermetic_hub(tmp_path: Path, monkeypatch, rules_db_dir: Path):
    import app.config
    from app import main
    from app.api.deps import get_repo
    from app.config import Settings, get_settings
    from app.llm.ollama_client import OllamaClient

    test_settings = Settings(
        data_dir=rules_db_dir,
        campaign_state_path=tmp_path / "campaign_state.json",
    )
    monkeypatch.setattr(app.config, "get_settings", lambda: test_settings)

    async def fake_generate(self, **kwargs):
        return "Fake answer from the God."

    async def fake_stream(self, **kwargs):
        yield "Fake "
        yield "answer."

    async def fake_chat(self, *, messages, model=None, tools=None, **kwargs):
        return {"role": "assistant", "content": "Fake answer.", "tool_calls": []}

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)
    monkeypatch.setattr(OllamaClient, "stream", fake_stream)
    monkeypatch.setattr(OllamaClient, "chat", fake_chat)

    main.app.dependency_overrides[get_repo] = lambda: CampaignRepository(
        str(tmp_path / "campaign.db")
    )
    main.app.dependency_overrides[get_settings] = lambda: test_settings
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(rules_db_dir: Path) -> TestClient:
    from app import main

    client = TestClient(main.app)
    client.headers["X-API-Key"] = TEST_API_KEY
    return client


def test_api_create_turn_state_combat_flow(authenticated_client) -> None:
    r = authenticated_client.post(
        "/campaign/create",
        json={"name": "SAMPLE CAMPAIGN", "premise": "A quiet valley.", "hero_prompt": "a brave human fighter"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body["campaign_id"]
    # LLM is faked to non-JSON here, so the world falls back to defaults.
    assert body["location"] == "Trailhead Village"
    assert body["quest"] == "First Steps"

    r = authenticated_client.post(f"/campaign/{cid}/turn", json={"action": "I look around", "seed": 5})
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["turn_num"] == 1
    assert turn["phase"] == "exploration"
    assert len(turn["choices"]) == 3

    r = authenticated_client.get(f"/campaign/{cid}/state")
    assert r.status_code == 200, r.text
    state = r.json()
    assert state["phase"] == "exploration"
    assert state["recent_turns"][0]["action"] == "I look around"

    r = authenticated_client.post(
        f"/campaign/{cid}/combat/start", json={"monster_names": ["SAMPLE GOBLIN"], "seed": 3}
    )
    assert r.status_code == 200, r.text
    started = r.json()
    assert started["phase"] == "combat"
    assert any(c["name"] == "SAMPLE GOBLIN" for c in started["combatants"])

    r = authenticated_client.post(f"/campaign/{cid}/turn", json={"action": "I attack the SAMPLE GOBLIN", "seed": 42})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "attack"

    r = authenticated_client.post(f"/campaign/{cid}/combat/end")
    assert r.status_code == 200, r.text
    assert r.json()["phase"] == "exploration"


def test_api_turn_on_missing_campaign_is_404(authenticated_client) -> None:
    r = authenticated_client.post("/campaign/999/turn", json={"action": "I look around"})
    assert r.status_code == 404


def test_api_solo_endpoints_require_auth(rules_db_dir: Path) -> None:
    from app import main

    client = TestClient(main.app)
    r = client.post("/campaign/create", json={"name": "SAMPLE CAMPAIGN"})
    assert r.status_code in (401, 403)


# ── Regression tests: seven PR #2 review findings ──────────────
# Each test below pins one of the seven correctness bugs found in the
# review of draft PR #2, so none of them can silently come back.


async def test_duplicate_monster_names_get_separate_rows(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN", "SAMPLE GOBLIN"], seed=3)
    goblins = [c for c in loop.repo.get_combatants(cid) if c.kind == "monster"]
    assert len(goblins) == 2
    assert len({c.id for c in goblins}) == 2
    assert all(c.name == "SAMPLE GOBLIN" and c.hp == 12 for c in goblins)
    # Heroes are still unique by name: one hero row, refreshed not duplicated.
    heroes = [c for c in loop.repo.get_combatants(cid) if c.kind == "hero"]
    assert len(heroes) == 1


async def test_end_combat_deactivates_combatants(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign("SAMPLE CAMPAIGN", premise="A quiet valley.")
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    assert loop.repo.get_combatants(cid, active_only=True)
    ended = await loop.end_combat(cid)
    assert ended["phase"] == "exploration"
    assert loop.repo.get_combatants(cid, active_only=True) == []
    assert all(not c.is_active for c in loop.repo.get_combatants(cid))


async def test_end_turn_and_end_combat_on_missing_campaign_raise(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    with pytest.raises(ValueError, match="no campaign 999"):
        await loop.end_turn(999)
    with pytest.raises(ValueError, match="no campaign 999"):
        await loop.end_combat(999)
    # Nothing was auto-created by the failed calls.
    assert loop.repo.campaign_exists(999) is False


def test_api_end_turn_and_end_combat_on_missing_campaign_are_404(
    authenticated_client,
) -> None:
    r = authenticated_client.post("/campaign/999/combat/end-turn")
    assert r.status_code == 404
    r = authenticated_client.post("/campaign/999/combat/end")
    assert r.status_code == 404


async def test_llm_refined_other_to_attack_actually_resolves(tmp_path: Path) -> None:
    llm = FakeLLM(outcome={**OUTCOME_JSON, "kind": "attack", "target": "SAMPLE GOBLIN"})
    loop = _make_loop(tmp_path / "campaign.db", llm=llm)
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    before = loop.repo.get_combatant_by_name(cid, "SAMPLE GOBLIN")
    assert before is not None and before.hp == 12
    # "stare" classifies as "other": the deterministic pass resolves nothing.
    assert classify_action("I stare at the SAMPLE GOBLIN") == "other"
    result = await loop.take_turn(cid, "I stare at the SAMPLE GOBLIN", seed=42)
    assert result.kind == "attack"
    # The refined attack must actually roll dice and change HP state.
    assert result.dice_rolls and result.dice_rolls[0]["notation"] == "d20"
    assert result.hp_changes
    change = result.hp_changes[0]
    assert change["name"] == "SAMPLE GOBLIN"
    after = loop.repo.get_combatant_by_name(cid, "SAMPLE GOBLIN")
    assert after is not None and after.hp == change["hp"]


async def test_rest_in_exploration_heals_wounded_hero(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    hero = next(c for c in loop.repo.get_combatants(cid) if c.kind == "hero")
    loop.repo.update_combatant(hero.id, hp=5)
    await loop.end_combat(cid)
    result = await loop.take_turn(cid, "I rest and bandage my wounds", seed=7)
    assert result.kind == "rest"
    assert result.hp_changes
    assert result.hp_changes[0]["healed"] > 0
    after = loop.repo.get_combatant(cid, hero.id)
    assert after is not None and after.hp > 5


async def test_rest_before_first_combat_creates_hero_rows(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    assert loop.repo.get_combatants(cid) == []
    result = await loop.take_turn(cid, "We rest for the night", seed=7)
    assert result.kind == "rest"
    # Nobody was wounded, so nothing was healed — and the turn does not
    # claim otherwise.
    assert result.hp_changes == []
    heroes = [c for c in loop.repo.get_combatants(cid) if c.kind == "hero"]
    assert len(heroes) == 1
    assert heroes[0].hp == heroes[0].max_hp


async def test_hero_hp_and_conditions_survive_next_combat(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path / "campaign.db")
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    hero = next(c for c in loop.repo.get_combatants(cid) if c.kind == "hero")
    loop.repo.update_combatant(
        hero.id, hp=5, conditions=[{"name": "Wounded", "value": 1}]
    )
    await loop.end_combat(cid)

    # The next encounter keeps the same hero row rather than deleting it and
    # recreating a full-HP replacement.
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=4)
    heroes = [c for c in loop.repo.get_combatants(cid) if c.kind == "hero"]
    assert len(heroes) == 1
    assert heroes[0].id == hero.id
    assert heroes[0].hp == 5
    assert heroes[0].max_hp == hero.max_hp
    assert heroes[0].conditions == [{"name": "Wounded", "value": 1}]
    assert heroes[0].is_active is True
    # Old monsters are replaced, not accumulated.
    assert len([c for c in loop.repo.get_combatants(cid) if c.kind == "monster"]) == 1


async def test_concurrent_turns_are_serialized(tmp_path: Path) -> None:
    class SlowFakeLLM(FakeLLM):
        def __init__(self) -> None:
            super().__init__()
            self.active = 0
            self.max_active = 0

        async def generate(self, prompt: str = "", **kwargs):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            try:
                await asyncio.sleep(0.01)
                return await super().generate(prompt, **kwargs)
            finally:
                self.active -= 1

    llm = SlowFakeLLM()
    loop = _make_loop(tmp_path / "campaign.db", llm=llm)
    created = await loop.create_campaign(
        "SAMPLE CAMPAIGN", premise="A quiet valley.", hero_prompt="a brave human fighter"
    )
    cid = created["campaign_id"]
    await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)

    first, second = await asyncio.gather(
        loop.take_turn(cid, "I attack the SAMPLE GOBLIN", seed=1),
        loop.take_turn(cid, "I attack the SAMPLE GOBLIN", seed=2),
    )
    assert sorted([first.turn_num, second.turn_num]) == [1, 2]
    assert llm.max_active == 1
    assert len(loop.repo.get_recent_turns(cid)) == 2


def test_encounter_monster_ac_scales_with_level_and_template() -> None:
    from app.agents.solo_loop import _encounter_monster_ac

    assert _encounter_monster_ac(1, "normal") == 13
    assert _encounter_monster_ac(5, "elite") == 19
    assert _encounter_monster_ac(3, "weak") == 13


async def test_encounter_built_monsters_use_level_based_ac(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.agents.encounter_builder import BuildResult, EncounterMonster

    class FakeEncounterAgent:
        def __init__(self, llm, retriever) -> None:
            pass

        async def build(self, *, party_level, party_size, threat, theme):
            return BuildResult(
                target_xp=70,
                total_xp=70,
                monsters=[
                    EncounterMonster(
                        name="SAMPLE WOLF",
                        count=2,
                        level=3,
                        xp_each=30,
                        content="",
                        source_book="",
                        hp=20,
                        template="elite",
                    ),
                    EncounterMonster(
                        name="SAMPLE RAT",
                        count=1,
                        level=1,
                        xp_each=10,
                        content="",
                        source_book="",
                        hp=6,
                        template="weak",
                    ),
                ],
                party_level=party_level,
                party_size=party_size,
                threat=threat,
                theme=theme,
            )

    monkeypatch.setattr(
        "app.agents.encounter_builder.EncounterBuilderAgent", FakeEncounterAgent
    )
    loop = _make_loop(tmp_path / "campaign.db")
    specs = await loop._build_encounter_specs("forest", "moderate", 3, 4)
    by_name: dict[str, list[dict]] = {}
    for spec in specs:
        by_name.setdefault(spec["name"], []).append(spec)
    assert len(specs) == 3
    assert [s["ac"] for s in by_name["SAMPLE WOLF"]] == [17, 17]  # 12 + 3 + 2 elite
    assert by_name["SAMPLE RAT"][0]["ac"] == 11  # 12 + 1 - 2 weak


def test_reserved_turn_numbers_never_collide(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    first = repo.reserve_turn_num(campaign.id)
    second = repo.reserve_turn_num(campaign.id)
    assert (first, second) == (1, 2)
    repo.record_turn(campaign.id, first, "player", "first", "First.")
    repo.record_turn(campaign.id, second, "player", "second", "Second.")
    turns = repo.get_recent_turns(campaign.id)
    assert sorted(t.turn_num for t in turns) == [1, 2]


def test_legacy_db_migrates_combatants_unique_and_turn_counter(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE campaign_turns (id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            turn_num INTEGER NOT NULL, actor TEXT NOT NULL DEFAULT 'player',
            action TEXT NOT NULL, narration TEXT NOT NULL DEFAULT '',
            outcome_json TEXT NOT NULL DEFAULT '{}', dice_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(campaign_id, turn_num));
        CREATE TABLE solo_state (campaign_id INTEGER PRIMARY KEY REFERENCES campaigns(id) ON DELETE CASCADE,
            phase TEXT NOT NULL DEFAULT 'exploration', round_num INTEGER NOT NULL DEFAULT 1,
            current_location_id INTEGER, active_combatant_id INTEGER,
            turn_order_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE combatants (id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            name TEXT NOT NULL, kind TEXT DEFAULT 'monster',
            hp INTEGER NOT NULL DEFAULT 1, max_hp INTEGER NOT NULL DEFAULT 1,
            temp_hp INTEGER NOT NULL DEFAULT 0, ac INTEGER NOT NULL DEFAULT 10,
            initiative INTEGER NOT NULL DEFAULT 0, conditions_json TEXT NOT NULL DEFAULT '[]',
            is_active INTEGER NOT NULL DEFAULT 1, turn_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(campaign_id, name));
        INSERT INTO campaigns (id, name) VALUES (1, 'SAMPLE CAMPAIGN');
        INSERT INTO solo_state (campaign_id) VALUES (1);
        INSERT INTO campaign_turns (campaign_id, turn_num, actor, action, narration)
            VALUES (1, 1, 'player', 'first', 'First.');
        INSERT INTO campaign_turns (campaign_id, turn_num, actor, action, narration)
            VALUES (1, 2, 'player', 'second', 'Second.');
        INSERT INTO combatants (campaign_id, name, kind, hp, max_hp, ac)
            VALUES (1, 'SAMPLE GOBLIN', 'monster', 12, 12, 16);
        """
    )
    conn.commit()
    conn.close()
    repo = CampaignRepository(str(db_path))
    # Duplicate names are now allowed, and the old goblin survived the rebuild.
    first = repo.add_combatant(1, "SAMPLE GOBLIN", hp=12, max_hp=12, ac=16)
    second = repo.add_combatant(1, "SAMPLE GOBLIN", hp=8, max_hp=8, ac=14)
    assert first != second
    goblins = [c for c in repo.get_combatants(1) if c.name == "SAMPLE GOBLIN"]
    assert len(goblins) == 3
    assert sorted(c.hp for c in goblins) == [8, 12, 12]

    # The rebuild must not leave the new table without its index or its
    # updated_at trigger; both originally belonged to the renamed table.
    check = sqlite3.connect(str(db_path))
    try:
        schema_objects = {
            row[0]
            for row in check.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('index', 'trigger') AND tbl_name = 'combatants'"
            )
        }
        assert "idx_combatants_campaign" in schema_objects
        assert "trigger_combatants_updated" in schema_objects
        check.execute(
            "UPDATE combatants SET updated_at = '2000-01-01 00:00:00' WHERE id = ?",
            (first,),
        )
        check.commit()
    finally:
        check.close()
    repo.update_combatant(first, hp=4)
    check = sqlite3.connect(str(db_path))
    try:
        stamp = check.execute(
            "SELECT updated_at FROM combatants WHERE id = ?", (first,)
        ).fetchone()[0]
    finally:
        check.close()
    assert stamp != "2000-01-01 00:00:00"

    # The turn counter was backfilled past the two recorded turns.
    assert repo.reserve_turn_num(1) == 3
    assert repo.reserve_turn_num(1) == 4
