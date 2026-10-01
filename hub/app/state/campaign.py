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
import logging
import os
import threading
from pathlib import Path
from typing import Any

CampaignState = dict[str, Any]

_EMPTY: CampaignState = {"party": [], "notes": []}
logger = logging.getLogger(__name__)


class CampaignStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        # Read-modify-write on a single JSON file with no lock lost updates
        # when two notes were added concurrently.
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> CampaignState:
        if not self._path.exists():
            return {"party": [], "notes": []}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError:
            # Returning an empty state here was destructive: the next
            # add_note did load() -> append -> save() and overwrote the corrupt
            # file with {"party": [], "notes": []}, destroying the campaign with
            # no error and no backup. Quarantine it instead.
            broken = self._path.with_suffix(self._path.suffix + ".corrupt")
            try:
                self._path.replace(broken)
            except OSError:
                pass
            logger.error("campaign_state.json was corrupt; moved to %s", broken)
            return {"party": [], "notes": []}
        except OSError:
            return {"party": [], "notes": []}
        # Ensure the expected keys exist.
        data.setdefault("party", [])
        data.setdefault("notes", [])
        return data

    def save(self, state: CampaignState) -> None:
        """Write atomically.

        Opening with "w" truncated in place, so a crash or power loss during
        json.dump left a half-written file that the next load() treated as
        corrupt. Write to a temp file, fsync, then rename - atomic on Windows
        and POSIX alike.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self._path)

    def add_note(self, prompt: str, response: str) -> CampaignState:
        with self._lock:
            state = self.load()
            state.setdefault("notes", []).append({"prompt": prompt, "response": response})
            self.save(state)
            return state

    def add_party_member(self, member: dict[str, Any]) -> CampaignState:
        with self._lock:
            state = self.load()
            state.setdefault("party", []).append(member)
            self.save(state)
            return state

    def reset(self) -> CampaignState:
        state = {"party": [], "notes": []}
        self.save(state)
        return state
