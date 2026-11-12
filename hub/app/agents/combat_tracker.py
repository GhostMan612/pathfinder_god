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


@dataclass
class RecoveryResult:
    """Outcome of a PF2e Remaster recovery check (DC 10 + dying value).

    Degrees of success: critical success (beat the DC by 10+, or a natural
    20) reduces Dying by 2 and stabilises at 0; success reduces Dying by 1;
    failure increases Dying by 1; critical failure (miss the DC by 10+, or a
    natural 1) increases Dying by 2. Reaching Dying 4 means death.
    """

    dying: int
    dead: bool
    stabilized: bool
    outcome: str
    roll: int
    dc: int
    notes: str


def dying_value(conditions: list[dict[str, Any]]) -> int:
    for cond in conditions or []:
        if str(cond.get("name", "")).lower() == "dying":
            try:
                return int(cond.get("value", 0) or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def wounded_value(conditions: list[dict[str, Any]]) -> int:
    for cond in conditions or []:
        if str(cond.get("name", "")).lower() == "wounded":
            try:
                return int(cond.get("value", 0) or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def gain_dying(
    conditions: list[dict[str, Any]], wounded: int | None = None
) -> tuple[list[dict[str, Any]], bool]:
    """Apply Dying to a creature that just dropped to 0 HP.

    PF2e Remaster: a wounded creature that gains the dying condition adds
    its wounded value to the dying value (here: Dying starts at wounded + 1),
    capped at 4 — and Dying 4 is dead. ``wounded`` defaults to the Wounded
    value already present in ``conditions``.
    """
    if wounded is None:
        wounded = wounded_value(conditions)
    value = min(4, max(1, int(wounded or 0) + 1))
    updated = [dict(c) for c in (conditions or [])]
    for cond in updated:
        if str(cond.get("name", "")).lower() == "dying":
            cond["value"] = value
            return updated, value >= 4
    updated.append({"name": "Dying", "value": value})
    return updated, value >= 4


class CombatTrackerAgent:
    """Deterministic combat resolution per PF2e Remaster."""

    @staticmethod
    def resolve_strike(
        attack_roll: int,
        target_ac: int,
        damage_roll: int,
        target_hp: int,
        target_temp_hp: int = 0,
        natural_roll: int | None = None,
    ) -> StrikeResult:
        """Resolve a single strike against a target per PF2e Remaster rules.

        Args:
            attack_roll: The attack roll total (d20 + modifiers).
            target_ac: Target's Armor Class.
            damage_roll: Total damage rolled (before doubling on crit).
            target_hp: Target's current HP.
            target_temp_hp: Target's current temporary HP.
            natural_roll: The unmodified face of the d20 roll (1-20), if known.
                In PF2e, a natural 20 improves the degree of success by one step,
                and a natural 1 worsens it by one step.

        Returns:
            StrikeResult with outcome, damage dealt, new HP values, and notes.
        """
        margin = attack_roll - target_ac

        if margin >= 10:
            base_outcome = "Critical Success"
        elif margin >= 0:
            base_outcome = "Success"
        elif margin >= -9:
            base_outcome = "Failure"
        else:
            base_outcome = "Critical Failure"

        if natural_roll == 20:
            outcome = {
                "Critical Failure": "Failure",
                "Failure": "Success",
                "Success": "Critical Success",
                "Critical Success": "Critical Success",
            }[base_outcome]
        elif natural_roll == 1:
            outcome = {
                "Critical Success": "Success",
                "Success": "Failure",
                "Failure": "Critical Failure",
                "Critical Failure": "Critical Failure",
            }[base_outcome]
        else:
            outcome = base_outcome

        if outcome == "Critical Success":
            damage = max(1, damage_roll * 2)
            notes = "Critical hit! Damage doubled."
        elif outcome == "Success":
            damage = max(1, damage_roll)
            notes = "Hit."
        elif outcome == "Failure":
            damage = 0
            notes = "Miss."
        else:
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
    def recovery_check(
        dying: int,
        wounded: int = 0,
        roll: int | None = None,
        rng: random.Random | None = None,
    ) -> RecoveryResult:
        """Make a PF2e Remaster recovery check for a dying creature.

        ``roll`` is an injected d20 result (tests / seeded replay); otherwise
        the roll comes from ``rng`` or the module random. ``wounded`` is
        accepted for symmetry with gain_dying and recorded in the notes, but
        the check itself only moves the dying value — wounded only matters
        when Dying is *gained*, not when recovering.
        """
        dying = max(0, int(dying or 0))
        dc = 10 + dying
        if roll is None:
            roll = (rng or random).randint(1, 20)
        roll = int(roll)
        margin = roll - dc
        if margin >= 10:
            base_outcome = "Critical Success"
        elif margin >= 0:
            base_outcome = "Success"
        elif margin <= -10:
            base_outcome = "Critical Failure"
        else:
            base_outcome = "Failure"

        # Natural 20 improves the degree by one step; natural 1 worsens it.
        if roll == 20:
            outcome = {
                "Critical Failure": "Failure",
                "Failure": "Success",
                "Success": "Critical Success",
                "Critical Success": "Critical Success",
            }[base_outcome]
        elif roll == 1:
            outcome = {
                "Critical Success": "Success",
                "Success": "Failure",
                "Failure": "Critical Failure",
                "Critical Failure": "Critical Failure",
            }[base_outcome]
        else:
            outcome = base_outcome

        if outcome == "Critical Success":
            new_dying = max(0, dying - 2)
            stabilized = new_dying == 0
            notes = f"Recovery check {roll} vs DC {dc}: critical success, Dying reduced to {new_dying}."
        elif outcome == "Success":
            new_dying = max(0, dying - 1)
            stabilized = new_dying == 0
            notes = f"Recovery check {roll} vs DC {dc}: success, Dying reduced to {new_dying}."
        elif outcome == "Failure":
            new_dying = dying + 1
            stabilized = False
            notes = f"Recovery check {roll} vs DC {dc}: failure, Dying increased to {new_dying}."
        else:
            new_dying = dying + 2
            stabilized = False
            notes = f"Recovery check {roll} vs DC {dc}: critical failure, Dying increased to {new_dying}."

        dead = new_dying >= 4
        if dead:
            new_dying = 4
            notes += " Dying 4 — the creature is dead."
        if stabilized:
            notes += " Stabilized."
        if wounded:
            notes += f" (Wounded {wounded}.)"
        return RecoveryResult(
            dying=new_dying,
            dead=dead,
            stabilized=stabilized,
            outcome=outcome,
            roll=roll,
            dc=dc,
            notes=notes,
        )

    @staticmethod
    def end_of_turn(
        conditions: list[dict[str, Any]],
        current_hp: int = 0,
        rng: random.Random | None = None,
    ) -> tuple[list[dict[str, Any]], str, int]:
        """Process end-of-turn condition updates per PF2e Remaster.

        - Persistent Damage: roll the dice, then make the DC 15 flat check
          BEFORE applying the damage; success ends the condition.
        - Dying: increments by 1 each end-of-turn while at 0 HP. At Dying 4
          the creature is dead (a Dead condition is appended so callers can
          see it in the returned list). Recovery checks are NOT done here —
          they happen at the start of the dying creature's own turn via
          recovery_check().
        - Wounded: when a creature at 0 HP gains Dying here, the new Dying
          value is wounded + 1 (capped at 4) via gain_dying().
        - Frightened: value > 1 -> decrement by 1; value == 1 -> remove.
        - Duration-based conditions: decrement; remove if 0.

        Args:
            conditions: List of condition dicts with keys:
                - name (str): Condition name (e.g., "Frightened", "Persistent Fire 1d6").
                - value (int): Condition value/severity.
                - duration_rounds (int, optional): Remaining rounds.
            current_hp: Current HP of the creature (for damage and Dying checks).
            rng: Optional random.Random for the persistent-damage flat check
                (seeded replay); defaults to module random.

        Returns:
            Tuple of (updated conditions list, notes string, damage taken).
        """
        updated = []
        notes_parts = []
        hp = max(0, int(current_hp))
        dead = False

        for cond in conditions:
            name = cond.get("name", "")
            value = int(cond.get("value", 1))
            duration = cond.get("duration_rounds")

            if name.lower().startswith("persistent"):
                display = re.sub(r"\s*\d+d\d+\s*", " ", name).strip() or name
                dice_match = re.search(r"(\d+d\d+)", name)
                pending = 0
                if dice_match:
                    # Thread the caller's RNG through so a seeded replay
                    # reproduces the persistent damage exactly.
                    pending, _, _ = roll_dice(dice_match.group(1), rng=rng)
                else:
                    # Persistent damage without dice notation uses the
                    # condition's flat value, e.g. "Persistent Fire 2" = 2.
                    try:
                        pending = int(cond.get("value", 0) or 0)
                    except (TypeError, ValueError):
                        pending = 0

                # PF2e Remaster: at the end of the turn the creature makes a
                # flat check against a FIXED DC 15, before taking the damage.
                # Success ends the condition. Using the rolled damage as the
                # DC made bigger dice harder to shake off - a 1d12 burn was
                # three times stickier than 1d4 - which inverts the rule.
                if pending <= 0:
                    notes_parts.append(f"No persistent {display} damage; condition ends.")
                    continue

                flat_check = (rng or random).randint(1, 20)
                if flat_check >= 15:
                    notes_parts.append(
                        f"Flat check {flat_check} vs DC 15: "
                        f"Recovered from {display}."
                    )
                    continue

                hp = max(0, hp - pending)
                notes_parts.append(
                    f"Flat check {flat_check} vs DC 15: failed, "
                    f"took {pending} {display} damage."
                )

            elif name.lower() == "dying":
                if hp <= 0:
                    value = min(4, value + 1)
                    notes_parts.append(f"Dying increased to {value}.")
                    if value >= 4:
                        dead = True
                        notes_parts.append("Dying 4 — the creature is dead.")

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

            # Work on a copy. end_of_turn was writing cond["value"] and
            # cond["duration_rounds"] onto the caller's dicts and returning the
            # same objects, so the caller's list was mutated as a side effect
            # and "updated" aliased the input.
            entry = dict(cond)
            entry["value"] = value
            updated.append(entry)

        damage_taken = max(0, int(current_hp) - hp)
        if damage_taken > 0 and hp <= 0 and not any(
            c.get("name", "").lower() == "dying" for c in updated
        ):
            # A wounded creature that gains Dying starts at wounded + 1.
            new_conditions, gained_dead = gain_dying(
                updated, wounded=wounded_value(conditions)
            )
            updated = new_conditions
            gained = dying_value(updated)
            notes_parts.append(f"Dying {gained}.")
            if gained_dead:
                dead = True
                notes_parts.append("Dying 4 — the creature is dead.")
        if dead and not any(
            c.get("name", "").lower() == "dead" for c in updated
        ):
            updated.append({"name": "Dead", "value": 1})

        notes = " ".join(notes_parts) if notes_parts else ""
        return updated, notes, damage_taken