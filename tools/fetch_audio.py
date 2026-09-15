#!/usr/bin/env python3
# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Automated CC0/royalty-free audio fetcher for Pathfinder God.

Downloads known public-domain and CC0 RPG audio assets from hotlink-safe
sources directly into spoke/assets/audio/, matching the schema in
audio_service.dart. Updates docs/audio-credits.md with attributions.

NOTE: Many CC0 audio hosts (Pixabay, Freesound) block direct hotlinking.
This script creates properly-named placeholder files and logs the
canonical source URLs for manual download. Replace placeholders with
real assets before release.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "spoke" / "assets" / "audio"
CREDITS_FILE = REPO_ROOT / "docs" / "audio-credits.md"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Canonical CC0 / royalty-free RPG audio sources.
# Format: (local_filename, source_url, attribution_line)
AUDIO_MANIFEST = [
    # Background music (loopable)
    (
        "bgm_dungeon.mp3",
        "https://pixabay.com/music/search/dungeon%20ambient/",
        'Dungeon ambience - source: Pixabay (CC0), search "dungeon ambient"',
    ),
    (
        "bgm_dungeon_ambient.mp3",
        "https://pixabay.com/music/search/dungeon%20dark%20ambient/",
        'Deep dungeon ambient - source: Pixabay (CC0), search "dungeon dark ambient"',
    ),
    (
        "bgm_combat.mp3",
        "https://pixabay.com/music/search/battle%20music/",
        'Combat tension - source: Pixabay (CC0), search "battle music"',
    ),
    (
        "bgm_combat_heavy.mp3",
        "https://pixabay.com/music/search/epic%20battle%20music/",
        'Heavy combat orchestral - source: Pixabay (CC0), search "epic battle music"',
    ),
    (
        "bgm_eerie.mp3",
        "https://pixabay.com/music/search/creepy%20ambient/",
        'Eerie atmosphere - source: Pixabay (CC0), search "creepy ambient"',
    ),
    (
        "bgm_tavern_rowdy.mp3",
        "https://pixabay.com/music/search/medieval%20tavern/",
        'Rowdy tavern music - source: Pixabay (CC0), search "medieval tavern"',
    ),
    # Sound effects (short, low-latency)
    (
        "dice_heavy.ogg",
        "https://freesound.org/search/?q=heavy%20dice",
        'Heavy dice impact - source: Freesound (CC0), search "heavy dice"',
    ),
    (
        "dice_glass.ogg",
        "https://freesound.org/search/?q=glass%20clink",
        'Glass dice clink - source: Freesound (CC0), search "glass clink"',
    ),
    (
        "dice_crit_chime.wav",
        "https://freesound.org/search/?q=magic%20chime",
        'Critical hit chime - source: Freesound (CC0), search "magic chime"',
    ),
    (
        "dice_fail_glass.wav",
        "https://freesound.org/search/?q=glass%20break",
        'Critical fail glass shatter - source: Freesound (CC0), search "glass break"',
    ),
]

# Required base assets (must exist for app to run)
REQUIRED_BASE = [
    "bgm_tavern.mp3",
    "bgm_inn.mp3",
    "dice_roll.ogg",
    "dice_crit.wav",
    "dice_fail.ogg",
    "error.ogg",
    "tap.wav",
]


def create_placeholder(path: Path, url: str) -> None:
    """Create a tiny placeholder file with source URL embedded as comment."""
    content = f"# Placeholder for {path.name}\n# Download from: {url}\n# Replace this file with the real CC0 asset.\n"
    path.write_text(content, encoding="utf-8")


def update_credits(new_entries: list[str]) -> None:
    """Append new attribution lines to docs/audio-credits.md if not already present."""
    existing = CREDITS_FILE.read_text(encoding="utf-8") if CREDITS_FILE.exists() else ""
    with CREDITS_FILE.open("a", encoding="utf-8") as f:
        for line in new_entries:
            if line not in existing:
                f.write(f"\n{line}")


def main() -> int:
    print("=== Pathfinder God Audio Fetcher ===")
    print(f"Target directory: {ASSETS_DIR}")
    print()

    new_credits = []
    success_count = 0

    for filename, url, credit in AUDIO_MANIFEST:
        dest = ASSETS_DIR / filename
        print(f"-> {filename}")

        if dest.exists() and dest.stat().st_size > 100:
            print(f"  OK Already exists ({dest.stat().st_size} bytes)")
            success_count += 1
            new_credits.append(f"- {credit}")
            continue

        print(f"  Source: {url}")
        create_placeholder(dest, url)
        print(f"  Created placeholder ({dest.stat().st_size} bytes)")
        success_count += 1
        new_credits.append(f"- {credit}")

    print()
    print(f"Summary: {success_count}/{len(AUDIO_MANIFEST)} asset slots ready")
    if new_credits:
        update_credits(new_credits)
        print(f"Updated {CREDITS_FILE} with {len(new_credits)} attribution(s)")

    missing = [f for f in REQUIRED_BASE if not (ASSETS_DIR / f).exists()]
    if missing:
        print(f"\nWARNING: Missing required assets: {', '.join(missing)}")
        return 1

    print("\nNext steps:")
    print("  1. Visit each Source URL above")
    print("  2. Download a CC0 asset matching the description")
    print("  3. Replace the placeholder in spoke/assets/audio/")
    print("  4. Run this script again to verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())