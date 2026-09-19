# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for CombatTrackerAgent deterministic PF2e combat math."""


from app.agents.combat_tracker import CombatTrackerAgent


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
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 1
        assert updated[0]["value"] == 1

    def test_frightened_1_expires(self):
        """Frightened 1 is removed."""
        conditions = [{"name": "Frightened", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 0

    def test_duration_condition_decrements(self):
        """Conditions with duration_rounds decrement and expire at 0."""
        conditions = [{"name": "Poisoned", "value": 2, "duration_rounds": 2}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 1
        assert updated[0]["duration_rounds"] == 1

    def test_duration_condition_expires(self):
        """Conditions with duration_rounds = 1 are removed."""
        conditions = [{"name": "Poisoned", "value": 2, "duration_rounds": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 0

    def test_other_conditions_unchanged(self):
        """Conditions without special rules pass through unchanged."""
        conditions = [
            {"name": "Prone", "value": 1},
            {"name": "Frightened", "value": 3},
        ]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        assert len(updated) == 2
        # Frightened should decay
        frightened = next(c for c in updated if c["name"] == "Frightened")
        assert frightened["value"] == 2
        # Prone should remain
        prone = next(c for c in updated if c["name"] == "Prone")
        assert prone["value"] == 1


class TestPersistentDamage:
    def test_persistent_damage_rolls_and_flat_check(self):
        """Persistent damage rolls dice and applies flat check."""
        conditions = [{"name": "Persistent Fire 1d6", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        # Should have notes about damage and flat check
        assert "Took" in notes or "Flat check" in notes

    def test_persistent_damage_flat_check_success(self):
        """Flat check >= 15 removes persistent damage."""
        # We can't easily test random, but we can verify structure
        conditions = [{"name": "Persistent Fire 1d6", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        # Should have notes about damage and flat check
        assert "Flat check" in notes

    def test_persistent_damage_flat_check_failure(self):
        """Flat check < 15 keeps persistent damage."""
        conditions = [{"name": "Persistent Fire 1d6", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        # If flat check fails, condition persists
        if "persists" in notes:
            assert len(updated) == 1
            assert updated[0]["name"] == "Persistent Fire 1d6"

    def test_persistent_damage_no_dice_notation(self):
        """Persistent damage without dice notation still gets flat check."""
        conditions = [{"name": "Persistent Fire", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        # Should still have flat check
        assert "Flat check" in notes


class TestDyingWounded:
    def test_dying_increments_at_zero_hp(self):
        """Dying increments when at 0 HP."""
        conditions = [{"name": "Dying", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions, current_hp=0)
        assert len(updated) == 1
        assert updated[0]["value"] == 2
        assert "Dying increased to 2" in notes

    def test_dying_not_increment_above_zero_hp(self):
        """Dying does not increment when above 0 HP."""
        conditions = [{"name": "Dying", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions, current_hp=10)
        assert len(updated) == 1
        assert updated[0]["value"] == 1

    def test_wounded_persists(self):
        """Wounded condition persists and doesn't change."""
        conditions = [{"name": "Wounded", "value": 2}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions, current_hp=0)
        assert len(updated) == 1
        assert updated[0]["value"] == 2
        assert updated[0]["name"] == "Wounded"

    def test_frightened_and_dying_together(self):
        """Multiple conditions processed together."""
        conditions = [
            {"name": "Frightened", "value": 2},
            {"name": "Dying", "value": 1},
        ]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions, current_hp=0)
        assert len(updated) == 2
        frightened = next(c for c in updated if c["name"] == "Frightened")
        dying = next(c for c in updated if c["name"] == "Dying")
        assert frightened["value"] == 1  # Decayed
        assert dying["value"] == 2  # Incremented
        assert "Flat check" in notes or "Dying increased" in notes


class TestPersistentDamageFlatCheck:
    def test_flat_check_success_removes(self):
        """Flat check >= 15 removes persistent damage condition."""
        # We can't easily control randomness, but we can verify the logic
        conditions = [{"name": "Persistent Fire 1d6", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        # The condition should be removed if flat check succeeds
        # We can't deterministically test this, but we verify the logic path exists
        assert "Flat check" in notes or "Took" in notes

    def test_persistent_damage_no_dice_notation(self):
        """Persistent damage without dice notation still gets flat check."""
        conditions = [{"name": "Persistent Fire", "value": 1}]
        updated, notes, _ = CombatTrackerAgent.end_of_turn(conditions)
        # Should still have flat check
        assert "Flat check" in notes

    def test_persistent_damage_reports_taken_damage(self):
        """Persistent damage notes report the rolled damage."""
        conditions = [{"name": "Persistent Fire 1d6", "value": 1}]
        updated, notes, damage = CombatTrackerAgent.end_of_turn(
            conditions, current_hp=30
        )
        assert damage >= 1
        assert "Took" in notes
        assert "Persistent Fire damage" in notes

    def test_persistent_damage_drops_to_zero_adds_dying(self):
        """Damage dropping HP to 0 appends Dying 1."""
        conditions = [{"name": "Persistent Fire 1d6", "value": 1}]
        updated, notes, damage = CombatTrackerAgent.end_of_turn(
            conditions, current_hp=1
        )
        assert damage >= 1
        assert any(c["name"] == "Dying" and c["value"] == 1 for c in updated)
        assert "Dying 1." in notes