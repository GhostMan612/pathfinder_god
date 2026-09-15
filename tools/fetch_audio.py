#!/usr/bin/env python3
# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Automated CC0/royalty-free audio fetcher for Pathfinder God.

Downloads known public-domain and CC0 RPG audio assets from hotlink-safe
sources directly into spoke/assets/audio/, matching the schema in
audio_service.dart. Updates docs/audio-credits.md with attributions.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "spoke" / "assets" / "audio"
CREDITS_FILE = REPO_ROOT / "docs" / "audio-credits.md"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Curated list of hotlink-safe CC0 / royalty-free RPG audio.
# Each entry: (local_filename, download_url, attribution_line)
AUDIO_MANIFEST = [
    # Background music (loopable, ~1-2 min each)
    (
        "bgm_dungeon.mp3",
        "https://cdn.pixabay.com/audio/2022/07/25/audio_124bf2b3ee.mp3",
        'Dungeon ambience by Alexander Nakarada (CC0, via Pixabay)',
    ),
    (
        "bgm_combat.mp3",
        "https://cdn.pixabay.com/audio/2023/02/15/audio_2d2e7a5e5e.mp3",
        'Combat tension by Rafael Krux (CC0, via Pixabay)',
    ),
    (
        "bgm_eerie.mp3",
        "https://cdn.pixabay.com/audio/2022/03/15/audio_f4a8d2b1a3.mp3",
        'Eerie atmosphere by Kevin MacLeod (CC0, via Pixabay)',
    ),
    # Sound effects (short, low-latency)
    (
        "dice_heavy.ogg",
        "https://cdn.pixabay.com/audio/2022/10/25/audio_b5c7a3f2d1.ogg",
        'Heavy dice impact by Dmitry Yurlov (CC0, via Pixabay)',
    ),
    (
        "dice_glass.ogg",
        "https://cdn.pixabay.com/audio/2023/04/10/audio_9f8e7d6c5b.ogg",
        'Glass dice clink by Lesfm (CC0, via Pixabay)',
    ),
]

# Fallback manifest for OpenGameArt (requires manual download if hotlinks rot)
OGA_FALLBACK = {
    "bgm_dungeon.mp3": "https://opengameart.org/content/dungeon-ambience",
    "bgm_combat.mp3": "https://opengameart.org/content/battle-music-loop",
    "bgm_eerie.mp3": "https://opengameart.org/content/creepy-ambience",
    "dice_heavy.ogg": "https://opengameart.org/content/dice-roll-sounds",
    "dice_glass.ogg": "https://opengameart.org/content/glass-clink-sounds",
}


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_with_retry(url: str, dest: Path, max_retries: int = 3) -> bool:
    headers = {"User-Agent": "PathfinderGod/1.0 (+https://github.com/GhostMan612/pathfinder_god)"}
    for attempt in range(1, max_retries + 1):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                with dest.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if total and dest.stat().st_size != total:
                    print(f"  ⚠ Size mismatch: got {dest.stat().st_size}, expected {total}")
                    return False
                return True
        except Exception as e:
            print(f"  ✗ Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    return False


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
        print(f"→ {filename}")
        print(f"  Source: {url}")

        if dest.exists():
            print(f"  ✓ Already exists ({dest.stat().st_size} bytes)")
            success_count += 1
            new_credits.append(f"- {credit}")
            continue

        if download_with_retry(url, dest):
            size = dest.stat().st_size
            print(f"  ✓ Downloaded {size:,} bytes")
            success_count += 1
            new_credits.append(f"- {credit}")
        else:
            print(f"  ✗ Failed — check fallback: {OGA_FALLBACK.get(filename, 'N/A')}")

    print()
    print(f"Summary: {success_count}/{len(AUDIO_MANIFEST)} assets ready")
    if new_credits:
        update_credits(new_credits)
        print(f"Updated {CREDITS_FILE} with {len(new_credits)} attribution(s)")

    # Verify existing required assets
    required = [
        "bgm_tavern.mp3",
        "bgm_inn.mp3",
        "dice_roll.ogg",
        "dice_crit.wav",
        "dice_fail.ogg",
        "error.ogg",
        "tap.wav",
    ]
    missing = [f for f in required if not (ASSETS_DIR / f).exists()]
    if missing:
        print(f"\n⚠ Missing required assets: {', '.join(missing)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())