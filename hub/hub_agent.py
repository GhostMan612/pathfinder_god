# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
import argparse
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import ollama  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    ollama = None

ROOT = Path(__file__).resolve().parent
DEFAULT_DBS = [
    ROOT / "pathfinder_god.db",
    ROOT / "pathfinder_rag.db",
    ROOT / "pathfinder_1e_rag.db",
    ROOT / "pathfinder_2e_rag.db",
]


def normalize_edition(raw_edition: Optional[str]) -> str:
    if raw_edition is None:
        return "both"
    cleaned = str(raw_edition).strip().lower()
    if cleaned in {"1e", "pf1", "pf1e", "pathfinder 1e", "pathfinder1", "pathfinder first edition"}:
        return "1e"
    if cleaned in {"2e", "pf2", "pf2e", "pathfinder 2e", "pathfinder2", "pathfinder second edition"}:
        return "2e"
    if cleaned in {"both", "all", "any", "default", ""}:
        return "both"
    return cleaned


def detect_mode(user_query: str) -> str:
    lowered = user_query.lower()
    if any(token in lowered for token in ["character", "build", "build me", "level", "class", "race", "ancestry", "background", "feat", "ability score", "wizard", "rogue"]):
        return "character"
    if any(token in lowered for token in ["campaign", "adventure", "story", "session", "plot", "arc", "town", "kingdom", "world", "module"]):
        return "campaign"
    if any(token in lowered for token in ["map", "battlemap", "dungeon", "hex", "settlement", "overland", "forest", "ruins", "castle"]):
        return "map"
    if any(token in lowered for token in ["encounter", "combat", "monster", "boss", "trap", "hazard", "npc"]):
        return "encounter"
    return "general"


def available_databases(edition: str) -> List[Path]:
    chosen: List[Path] = []
    seen = set()
    for db_path in DEFAULT_DBS:
        if db_path.exists() and db_path not in seen:
            if edition == "both":
                chosen.append(db_path)
            elif edition == "1e" and db_path.name in {"pathfinder_god.db", "pathfinder_rag.db", "pathfinder_1e_rag.db"}:
                chosen.append(db_path)
            elif edition == "2e" and db_path.name in {"pathfinder_god.db", "pathfinder_rag.db", "pathfinder_2e_rag.db"}:
                chosen.append(db_path)
            seen.add(db_path)
    return chosen


