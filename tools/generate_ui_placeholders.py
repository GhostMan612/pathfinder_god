#!/usr/bin/env python3
# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Generate 9-slice UI placeholder assets for Pathfinder God.

Creates mathematically perfect 128x128 RGBA panels with 15px
protected corner zones that align exactly with the
RpgPanel.centerSlice Rect.fromLTRB(15, 15, 113, 113) stretch zone.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "spoke" / "assets" / "ui"


def create_9slice_panel(
    filepath: Path,
    outer_color: tuple[int, int, int, int],
    inner_color: tuple[int, int, int, int],
    border_width: int = 15,
    size: int = 128,
) -> None:
    """Create a 9-slice ready panel with protected corners.

    Args:
        filepath: Output path
        outer_color: RGBA for the border/corners
        inner_color: RGBA for the stretchable center
        border_width: Protected corner width (must match Dart centerSlice)
        size: Output dimension (square)
    """
    img = Image.new("RGBA", (size, size), outer_color)
    draw = ImageDraw.Draw(img)

    # Draw the inner stretchable fill
    inner_box = [border_width, border_width, size - border_width, size - border_width]
    draw.rectangle(inner_box, fill=inner_color)

    # Add subtle corner accents (15px) to visually confirm 9-slice zones
    accent = border_width
    for x, y in [(0, 0), (size - accent, 0), (0, size - accent), (size - accent, size - accent)]:
        draw.rectangle([x, y, x + accent, y + accent], fill=(0, 0, 0, 80))

    filepath.parent.mkdir(parents=True, exist_ok=True)
    img.save(filepath)
    print(f"[OK] Generated {filepath.relative_to(REPO_ROOT)}")


def main() -> int:
    print("=== Pathfinder God UI Placeholder Generator ===")
    print(f"Output: {OUTPUT_DIR}")
    print()

    # Palette: (filename, outer_RGBA, inner_RGBA)
    panels = [
        (
            "stone_border.png",
            (80, 80, 80, 255),      # Stone grey border
            (30, 30, 30, 255),      # Dark slate center
        ),
        (
            "parchment_border.png",
            (139, 69, 19, 255),     # SaddleBrown border
            (212, 196, 161, 255),   # Parchment center
        ),
        (
            "gold_filigree.png",
            (212, 175, 55, 255),    # Gold border
            (20, 20, 20, 255),      # Charcoal center
        ),
        (
            "gothic_stone.png",
            (40, 40, 40, 255),      # Dark stone border
            (15, 10, 15, 255),      # Void center
        ),
    ]

    for filename, outer, inner in panels:
        create_9slice_panel(OUTPUT_DIR / filename, outer, inner)

    print(f"\nAll 4 UI assets generated in {OUTPUT_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())