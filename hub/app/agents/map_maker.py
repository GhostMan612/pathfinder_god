# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Map Maker Agent — LLM map design + dual-layer Pillow rendering.

Generates print-ready battle maps from natural language: a Player view
(public geometry only) and a GM view (labels plus secret features).
"""

from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.llm.ollama_client import OllamaClient

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

logger = logging.getLogger(__name__)

CELL_SIZE = 50


@dataclass
class MapRoom:
    x: int
    y: int
    w: int
    h: int
    name: str


@dataclass
class MapSecretFeature:
    x: int
    y: int
    w: int
    h: int
    type: str
    name: str


@dataclass
class MapLayout:
    width: int
    height: int
    rooms: list[MapRoom]
    secret_features: list[MapSecretFeature]


@dataclass
class BuildResult:
    valid: bool
    layout: MapLayout | None
    gm_base64_png: str | None
    player_base64_png: str | None
    error: str | None


SYSTEM_PROMPT = """You are a Pathfinder 2e battle map designer.
Given a user prompt describing a location, output a JSON object with:
- width: grid width in squares (1-50)
- height: grid height in squares (1-50)
- rooms: array of PUBLIC geometry objects with x, y, w, h (all ints, grid coordinates), name (string)
- secret_features: array of HIDDEN objects with x, y, w, h (all ints, grid coordinates), type (string, e.g. "trap", "secret door", "hidden treasure"), name (string, e.g. "Pit")