def _connect(db_path: Path) -> Optional[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn
    except Exception as exc:  # pragma: no cover - runtime guard
        print(f"[DB Error] unable to open {db_path.name}: {exc}")
        return None


def query_db(search_term: str, edition: str = "both", limit: int = 3) -> List[Tuple[str, str]]:
    clean_term = re.sub(r"[^\w\s]", "", search_term)
    words = [word for word in clean_term.split() if len(word) > 3]
    search_query = " OR ".join(words) if words else clean_term or search_term

    results: List[Tuple[str, str]] = []
    for db_path in available_databases(edition):
        conn = _connect(db_path)
        if conn is None:
            continue
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = {row[0] for row in cursor.fetchall()}

            if "rules_fts" in tables and "rules" in tables:
                cursor.execute(
                    """
                    SELECT rules.name, rules.raw_content
                    FROM rules_fts
                    JOIN rules ON rules_fts.rowid = rules.id
                    WHERE rules_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (search_query, limit),
                )
            elif "chunks" in tables:
                cursor.execute(
                    "SELECT source, content FROM chunks WHERE chunks MATCH ? LIMIT ?",
                    (search_query, limit),
                )
            elif "items" in tables:
                cursor.execute(
                    "SELECT name, content FROM items WHERE items MATCH ? LIMIT ?",
                    (search_query, limit),
                )
            elif "rules" in tables:
                like_term = f"%{search_term}%"
                cursor.execute(
                    "SELECT name, raw_content FROM rules WHERE name LIKE ? OR raw_content LIKE ? LIMIT ?",
                    (like_term, like_term, limit),
                )
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                conn.close()
                continue

            for row in cursor.fetchall():
                if row and row[1]:
                    name = row[0] if isinstance(row[0], str) else str(row[0])
                    content = row[1] if isinstance(row[1], str) else str(row[1])
                    results.append((name, content[:1200]))
        except Exception as exc:  # pragma: no cover - runtime guard
            print(f"[DB Error] query failed for {db_path.name}: {exc}")
        finally:
            conn.close()

    return results[:limit]


def build_context(user_query: str, edition: str = "both") -> str:
    hits = query_db(user_query, edition=edition)
    if hits:
        snippets = []
        for name, content in hits:
            snippets.append(f"Source: {name}\n{content}")
        return "\n\n".join(snippets)
    return (
        "No local Pathfinder rule hit was found in the bundled databases. "
        "Answer as a knowledgeable GM using broad Pathfinder principles and clearly state any assumptions."
    )


def build_prompt(user_query: str, mode: str, edition: str, context: str, history: Optional[List[Tuple[str, str]]] = None) -> str:
    mode_instructions = {
        "character": "You are an expert Pathfinder character builder. Create a practical character concept with class, ancestry, background, key abilities, equipment, and a short playstyle summary.",
        "campaign": "You are an expert Pathfinder campaign designer. Write a compelling campaign premise, structure, and key plot beats that fit Pathfinder tone.",
        "map": "You are an expert Pathfinder cartographer. Design a vivid locale, notable landmarks, and a practical encounter layout for a GM.",
        "encounter": "You are an expert Pathfinder encounter designer. Build a tactical encounter with enemies, terrain, and dramatic stakes.",
        "general": "You are a master Pathfinder GM. Provide a helpful and rules-aware answer that is immersive and actionable.",
    }
    history_block = ""
    if history:
        history_lines = []
        for speaker, message in history[-4:]:
            history_lines.append(f"{speaker.title()}: {message}")
        history_block = "\n".join(history_lines)

    return f"""
{mode_instructions[mode]}

Edition focus: {edition}

Recent conversation:
{history_block if history_block else 'None'}

Rule context:
{context}

User request:
{user_query}

Respond with a concise but useful answer. If the rule context does not contain enough detail, say so and make a clear assumption.
"""


def format_character_sheet(character_class: str, ancestry: str, background: str, level: str, theme: str) -> str:
    return f"""Character Sheet
================
Class: {character_class}
Ancestry: {ancestry}
Background: {background}
Level: {level}
Theme: {theme}

Core Notes
- Choose a simple gear loadout that fits the theme.
- Pick 2-3 signature abilities or tactics.
- Add a short hook for why the character joins the party.
"""


def format_adventure_outline(title: str, sessions: int) -> str:
    return f"""Adventure Outline
=================
Title: {title}
Sessions: {sessions}

Structure
1. Opening hook: establish the danger and the party's reason to act.
2. Rising tension: reveal factions, clues, and escalating stakes.
3. Climax: confront the villain, trap, or mystery.
4. Resolution: reward the party and leave room for future play.
"""


def format_session_note(title: str, summary: str) -> str:
    return f"""Session Note
===========
Title: {title}
Summary: {summary}
"""


def format_npc_template(name: str, role: str, location: str) -> str:
    return f"""NPC Template
============
Name: {name}
Role: {role}
Location: {location}

Motivation: What does this NPC want right now?
Secrets: What do they hide?
Hook: How do they pull the party into the story?
"""


def format_encounter_template(title: str, party_level: int) -> str:
    return f"""Encounter Template
===================
Title: {title}
Party Level: {party_level}

Setup: What dangerous situation faces the party?
Threats: What enemies, hazards, or complications appear?
Objective: What must the party accomplish?
Reward: What payoff awaits success?
"""


def save_campaign_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def load_campaign_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"party": [], "notes": []}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_command(raw_input: str) -> Tuple[str, Optional[str]]:
    command = raw_input.strip()
    if not command.startswith("/"):
        return ("chat", None)
    if command in {"/save", "/new"}:
        return (command[1:], None)
    if command.startswith("/load "):
        return ("load", command[len("/load "):].strip())
    return ("help", None)


def generate_fallback(user_query: str, mode: str, edition: str) -> str:
    if mode == "character":
        return format_character_sheet("TBD", "TBD", "TBD", "Level 1", "Pathfinder adventure")
    if mode == "campaign":
        return format_adventure_outline(f"Pathfinder Adventure ({edition.upper()})", 3)
    if mode == "map":
        return (
            f"Map concept for {edition.upper()}:\n"
            f"- Build a layered locale with a central hub, hidden danger, and a fallback escape route.\n"
            f"- Place 4-6 points of interest that encourage exploration and negotiation.\n"
            f"- Include terrain that changes the pacing of encounters."
        )
    if mode == "encounter":
        return format_encounter_template("Custom Encounter", 3)
    summary = f"Pathfinder GM answer for {edition.upper()}:"
    if "rule" in user_query.lower() or "rules" in user_query.lower():
        return (
            f"{summary}\n"
            f"- Answer with a direct rules summary and note any uncertainty.\n"
            f"- If a precise rule is unavailable locally, say so and provide the closest practical ruling."
        )
    return (
        f"{summary}\n"
        f"- Frame the request as a playable scene or situation.\n"
        f"- Give the party a clear goal, a complication, and a reward.\n"
        f"- Keep the tone grounded in classic Pathfinder adventure structure."
    )


def run_agent(user_query: str, edition: Optional[str] = None, history: Optional[List[Tuple[str, str]]] = None) -> str:
    normalized_edition = normalize_edition(edition)
    mode = detect_mode(user_query)
    context = build_context(user_query, edition=normalized_edition)
    prompt = build_prompt(user_query, mode, normalized_edition, context, history=history)

    if ollama is not None:
        try:
            response = ollama.chat(
                model=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
                messages=[
                    {"role": "system", "content": "You are a precise Pathfinder GM assistant with access to local 1e and 2e knowledge."},
                    {"role": "user", "content": prompt},
                ],
            )
            return response["message"]["content"]
        except Exception as exc:  # pragma: no cover - runtime guard
            print(f"[Ollama] falling back to local planner: {exc}")

    return generate_fallback(user_query, mode, normalized_edition)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pathfinder GM assistant with 1e and 2e support")
    parser.add_argument("query", nargs="?", help="What should the Pathfinder god help with?")
    parser.add_argument("--edition", default=None, help="Edition filter: 1e, 2e, or both")
    parser.add_argument("--state-file", default=str(ROOT / "campaign_state.json"), help="Path to the JSON campaign state file")
    args = parser.parse_args()

    history: List[Tuple[str, str]] = []
    state_path = Path(args.state_file)
    state = load_campaign_state(state_path)

    if args.query:
        print(run_agent(args.query, edition=args.edition, history=history))
        return

    print("Pathfinder GM Assistant ready. Type 'quit' to exit or '/save' to persist state.")
    while True:
        try:
            user_query = input("\nGM Query: ").strip()
        except KeyboardInterrupt:
            save_campaign_state(state_path, state)
            print("\nGoodbye.")
            break
        if not user_query or user_query.lower() in {"quit", "exit"}:
            save_campaign_state(state_path, state)
            print("Goodbye.")
            break

        command, argument = parse_command(user_query)
        if command == "save":
            save_campaign_state(state_path, state)
            print(f"Saved campaign state to {state_path}")
            continue
        if command == "load":
            target = Path(argument) if argument else state_path
            if not target.is_absolute():
                target = ROOT / target
            state = load_campaign_state(target)
            state_path = target
            print(f"Loaded campaign state from {state_path}")
            continue
        if command == "new":
            state = {"party": [], "notes": []}
            state_path = ROOT / "campaign_state.json"
            print("Started a new campaign state")
            continue
        if command == "help":
            print("Commands: /save, /load <file>, /new, /help")
            continue

        history.append(("user", user_query))
        print("\n--- Pathfinder Response ---")
        response = run_agent(user_query, edition=args.edition, history=history)
        history.append(("assistant", response))
        if "party" in user_query.lower() or "session" in user_query.lower() or "npc" in user_query.lower():
            state.setdefault("notes", []).append({"prompt": user_query, "response": response})
        print(response)


if __name__ == "__main__":
    main()
