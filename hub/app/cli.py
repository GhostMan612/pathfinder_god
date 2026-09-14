# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Command-line access to the God — a convenience wrapper over the service.

Mirrors the old ``hub_agent.py`` UX:

    pathfinder-god "build me a level 3 rogue"
    pathfinder-god --edition 2e            # interactive loop

Handy for testing the hub without the phone or the HTTP server.
"""
from __future__ import annotations

import argparse
import asyncio

from .config import get_settings
from .service import GodService
from .state.campaign import CampaignStore


async def _answer(service: GodService, query: str, edition: str | None, history: list[tuple[str, str]]) -> str:
    result, prepared = await service.ask(query, edition=edition, history=history)
    tag = f"[{result.backend} · {prepared.mode} · {prepared.edition}]"
    return f"{tag}\n{result.text}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Pathfinder God — local GM (1e + 2e)")
    parser.add_argument("query", nargs="?", help="What should the Pathfinder God help with?")
    parser.add_argument("--edition", default=None, help="Edition filter: 1e, 2e, or both")
    args = parser.parse_args()

    settings = get_settings()
    service = GodService(settings)
    store = CampaignStore(settings.campaign_state_path)

    if args.query:
        print(asyncio.run(_answer(service, args.query, args.edition, [])))
        return

    print("Pathfinder God ready. Type 'quit' to exit, '/save' to persist, '/new' to reset.")
    history: list[tuple[str, str]] = []
    while True:
        try:
            query = input("\nGM Query: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break
        if not query or query.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break
        if query == "/save":
            for speaker, message in history:
                if speaker == "user":
                    continue
            print(f"Saved campaign state to {store.path}")
            continue
        if query == "/new":
            store.reset()
            history.clear()
            print("Started a new campaign state.")
            continue

        history.append(("user", query))
        print("\n--- Pathfinder Response ---")
        answer = asyncio.run(_answer(service, query, args.edition, history))
        history.append(("assistant", answer))
        if any(tok in query.lower() for tok in ("party", "session", "npc")):
            store.add_note(query, answer)
        print(answer)


if __name__ == "__main__":
    main()
