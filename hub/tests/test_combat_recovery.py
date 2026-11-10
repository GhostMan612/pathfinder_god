# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for the combat tracker gaps closed by the solo loop work:
Dying-4 death threshold, PF2e Remaster recovery checks, and Wounded
modifying the Dying value when it is gained.
"""
from __future__ import annotations

from app.agents.combat_tracker import (
    CombatTrackerAgent,
    dying_value,
    gain_dying,
    wounded_value,
)

recovery_check = CombatTrackerAgent.recovery_check


def test_recovery_check_success_reduces_dying_by_one():
    result = recovery_check(dying=2, roll=15)  # DC 12, margin +3
    assert result.outcome == "Success"
    assert result.dying == 1
    assert result.dead is False
    assert result.stabilized is False
    assert result.dc == 12


def test_recovery_check_critical_success_reduces_by_two_and_stabilizes():
    result = recovery_check(dying=2, roll=20)  # natural 20: critical success
    assert result.outcome == "Critical Success"
    assert result.dying == 0
    assert result.stabilized is True
    assert result.dead is False


def test_recovery_check_natural_20_is_critical_success():
    # DC 10 + 3 = 13; a 20 would be a plain success on margin alone.
    result = recovery_check(dying=3, roll=20)
    assert result.outcome == "Critical Success"
    assert result.dying == 1


def test_recovery_check_failure_increases_dying_by_one():
    result = recovery_check(dying=1, roll=5)  # DC 11
    assert result.outcome == "Failure"
    assert result.dying == 2
    assert result.dead is False


def test_recovery_check_critical_failure_increases_by_two_and_can_kill():
    result = recovery_check(dying=2, roll=1)  # natural 1
    assert result.outcome == "Critical Failure"
    assert result.dying == 4
    assert result.dead is True


def test_recovery_check_failure_to_dying_4_is_death():
    result = recovery_check(dying=3, roll=2)  # DC 13, margin -11
    assert result.dying == 4
    assert result.dead is True


def test_end_of_turn_dying_4_marks_dead():
    conditions, notes, damage = CombatTrackerAgent.end_of_turn(
        [{"name": "Dying", "value": 3}], current_hp=0
    )
    assert dying_value(conditions) == 4
    assert any(c["name"] == "Dead" for c in conditions)
    assert "dead" in notes.lower()


def test_end_of_turn_dying_increments_while_at_zero_hp():
    conditions, notes, _ = CombatTrackerAgent.end_of_turn(
        [{"name": "Dying", "value": 1}], current_hp=0
    )
    assert dying_value(conditions) == 2
    assert not any(c["name"] == "Dead" for c in conditions)


def test_end_of_turn_dying_does_not_increment_above_zero_hp():
    conditions, _, _ = CombatTrackerAgent.end_of_turn(
        [{"name": "Dying", "value": 1}], current_hp=5
    )
    assert dying_value(conditions) == 1


def test_gain_dying_uses_wounded_plus_one():
    conditions, dead = gain_dying([{"name": "Wounded", "value": 2}])
    assert dying_value(conditions) == 3
    assert dead is False


def test_gain_dying_wounded_caps_at_four_and_kills():
    conditions, dead = gain_dying([{"name": "Wounded", "value": 3}])
    assert dying_value(conditions) == 4
    assert dead is True


def test_gain_dying_without_wounded_starts_at_one():
    conditions, dead = gain_dying([])
    assert dying_value(conditions) == 1
    assert dead is False


class _SeqRng:
    """Deterministic RNG returning a fixed sequence of randint values."""

    def __init__(self, values):
        self._values = list(values)

    def randint(self, a, b):
        return self._values.pop(0)


def test_end_of_turn_new_dying_uses_wounded_value():
    # Persistent damage drops the creature to 0 HP; it is Wounded 2, so the
    # Dying it gains is 3, not 1. The sequenced RNG rolls 6 damage and a
    # flat check of 1 (fail), so the damage always lands.
    conditions, notes, damage = CombatTrackerAgent.end_of_turn(
        [
            {"name": "Wounded", "value": 2},
            {"name": "Persistent Fire 1d6", "value": 6},
        ],
        current_hp=3,
        rng=_SeqRng([6, 1]),
    )
    assert damage == 3
    assert dying_value(conditions) == 3


def test_wounded_value_helper():
    assert wounded_value([{"name": "Wounded", "value": 2}]) == 2
    assert wounded_value([{"name": "Frightened", "value": 1}]) == 0
    assert dying_value([{"name": "Dying", "value": 2}]) == 2
