# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tiny UI sounds for the Command Center (Windows Crew only).

Uses winsound (stdlib, zero dependencies, PyInstaller-safe) so the
standalone exe needs no audio plugins. Silent no-op on other platforms
or when a file is missing — sound must never break the console.
Royalty-free sources + licenses: docs/audio-credits.md
"""
from __future__ import annotations

import sys
from pathlib import Path


def _sounds_dir() -> Path:
    frozen = getattr(sys, "frozen", False)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    if frozen:
        return base / "sounds"
    return Path(__file__).parent / "sounds"


def play(name: str) -> None:
    try:
        import winsound

        path = _sounds_dir() / name
        if path.exists():
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME
                | winsound.SND_ASYNC
                | winsound.SND_NODEFAULT,
            )
    except Exception:
        pass


def roll() -> None:
    play("cc_roll.wav")


def crit() -> None:
    play("cc_crit.wav")


def tap() -> None:
    play("cc_tap.wav")
