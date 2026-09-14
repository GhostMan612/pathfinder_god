# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""GM mode detection and prompt building.

Ported from ``hub_agent.py`` (``detect_mode`` / ``build_prompt`` and the mode
instruction table), lightly extended so the God can produce the *full*
biographies and backstories the project calls for.
"""
from __future__ import annotations

_MODE_TOKENS: list[tuple[str, tuple[str, ...]]] = [
    ("character", ("character", "build", "build me", "level", "class", "race", "ancestry",
                   "background", "feat", "ability score", "wizard", "rogue", "pc", "player character")),
    ("campaign", ("campaign", "adventure", "story", "session", "plot", "arc", "town",
                  "kingdom", "world", "module", "quest")),
    ("map", ("map", "battlemap", "dungeon", "hex", "settlement", "overland", "forest",
             "ruins", "castle", "cave", "region")),
    ("encounter", ("encounter", "combat", "monster", "boss", "trap", "hazard", "npc",
                   "villain", "creature", "fight")),
]

MODE_INSTRUCTIONS: dict[str, str] = {
    "character": (
        "You are an expert Pathfinder character builder. Produce a complete, playable "
        "character: name, ancestry/race, class (and archetype/subclass), background, key "
        "ability scores, signature feats/abilities, equipment, and a short playstyle "
        "summary — followed by a FULL biography and backstory (origin, motivations, "
        "relationships, defining events, and a secret or flaw)."
    ),
    "npc": (
        "You are an expert Pathfinder GM building a memorable NPC. Give name, ancestry, "
        "role/occupation, location, appearance, mannerisms, a stat-block sketch, then a "
        "FULL biography and backstory: history, motivations, secrets, allies/enemies, and "
        "a hook that pulls the party in."
    ),
    "monster": (
        "You are an expert Pathfinder monster designer. Provide the creature's name, type, "
        "level/CR, a practical stat-block sketch (defenses, key attacks, special abilities, "
        "tactics), ecology, and a FULL biography/lore entry: origin, behaviour, habitat, "
        "and its place in the world."
    ),
    "boss": (
        "You are an expert Pathfinder boss designer. Deliver a climactic antagonist: name, "
        "type, level/CR, a full stat-block sketch with phases/legendary-style actions and "
        "tactics, lair and minions, and a FULL biography and backstory — rise to power, "
        "goals, grudges, and the tragedy or menace that makes them unforgettable."
    ),
    "map": (
        "You are an expert Pathfinder cartographer. Design a vivid, scaled locale: overall "
        "layout with approximate dimensions/scale, keyed points of interest, terrain and "
        "hazards, read-aloud sensory detail, and suggested encounters for a GM to run."
    ),
    "campaign": (
        "You are an expert Pathfinder campaign designer. Write a compelling premise, the "
        "structure and key plot beats, major factions and NPCs, and how the arc escalates "
        "from hook to climax to resolution."
    ),
    "encounter": (
        "You are an expert Pathfinder encounter designer. Build a tactical encounter with "
        "enemies, terrain, objectives, and dramatic stakes, balanced to the party level."
    ),
    "general": (
        "You are a master Pathfinder GM. Provide a helpful, rules-aware answer that is "
        "immersive and actionable. Cite the edition and rule name when you rely on the "
        "provided rule context."
    ),
}


def detect_mode(user_query: str) -> str:
    """Classify a request into a generation mode (defaults to ``general``)."""
    lowered = user_query.lower()
    for mode, tokens in _MODE_TOKENS:
        if any(tok in lowered for tok in tokens):
            return mode
    return "general"


def build_prompt(
    user_query: str,
    mode: str,
    edition: str,
    context: str,
    history: list[tuple[str, str]] | None = None,
) -> str:
    """Assemble the final user prompt from mode, edition, RAG context, and history."""
    instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["general"])

    history_block = "None"
    if history:
        history_block = "\n".join(f"{speaker.title()}: {message}" for speaker, message in history[-4:])

    return f"""{instruction}

Edition focus: {edition}

Recent conversation:
{history_block}

Rule context:
{context}

User request:
{user_query}

Respond in Markdown. Ground your answer in the rule context above; if it lacks a detail,
say so briefly and make a clear, sensible Pathfinder assumption rather than inventing rules.
"""
