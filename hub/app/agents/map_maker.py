# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Map Maker Agent — LLM map design + Pillow rendering.

Generates a print-ready battle map PNG from a natural language prompt.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.llm.ollama_client import OllamaClient
from app.config import get_settings

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

logger = logging.getLogger(__name__)


@dataclass
class MapRoom:
    x: int
    y: int
    w: int
    h: int
    name: str


@dataclass
class MapLayout:
    width: int
    height: int
    rooms: list[MapRoom]


@dataclass
class BuildResult:
    valid: bool
    layout: MapLayout | None
    base64_png: str | None
    error: str | None


SYSTEM_PROMPT = """You are a Pathfinder 2e battle map designer.
Given a user prompt describing a location, output a JSON object with:
- width: grid width in squares (1-50)
- height: grid height in squares (1-50)
- rooms: array of objects with x, y, w, h (all ints, grid coordinates), name (string)

Rules:
- Coordinates are 0-indexed from top-left
- Rooms must not exceed map bounds
- Rooms should be rectangular
- Total area of rooms should not exceed map area
- Output ONLY the JSON object, no markdown, no commentary
"""


class MapMakerAgent:
    def __init__(self, llm: OllamaClient):
        self._llm = llm
        self._settings = get_settings()

    def _parse_layout(self, raw: str) -> MapLayout | None:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

        try:
            width = int(data.get("width", 0))
            height = int(data.get("height", 0))
            rooms_data = data.get("rooms", [])
            if not (1 <= width <= 50 and 1 <= height <= 50):
                return None
            rooms = []
            for r in rooms_data:
                room = MapRoom(
                    x=int(r["x"]),
                    y=int(r["y"]),
                    w=int(r["w"]),
                    h=int(r["h"]),
                    name=str(r.get("name", "Room")),
                )
                if not (0 <= r["x"] < width and 0 <= r["y"] < height):
                    return None
                if not (1 <= r["w"] <= width and 1 <= r["h"] <= height):
                    return None
                if not (0 <= r["x"] + r["w"] <= width and 0 <= r["y"] + r["h"] <= height):
                    return None
                rooms.append(room)
            return MapLayout(width=width, height=height, rooms=rooms)
        except (KeyError, ValueError, TypeError):
            return None

    def _render_map(self, layout: MapLayout) -> str | None:
        if Image is None:
            return None

        cell_size = 50
        width_px = layout.width * cell_size
        height_px = layout.height * cell_size

        # Create image with dark void background
        img = Image.new("RGBA", (width_px, height_px), (0x1E, 0x1B, 0x18, 0xFF))
        draw = ImageDraw.Draw(img)

        # Draw grid overlay (subtle gold)
        grid_color = (0xD4, 0xAF, 0x37, 0x33)  # #D4AF37 at 20% opacity
        for x in range(0, width_px + 1, 50):
            draw.line([(x, 0), (x, height_px)], fill=grid_color, width=1)
        for y in range(0, height_px + 1, 50):
            draw.line([(0, y), (width_px, y)], fill=grid_color, width=1)

        # Draw rooms
        room_fill = (0x28, 0x24, 0x1F, 0xE6)  # Dark parchment
        room_border = (0xD4, 0xAF, 0x37, 0xFF)  # Gold border

        # Try to load a font
        font = None
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 12)
        except Exception:
            try:
                font = ImageFont.load_default()
            except Exception:
                pass

        for room in layout.rooms:
            x0 = room.x * 50
            y0 = room.y * 50
            x1 = (room.x + room.w) * 50
            y1 = (room.y + room.h) * 50

            # Draw room fill
            draw.rectangle([x0, y0, x1, y1], fill=room_fill)

            # Draw room border (thick)
            draw.rectangle([x0, y0, x1, y1], outline=room_border, width=3)

            # Draw room name centered
            if room.name:
                text = room.name
                if font:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                    tx = x0 + (room.w * 50 - text_w) // 2
                    ty = y0 + (room.h * 50 - text_h) // 2
                    # Draw text with shadow for readability
                    draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0, 200), font=font)
                    draw.text((tx, ty), text, fill=(0xD4, 0xAF, 0x37, 0xFF), font=font)

        # Encode to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("ascii")

    async def build(self, prompt: str) -> BuildResult:
        full_prompt = SYSTEM_PROMPT + "\n\nUser request: " + prompt.strip()
        try:
            raw = await self._llm.generate(
                prompt=full_prompt,
                model="qwen2.5:3b",
                temperature=0.3,
                num_predict=800,
            )
        except Exception as e:
            logger.error(f"MapMaker LLM failed: {e}")
            return BuildResult(False, None, None, f"LLM generation failed: {e}")

        layout = self._parse_layout(raw)
        if layout is None:
            return BuildResult(False, None, None, "LLM returned invalid JSON or invalid layout")

        try:
            b64 = self._render_map(layout)
        except Exception as e:
            logger.error(f"Map rendering failed: {e}")
            return BuildResult(False, None, None, f"Map rendering failed: {e}")

        if b64 is None:
            return BuildResult(False, None, None, "Pillow not available or rendering failed")

        return BuildResult(
            valid=True,
            layout=layout,
            base64_png=b64,
            error=None,
        )


SYSTEM_PROMPT = """You are a Pathfinder 2e battle map designer.
Given a user prompt describing a location, output a JSON object with:
- width: grid width in squares (1-50)
- height: grid height in squares (1-50)
- rooms: array of objects with x, y, w, h (all ints, grid coordinates), name (string)

Rules:
- Coordinates are 0-indexed from top-left
- Rooms must not exceed map bounds
- Rooms should be rectangular
- Total area of rooms should not exceed map area
- Output ONLY the JSON object, no markdown, no commentary
"""