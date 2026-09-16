# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Combat Tracker Agent — Deterministic PF2e combat resolution.

Provides pure-Python functions for strike resolution and condition management
that mirror the Rules Lawyer tables. No LLM involvement — pure math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StrikeResult:
    outcome: str
    damage_dealt: int
    new_hp: int
    new_temp_hp: int
    notes: str


class CombatTrackerAgent:
    """Deterministic combat resolution per PF2e Remaster."""

    @staticmethod
    def resolve_strike(
        attack_roll: int,
        target_ac: int,
        damage_roll: int,
        target_hp: int,
        target_temp_hp: int = 0,
    ) -> StrikeResult:
        """Resolve a single strike against a target.

        Args:
            attack_roll: The attack roll total (d20 + modifiers).
            target_ac: Target's Armor Class.
            damage_roll: Total damage rolled (before doubling on crit).
            target_hp: Target's current HP.
            target_temp_hp: Target's current temporary HP.

        Returns:
            StrikeResult with outcome, damage dealt, new HP values, and notes.
        """
        margin = attack_roll - target_ac

        if margin >= 10:
            outcome = "Critical Success"
            damage = max(1, damage_roll * 2)
            notes = "Critical hit! Damage doubled."
        elif margin >= 0:
            outcome = "Success"
            damage = max(1, damage_roll)
            notes = "Hit."
        elif margin >= -9:
            outcome = "Failure"
            damage = 0
            notes = "Miss."
        else:
            outcome = "Critical Failure"
            damage = 0
            notes = "Critical miss."

        # Apply damage: temp HP first, then HP
        remaining_temp = target_temp_hp
        remaining_hp = target_hp

        if damage > 0:
            if remaining_temp >= damage:
                remaining_temp -= damage
            else:
                damage -= remaining_temp
                remaining_temp = 0
                remaining_hp = max(0, remaining_hp - damage)

        return StrikeResult(
            outcome=outcome,
            damage_dealt=damage,
            new_hp=remaining_hp,
            new_temp_hp=remaining_temp,
            notes=notes,
        )

    @staticmethod
    def end_of_turn(conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process end-of-turn condition updates per PF2e Remaster.

        - Frightened: value > 1 -> decrement by 1; value == 1 -> remove.
        - Any condition with duration_rounds: decrement; remove if 0.

        Args:
            conditions: List of condition dicts with keys:
                - name (str): Condition name (e.g., "Frightened", "Prone").
                - value (int): Condition value/severity.
                - duration_rounds (int, optional): Remaining rounds.

        Returns:
            Updated list of condition dicts.
        """
        updated = []
        for cond in conditions:
            name = cond.get("name", "")
            value = int(cond.get("value", 1))
            duration = cond.get("duration_rounds")

            # Frightened decays
            if name.lower() == "frightened":
                if value > 1:
                    value -= 1
                else:
                    # Frightened 1 expires
                    continue

            # Duration-based conditions
            if duration is not None:
                duration = int(duration) - 1
                if duration <= 0:
                    continue
                cond["duration_rounds"] = duration

            cond["value"] = value
            updated.append(cond)

        return updated