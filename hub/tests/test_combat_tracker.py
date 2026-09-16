# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for CombatTrackerAgent deterministic PF2e combat math."""

import pytest

from app.agents.combat_tracker import CombatTrackerAgent, StrikeResult


class TestCombatTrackerAgent:
    def test_critical_success_doubles_damage(self):
        """Margin >= +10 is a critical success with doubled damage."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=25,
            target_ac=15,
            damage_roll=6,
            target_hp=20,
        )
        assert result.outcome == "Critical Success"
        assert result.damage_dealt == 12  # 6 * 2
        assert result.new_hp == 8  # 20 - 12
        assert result.new_temp_hp == 0

    def test_success_normal_damage(self):
        """Margin 0 to +9 is a success with normal damage."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=20,
            target_ac=15,
            damage_roll=6,
            target_hp=20,
        )
        assert result.outcome == "Success"
        assert result.damage_dealt == 6
        assert result.new_hp == 14

    def test_failure_no_damage(self):
        """Margin -1 to -9 is a failure with 0 damage."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=10,
            target_ac=15,
            damage_roll=6,
            target_hp=20,
        )
        assert result.outcome == "Failure"
        assert result.damage_dealt == 0
        assert result.new_hp == 20

    def test_critical_failure_no_damage(self):
        """Margin <= -10 is a critical failure with 0 damage."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=5,
            target_ac=15,
            damage_roll=6,
            target_hp=20,
        )
        assert result.outcome == "Critical Failure"
        assert result.damage_dealt == 0
        assert result.new_hp == 20

    def test_temp_hp_absorbs_damage_first(self):
        """Temp HP absorbs damage before real HP."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=20,
            target_ac=15,
            damage_roll=6,
            target_hp=20,
            target_temp_hp=10,
        )
        assert result.damage_dealt == 6
        assert result.new_temp_hp == 4  # 10 - 6
        assert result.new_hp == 20  # HP unchanged

    def test_temp_hp_exhausted_then_hp(self):
        """When temp HP exhausted, remainder goes to HP."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=20,
            target_ac=15,
            damage_roll=15,
            target_hp=20,
            target_temp_hp=5,
        )
        assert result.damage_dealt == 10  # 15 total, 5 absorbed by temp HP
        assert result.new_temp_hp == 0
        assert result.new_hp == 10  # 20 - (15 - 5)

    def test_critical_success_min_damage_1(self):
        """Critical success with 0 damage roll still deals 1 damage."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=25,
            target_ac=15,
            damage_roll=0,
            target_hp=20,
        )
        assert result.damage_dealt == 1
        assert result.new_hp == 19

    def test_success_min_damage_1(self):
        """Success with 0 damage roll still deals 1 damage."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=20,
            target_ac=15,
            damage_roll=0,
            target_hp=20,
        )
        assert result.damage_dealt == 1

    def test_hp_clamped_at_zero(self):
        """HP never goes below 0."""
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=25,
            target_ac=15,
            damage_roll=50,
            target_hp=10,
        )
        assert result.new_hp == 0


class TestEndOfTurnConditions:
    def test_frightened_decays(self):
        """Frightened > 1 decrements by 1."""
        conditions = [{"name": "Frightened", "value": 2}]
        updated = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 1
        assert updated[0]["value"] == 1

    def test_frightened_1_expires(self):
        """Frightened 1 is removed."""
        conditions = [{"name": "Frightened", "value": 1}]
        updated = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 0

    def test_duration_condition_decrements(self):
        """Conditions with duration_rounds decrement and expire at 0."""
        conditions = [{"name": "Poisoned", "value": 2, "duration_rounds": 2}]
        updated = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 1
        assert updated[0]["duration_rounds"] == 1

    def test_duration_condition_expires(self):
        """Conditions with duration_rounds = 1 are removed."""
        conditions = [{"name": "Poisoned", "value": 2, "duration_rounds": 1}]
        updated = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 0

    def test_other_conditions_unchanged(self):
        """Conditions without special rules pass through unchanged."""
        conditions = [
            {"name": "Prone", "value": 1},
            {"name": "Frightened", "value": 3},
        ]
        updated = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 2
        # Frightened should decay
        frightened = next(c for c in updated if c["name"] == "Frightened")
        assert frightened["value"] == 2
        # Prone should remain
        prone = next(c for c in updated if c["name"] == "Prone")
        assert prone["value"] == 1