# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for EncounterBuilderAgent deterministic PF2e XP math."""

import pytest

from app.agents.encounter_builder import (
    EncounterBuilderAgent,
    THREAT_BUDGET_4,
    THREAT_ADJ_PER_PLAYER,
    CREATURE_XP_BY_LEVEL_DIFF,
)

from app.llm.ollama_client import OllamaClient
from app.rag.retriever import Retriever
from app.db.repository import CampaignRepository


class TestXPBudgetMath:
    def test_base_budgets(self):
        """Base XP budgets for 4 players match PF2e Remaster tables."""
        assert THREAT_BUDGET_4["trivial"] == 40
        assert THREAT_BUDGET_4["low"] == 60
        assert THREAT_BUDGET_4["moderate"] == 80
        assert THREAT_BUDGET_4["severe"] == 120
        assert THREAT_BUDGET_4["extreme"] == 160

    def test_player_adjustments(self):
        """Per-player adjustments match tables."""
        assert THREAT_ADJ_PER_PLAYER["trivial"] == 10
        assert THREAT_ADJ_PER_PLAYER["low"] == 15
        assert THREAT_ADJ_PER_PLAYER["moderate"] == 20
        assert THREAT_ADJ_PER_PLAYER["severe"] == 30
        assert THREAT_ADJ_PER_PLAYER["extreme"] == 40

    def test_budget_calculation_4_players(self):
        """4-player party uses base budget."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.calculate_budget(1, 4, "trivial") == 40
        assert agent.calculate_budget(5, 4, "low") == 60
        assert agent.calculate_budget(10, 4, "moderate") == 80
        assert agent.calculate_budget(15, 4, "severe") == 120
        assert agent.calculate_budget(20, 4, "extreme") == 160

    def test_budget_calculation_5_players(self):
        """5 players adds one adjustment."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.calculate_budget(1, 5, "moderate") == 80 + 20  # 100
        assert agent.calculate_budget(5, 5, "severe") == 120 + 30  # 150
        assert agent.calculate_budget(10, 5, "extreme") == 160 + 40  # 200

    def test_budget_calculation_3_players(self):
        """3 players subtracts one adjustment."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.calculate_budget(1, 3, "moderate") == 80 - 20  # 60
        assert agent.calculate_budget(5, 3, "severe") == 120 - 30  # 90

    def test_budget_calculation_6_players(self):
        """6 players adds two adjustments."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.calculate_budget(1, 6, "moderate") == 80 + 40  # 120

    def test_budget_invalid_threat_raises(self):
        """Invalid threat raises ValueError."""
        agent = EncounterBuilderAgent(None, None)
        with pytest.raises(ValueError):
            agent.calculate_budget(1, 4, "impossible")


