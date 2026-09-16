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