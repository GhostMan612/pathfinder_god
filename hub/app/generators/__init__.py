# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Typed generators — the God's core creative powers.

Each ``kind`` maps to (a) a prompt wrapper that frames the user's request and
(b) the agent ``mode`` that selects the right system instruction (full bios and
backstories). The actual generation runs through ``service.GodService``.
"""
from __future__ import annotations

# kind -> (prompt template, agent mode)
GENERATORS: dict[str, tuple[str, str]] = {
    "character": ("Create a complete Pathfinder player character: {p}", "character"),
    "npc": ("Create a memorable Pathfinder NPC: {p}", "npc"),
    "monster": ("Design a Pathfinder monster: {p}", "monster"),
    "boss": ("Design a climactic Pathfinder boss encounter: {p}", "boss"),
    "map": ("Design a scaled Pathfinder map/location: {p}", "map"),
    "campaign": ("Design a Pathfinder campaign: {p}", "campaign"),
    "encounter": ("Design a Pathfinder combat encounter: {p}", "encounter"),
}


def resolve(kind: str, prompt: str) -> tuple[str, str | None]:
    """Return ``(query, mode)`` for a generator kind.

    Unknown kinds fall back to the raw prompt with auto-detected mode.
    """
    entry = GENERATORS.get(kind)
    if entry is None:
        return prompt, None
    template, mode = entry
    return template.format(p=prompt), mode


def kinds() -> list[str]:
    return list(GENERATORS)