class TestCreatureXP:
    def test_level_diff_table(self):
        """Creature XP by level difference matches table."""
        assert CREATURE_XP_BY_LEVEL_DIFF[-4] == 10
        assert CREATURE_XP_BY_LEVEL_DIFF[-3] == 15
        assert CREATURE_XP_BY_LEVEL_DIFF[-2] == 20
        assert CREATURE_XP_BY_LEVEL_DIFF[-1] == 30
        assert CREATURE_XP_BY_LEVEL_DIFF[0] == 40
        assert CREATURE_XP_BY_LEVEL_DIFF[1] == 60
        assert CREATURE_XP_BY_LEVEL_DIFF[2] == 80
        assert CREATURE_XP_BY_LEVEL_DIFF[3] == 120
        assert CREATURE_XP_BY_LEVEL_DIFF[4] == 160

    def test_creature_xp_at_party_level(self):
        """Creature at PL costs 40 XP."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.creature_xp(5, 5) == 40
        assert agent.creature_xp(10, 10) == 40

    def test_creature_xp_below_party_level(self):
        """Creatures below PL cost less."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.creature_xp(5, 4) == 30   # PL-1
        assert agent.creature_xp(5, 3) == 20   # PL-2
        assert agent.creature_xp(5, 2) == 15   # PL-3
        assert agent.creature_xp(5, 1) == 10   # PL-4
        assert agent.creature_xp(5, 0) == 10   # PL-5 clamped to -4

    def test_creature_xp_above_party_level(self):
        """Creatures above PL cost more."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.creature_xp(5, 6) == 60   # PL+1
        assert agent.creature_xp(5, 7) == 80   # PL+2
        assert agent.creature_xp(5, 8) == 120  # PL+3
        assert agent.creature_xp(5, 9) == 160  # PL+4
        assert agent.creature_xp(5, 10) == 160 # PL+5 clamped to +4

    def test_creature_xp_extreme_levels(self):
        """Extreme level differences clamp to table bounds."""
        agent = EncounterBuilderAgent(None, None)
        assert agent.creature_xp(1, 20) == 160  # PL+19 clamped to +4
        assert agent.creature_xp(20, 1) == 10   # PL-19 clamped to -4


class TestEncounterBuilderAgent:
    def test_calculate_budget_delegates(self):
        """Agent delegates to calculate_budget."""
        from app.agents.encounter_builder import EncounterBuilderAgent
        from app.llm.ollama_client import OllamaClient
        from app.rag.retriever import Retriever
        from app.db.repository import CampaignRepository

        # This is a structural test - just verify the agent can be instantiated
        # with proper dependencies
        agent = EncounterBuilderAgent(
            llm=OllamaClient("http://test"),
            retriever=Retriever(CampaignRepository()),
        )
        assert agent.calculate_budget(5, 4, "moderate") == 80
        assert agent.calculate_budget(5, 5, "moderate") == 100
        assert agent.calculate_budget(5, 3, "moderate") == 60

    def test_creature_xp_delegates(self):
        """Agent delegates to creature_xp."""
        from app.agents.encounter_builder import EncounterBuilderAgent
        from app.llm.ollama_client import OllamaClient
        from app.rag.retriever import Retriever
        from app.db.repository import CampaignRepository

        agent = EncounterBuilderAgent(
            llm=OllamaClient("http://test"),
            retriever=Retriever(CampaignRepository()),
        )
        assert agent.creature_xp(5, 5) == 40
        assert agent.creature_xp(5, 6) == 60
        assert agent.creature_xp(5, 4) == 30


class TestEliteWeakTemplates:
    def _agent(self):
        from app.agents.encounter_builder import EncounterBuilderAgent
        return EncounterBuilderAgent(None, None)

    def test_elite_raises_stats(self):
        """Elite: +2 AC/saves/strikes/damage, HP x1.2."""
        adj = self._agent().apply_template(
            level=3, ac=18, saves=9, strikes=12, hp=45, template="elite"
        )
        assert adj.ac == 20
        assert adj.saves == 11
        assert adj.strikes == 14
        assert adj.damage_bonus == 2
        assert adj.hp == 54
        assert adj.level == 3
        assert adj.template == "elite"

    def test_weak_lowers_stats(self):
        """Weak: -2 AC/saves/strikes/damage, HP x0.8."""
        adj = self._agent().apply_template(
            level=3, ac=18, saves=9, strikes=12, hp=45, template="weak"
        )
        assert adj.ac == 16
        assert adj.saves == 7
        assert adj.strikes == 10
        assert adj.damage_bonus == -2
        assert adj.hp == 36
        assert adj.template == "weak"

    def test_normal_is_identity(self):
        """Normal template leaves stats untouched."""
        adj = self._agent().apply_template(
            level=3, ac=18, saves=9, strikes=12, hp=45, template="normal"
        )
        assert (adj.ac, adj.saves, adj.strikes, adj.damage_bonus, adj.hp) == (
            18, 9, 12, 0, 45,
        )

    def test_weak_hp_floor_is_one(self):
        """Weak HP never drops below 1."""
        adj = self._agent().apply_template(
            level=1, ac=15, saves=5, strikes=6, hp=1, template="weak"
        )
        assert adj.hp == 1

    def test_unknown_template_raises(self):
        """Unknown template names are rejected."""
        with pytest.raises(ValueError):
            self._agent().apply_template(
                level=1, ac=15, saves=5, strikes=6, hp=10, template="mythic"
            )

    def test_level_bumps_for_xp(self):
        """Elite counts +1 level, weak -1, normal +0 for XP."""
        agent = self._agent()
        assert agent.template_level_bump("elite") == 1
        assert agent.template_level_bump("weak") == -1
        assert agent.template_level_bump("normal") == 0
        with pytest.raises(ValueError):
            agent.template_level_bump("mythic")


class TestDynamicHp:
    def _agent(self):
        from app.agents.encounter_builder import EncounterBuilderAgent
        return EncounterBuilderAgent(None, None)

    def test_static_hp_extracted(self):
        """Plain 'HP 45' stat blocks parse directly."""
        assert self._agent().extract_hp("Goblin Warrior Creature 1, HP 45, AC 15") == 45

    def test_missing_hp_returns_none(self):
        """Content without HP yields None."""
        assert self._agent().extract_hp("A mysterious fog with no stats") is None

    def test_hit_dice_detected(self):
        """Parenthesized and bare dice notations are found."""
        agent = self._agent()
        assert agent.extract_hit_dice("Ogre HP 10d8+20, AC 14") == "10d8+20"
        assert agent.extract_hit_dice("Ooze HP 45 (6d8+18), AC 12") == "6d8+18"
        assert agent.extract_hit_dice("Goblin HP 45, AC 15") is None

    def test_roll_hp_prefers_dice(self):
        """Dice notation is rolled; ranges stay sane."""
        hp = self._agent().roll_hp("Ogre HP 10d8+20, AC 14")
        assert hp is not None
        assert 30 <= hp <= 100

    def test_roll_hp_deterministic_notation(self):
        """1d1+5 always rolls 6."""
        assert self._agent().roll_hp("Wisp HP 1d1+5, AC 10") == 6

    def test_roll_hp_falls_back_to_static(self):
        """No dice notation returns the static HP."""
        assert self._agent().roll_hp("Goblin HP 45, AC 15") == 45

    def test_roll_hp_missing_returns_none(self):
        """No HP anywhere returns None."""
        assert self._agent().roll_hp("A mysterious fog") is None


class _FakeRetriever:
    def __init__(self, hits):
        self._hits = hits

    async def search(self, query, edition="2e", limit=100):
        return self._hits


class _FakeLlm:
    def __init__(self, payload):
        self._payload = payload

    async def generate(self, **kwargs):
        return self._payload


def _goblin_hit():
    return {
        "name": "Goblin Warrior",
        "system": "2e",
        "content": "Goblin Warrior Creature 1, HP 1d1+5, AC 15. Melee shortsword +6 (1d6).",
        "source_book": "Bestiary",
    }


class TestBuildTemplateWiring:
    @pytest.mark.asyncio
    async def test_build_rolls_hp_and_tags_template(self):
        """Build hydrates rolled HP and the requested template."""
        from app.agents.encounter_builder import EncounterBuilderAgent
        agent = EncounterBuilderAgent(
            _FakeLlm('[{"name": "Goblin Warrior", "count": 1}]'),
            _FakeRetriever([_goblin_hit()]),
        )
        result = await agent.build(
            party_level=1, party_size=4, threat="low",
            theme="goblin", template="elite",
        )
        assert len(result.monsters) == 1
        monster = result.monsters[0]
        assert monster.template == "elite"
        assert monster.hp == 7
        assert monster.xp_each == 60
        assert result.total_xp == 60
        assert result.total_xp == result.target_xp