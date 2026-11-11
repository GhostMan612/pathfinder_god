# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Deterministic encounter lifecycle shared by the repository and SoloLoop.

An encounter is a campaign-scoped lifecycle record, not another combat
calculator. All five kinds — ``battle``, ``loot``, ``door``, ``trap``, and
``npc`` — share the same transition rules, and each has a deterministic
resolver in SoloLoop (battle through the combat tracker, the rest through
their per-kind resolvers).

The invariant is deliberately small: at most one encounter per campaign may be
``active`` (the database enforces this with a partial unique index), and only
the transitions in ``ALLOWED_TRANSITIONS`` are legal. Terminal states never
move again; a new encounter starts a new row.

Instant-resolution hazards are the one carve-out. A trap that fires and is
resolved by a single roll does not need to occupy the active slot while a
battle or door encounter is running. ``instant=True`` therefore allows a
pending trap to move straight to ``resolved`` or ``failed``; it is never
``active`` and never blocks another encounter.
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
# Hazards that can resolve in one roll without becoming an active encounter.
INSTANT_RESOLUTION_KINDS: Final[frozenset[str]] = frozenset({"trap"})
INSTANT_RESOLUTION_TARGETS: Final[frozenset[str]] = frozenset(
    {"resolved", "failed"}
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


def validate_transition(
    current: str,
    target: str,
    *,
    kind: str | None = None,
    instant: bool = False,
) -> str:
    """Validate one lifecycle edge and return the target status.

    ``instant=True`` is the trap carve-out: it permits a pending trap to move
    directly to a terminal state without becoming ``active``. Every other
    transition still follows ``ALLOWED_TRANSITIONS``. The caller is responsible
    for persisting the transition; keeping this function pure makes the matrix
    exhaustively testable without a database or an LLM.
    """
    validate_status(current)
    validate_status(target)
    if instant:
        if kind is None:
            raise EncounterStateError(
                "instant resolution requires an encounter kind"
            )
        validate_kind(kind)
        if kind not in INSTANT_RESOLUTION_KINDS:
            allowed = ", ".join(sorted(INSTANT_RESOLUTION_KINDS))
            raise EncounterStateError(
                f"instant resolution is not available for {kind!r}; "
                f"only these kinds can resolve instantly: {allowed}"
            )
        if current != "pending" or target not in INSTANT_RESOLUTION_TARGETS:
            raise EncounterStateError(
                "instant resolution is only available from 'pending' to "
                "'resolved' or 'failed'"
            )
        return target
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
