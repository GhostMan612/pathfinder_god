# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Campaign state — save/load the party roster and GM notes as JSON.

Ported from ``hub_agent.py``'s ``save_campaign_state`` / ``load_campaign_state``,
wrapped in a small store so the FastAPI layer can read/append safely. The file
lives under ``data/`` and is git-ignored (per-user runtime state).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CampaignState = dict[str, Any]

_EMPTY: CampaignState = {"party": [], "notes": []}


class CampaignStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> CampaignState:
        if not self._path.exists():
            return {"party": [], "notes": []}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {"party": [], "notes": []}
        # Ensure the expected keys exist.
        data.setdefault("party", [])
        data.setdefault("notes", [])
        return data

    def save(self, state: CampaignState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)

    def add_note(self, prompt: str, response: str) -> CampaignState:
        state = self.load()
        state.setdefault("notes", []).append({"prompt": prompt, "response": response})
        self.save(state)
        return state

    def add_party_member(self, member: dict[str, Any]) -> CampaignState:
        state = self.load()
        state.setdefault("party", []).append(member)
        self.save(state)
        return state

    def reset(self) -> CampaignState:
        state = {"party": [], "notes": []}
        self.save(state)
        return state
