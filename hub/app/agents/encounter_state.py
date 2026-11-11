# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Deterministic encounter lifecycle shared by the repository and SoloLoop.

An encounter is a campaign-scoped lifecycle record, not another combat
calculator. The first concrete type is ``battle``: ``start_combat`` creates a
pending battle, activates it once the roster is built, and resolves or abandons
it when the fight ends. The remaining kinds are reserved so the door/trap/NPC
slices can attach to the same transition rules instead of inventing a second
state model later.

The invariant is deliberately small: at most one encounter per campaign may be
``active`` (the database enforces this with a partial unique index), and only
the transitions in ``ALLOWED_TRANSITIONS`` are legal. Terminal states never
move again; a new encounter starts a new row.
"""

from __future__ import annotations

from typing import Final, Literal

EncounterKind = Literal["battle", "loot", "door", "trap", "npc"]
EncounterStatus = Literal[
    "pending", "active", "resolved", "failed", "abandoned"
]

ENCOUNTER_KINDS: Final[tuple[str, ...]] = (
    "battle",
    "loot",
    "door",
    "trap",
    "npc",
)
ENCOUNTER_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "active",
    "resolved",
    "failed",
    "abandoned",
)
TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {"resolved", "failed", "abandoned"}
)

# pending -> active (start) or abandoned (never started).
# active -> resolved (success), failed (defeat), or abandoned (fled/cancelled).
# Terminal statuses have no outgoing edges.
ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"active", "abandoned"}),
    "active": frozenset({"resolved", "failed", "abandoned"}),
    "resolved": frozenset(),
    "failed": frozenset(),
    "abandoned": frozenset(),
}


class EncounterStateError(ValueError):
    """Raised when an encounter kind, status, or transition is invalid."""


def validate_kind(kind: str) -> str:
    """Return ``kind`` unchanged or raise ``EncounterStateError``."""
    if kind not in ENCOUNTER_KINDS:
        allowed = ", ".join(ENCOUNTER_KINDS)
        raise EncounterStateError(
            f"unknown encounter kind {kind!r}; expected one of: {allowed}"
        )
    return kind


def validate_status(status: str) -> str:
    """Return ``status`` unchanged or raise ``EncounterStateError``."""
    if status not in ENCOUNTER_STATUSES:
        allowed = ", ".join(ENCOUNTER_STATUSES)
        raise EncounterStateError(
            f"unknown encounter status {status!r}; expected one of: {allowed}"
        )
    return status


def validate_transition(current: str, target: str) -> str:
    """Validate one lifecycle edge and return the target status.

    The caller is responsible for persisting the transition. Keeping this
    function pure makes the transition matrix exhaustively testable without a
    database or an LLM.
    """
    validate_status(current)
    validate_status(target)
    if target not in ALLOWED_TRANSITIONS[current]:
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS[current])) or "none"
        raise EncounterStateError(
            f"cannot transition encounter from {current!r} to {target!r}; "
            f"allowed from {current!r}: {allowed}"
        )
    return target


def is_terminal(status: str) -> bool:
    """True when the encounter can never transition again."""
    validate_status(status)
    return status in TERMINAL_STATUSES