Rules:
- Coordinates are 0-indexed from top-left
- Rooms and secret features must not exceed map bounds
- Rooms should be rectangular
- Total area of rooms should not exceed map area
- Designate every feature as "public" (goes in rooms) or "secret" (goes in secret_features): secret doors, hidden traps, concealed treasures and spy holes are secret; everything the party can see is public
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
            if not (1 <= width <= 50 and 1 <= height <= 50):
                return None
            rooms_data = data.get("rooms", [])
            secrets_data = data.get("secret_features", [])
            rooms = []
            for r in rooms_data:
                if not self._fits_bounds(r, width, height):
                    return None
                rooms.append(
                    MapRoom(
                        x=int(r["x"]),
                        y=int(r["y"]),
                        w=int(r["w"]),
                        h=int(r["h"]),
                        name=str(r.get("name", "Room")),
                    )
                )
            secrets = []
            for s in secrets_data:
                if not self._fits_bounds(s, width, height):
                    return None
                secrets.append(
                    MapSecretFeature(
                        x=int(s["x"]),
                        y=int(s["y"]),
                        w=int(s["w"]),
                        h=int(s["h"]),
                        type=str(s.get("type", "trap")),
                        name=str(s.get("name", "Secret")),
                    )
                )
            return MapLayout(
                width=width,
                height=height,
                rooms=rooms,
                secret_features=secrets,
            )
        except (KeyError, ValueError, TypeError):
            return None

    @staticmethod
    def _fits_bounds(item: Any, width: int, height: int) -> bool:
        try:
            x, y, w, h = int(item["x"]), int(item["y"]), int(item["w"]), int(item["h"])
        except (KeyError, ValueError, TypeError):
            return False
        if not (0 <= x < width and 0 <= y < height):
            return False
        if not (1 <= w <= width and 1 <= h <= height):
            return False
        return 0 <= x + w <= width and 0 <= y + h <= height

    @staticmethod
    def _load_font() -> Any:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", 12)
        except Exception:
            try:
                return ImageFont.load_default()
            except Exception:
                return None

    @staticmethod
    def _encode(img: Any) -> str:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("ascii")

    def _base_image(self, layout: MapLayout, grid_enabled: bool) -> Any:
        width_px = layout.width * CELL_SIZE
        height_px = layout.height * CELL_SIZE

        img = Image.new("RGBA", (width_px, height_px), (0x1E, 0x1B, 0x18, 0xFF))
        draw = ImageDraw.Draw(img)

        if grid_enabled:
            grid_color = (0xD4, 0xAF, 0x37, 0x33)
            for x in range(0, width_px + 1, CELL_SIZE):
                draw.line([(x, 0), (x, height_px)], fill=grid_color, width=1)
            for y in range(0, height_px + 1, CELL_SIZE):
                draw.line([(0, y), (width_px, y)], fill=grid_color, width=1)

        room_fill = (0x28, 0x24, 0x1F, 0xE6)
        room_border = (0xD4, 0xAF, 0x37, 0xFF)

        for room in layout.rooms:
            x0 = room.x * CELL_SIZE
            y0 = room.y * CELL_SIZE
            x1 = (room.x + room.w) * CELL_SIZE
            y1 = (room.y + room.h) * CELL_SIZE
            draw.rectangle([x0, y0, x1, y1], fill=room_fill)
            draw.rectangle([x0, y0, x1, y1], outline=room_border, width=3)

        return img

    def _overlay_gm_layer(self, img: Any, layout: MapLayout) -> None:
        draw = ImageDraw.Draw(img)
        font = self._load_font()
        secret_fill = (0x7B, 0x1E, 0x1E, 0xB4)
        secret_border = (0x7B, 0x1E, 0x1E, 0xFF)

        for room in layout.rooms:
            self._label(
                draw,
                font,
                room.x * CELL_SIZE,
                room.y * CELL_SIZE,
                room.w * CELL_SIZE,
                room.h * CELL_SIZE,
                room.name,
                (0xD4, 0xAF, 0x37, 0xFF),
            )

        for secret in layout.secret_features:
            x0 = secret.x * CELL_SIZE
            y0 = secret.y * CELL_SIZE
            x1 = (secret.x + secret.w) * CELL_SIZE
            y1 = (secret.y + secret.h) * CELL_SIZE
            draw.rectangle([x0, y0, x1, y1], fill=secret_fill)
            draw.rectangle([x0, y0, x1, y1], outline=secret_border, width=2)
            self._label(
                draw,
                font,
                x0,
                y0,
                secret.w * CELL_SIZE,
                secret.h * CELL_SIZE,
                f"{secret.type}: {secret.name}",
                (0xFF, 0xE0, 0xE0, 0xFF),
            )

    @staticmethod
    def _label(
        draw: Any,
        font: Any,
        x0: int,
        y0: int,
        w_px: int,
        h_px: int,
        text: str,
        fill: tuple[int, int, int, int],
    ) -> None:
        if not text or font is None:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        tx = x0 + (w_px - text_w) // 2
        ty = y0 + (h_px - text_h) // 2
        draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0, 200), font=font)
        draw.text((tx, ty), text, fill=fill, font=font)

    def render(
        self, layout: MapLayout, grid_enabled: bool = True
    ) -> tuple[str, str]:
        if Image is None:
            raise RuntimeError("Pillow not available")
        player = self._base_image(layout, grid_enabled)
        player_b64 = self._encode(player)
        gm = player.copy()
        self._overlay_gm_layer(gm, layout)
        gm_b64 = self._encode(gm)
        return gm_b64, player_b64

    async def build(self, prompt: str, grid_enabled: bool = True) -> BuildResult:
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
            return BuildResult(False, None, None, None, f"LLM generation failed: {e}")

        layout = self._parse_layout(raw)
        if layout is None:
            return BuildResult(
                False, None, None, None, "LLM returned invalid JSON or invalid layout"
            )

        try:
            gm_b64, player_b64 = self.render(layout, grid_enabled)
        except Exception as e:
            logger.error(f"Map rendering failed: {e}")
            return BuildResult(False, None, None, None, f"Map rendering failed: {e}")

        return BuildResult(
            valid=True,
            layout=layout,
            gm_base64_png=gm_b64,
            player_base64_png=player_b64,
            error=None,
        )
