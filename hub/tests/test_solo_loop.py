# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for the solo campaign loop: create campaign, turns, combat
lifecycle, quest completion, and the LLM-down fallback. Synthetic names
only; the LLM is always faked — no Ollama is contacted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.solo_loop import SoloLoop, classify_action
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
    started = await loop.start_combat(cid, monster_names=["SAMPLE GOBLIN"], seed=3)
    first_active = started.active_combatant
    advanced = await loop.end_turn(cid)
    assert advanced["phase"] == "combat"
    ended = await loop.end_combat(cid)
    assert ended["phase"] == "exploration"
    assert ended["active_combatant"] is None
    state = loop.repo.get_solo_state(cid)
    assert state.phase == "exploration" and state.active_combatant_id is None


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
