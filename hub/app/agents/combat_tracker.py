# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Combat Tracker Agent — Deterministic PF2e combat resolution.

Provides pure-Python functions for strike resolution and condition management
that mirror the Rules Lawyer tables. No LLM involvement — pure math.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

from app.agents.dice_utils import roll_dice


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
    def end_of_turn(
        conditions: list[dict[str, Any]], current_hp: int = 0
    ) -> tuple[list[dict[str, Any]], str, int]:
        """Process end-of-turn condition updates per PF2e Remaster.

        - Persistent Damage: roll dice, subtract from HP, DC 15 flat check to remove.
        - Dying: increment if at 0 HP; appended at 1 if damage drops HP to 0.
        - Wounded: tracked separately, adds to Dying value.
        - Frightened: value > 1 -> decrement by 1; value == 1 -> remove.
        - Duration-based conditions: decrement; remove if 0.

        Args:
            conditions: List of condition dicts with keys:
                - name (str): Condition name (e.g., "Frightened", "Persistent Fire 1d6").
                - value (int): Condition value/severity.
                - duration_rounds (int, optional): Remaining rounds.
            current_hp: Current HP of the creature (for damage and Dying checks).

        Returns:
            Tuple of (updated conditions list, notes string, damage taken).
        """
        updated = []
        notes_parts = []
        hp = max(0, int(current_hp))

        for cond in conditions:
            name = cond.get("name", "")
            value = int(cond.get("value", 1))
            duration = cond.get("duration_rounds")

            if name.lower().startswith("persistent"):
                display = re.sub(r"\s*\d+d\d+\s*", " ", name).strip() or name
                dice_match = re.search(r"(\d+d\d+)", name)
                if dice_match:
                    total, _, _ = roll_dice(dice_match.group(1))
                    hp = max(0, hp - total)
                    notes_parts.append(f"Took {total} {display} damage.")

                flat_check = random.randint(1, 20)
                if flat_check >= 15:
                    notes_parts.append(f"Flat check {flat_check}: Recovered from {display}.")
                    continue
                else:
                    notes_parts.append(f"Flat check {flat_check}: {display} persists.")

            elif name.lower() == "dying":
                if hp <= 0:
                    value += 1
                    notes_parts.append(f"Dying increased to {value}.")

            elif name.lower() == "wounded":
                pass

            elif name.lower() == "frightened":
                if value > 1:
                    value -= 1
                else:
                    continue

            elif duration is not None:
                duration = int(duration) - 1
                if duration <= 0:
                    continue
                cond["duration_rounds"] = duration

            else:
                pass

            cond["value"] = value
            updated.append(cond)

        damage_taken = max(0, int(current_hp) - hp)
        if damage_taken > 0 and hp <= 0 and not any(
            c.get("name", "").lower() == "dying" for c in updated
        ):
            updated.append({"name": "Dying", "value": 1})
            notes_parts.append("Dying 1.")

        notes = " ".join(notes_parts) if notes_parts else ""
        return updated, notes, damage_taken