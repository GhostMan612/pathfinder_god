# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Map Maker Agent â€” LLM map design + dual-layer Pillow rendering.

Generates print-ready battle maps from natural language: a Player view
(public geometry only) and a GM view (labels plus secret features).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

from app.agents.json_builder import generate_validated_json
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

PROP_TYPES = ("crate", "brazier", "pillar", "chest", "barrel", "altar")
TOKEN_KINDS = ("hero", "monster", "npc", "loot")
TOKEN_COLORS = {
    "hero": "#3b82f6",
    "monster": "#dc2626",
    "npc": "#22c55e",
    "loot": "#eab308",
}


@dataclass
class MapPoint:
    x: int
    y: int


@dataclass
class MapDoor:
    x: int
    y: int
    orientation: str = "ew"
    kind: str = "wood"


@dataclass
class MapCorridor:
    cells: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class MapToken:
    id: str
    name: str
    kind: str
    x: int
    y: int
    z: float = 0.5
    color: str = "#d4af37"
    # Populated when a map is generated for an active battle. The token keeps
    # its own grid cell; the IDs make the token addressable from the encounter
    # and combat state instead of matching by display name later.
    encounter_id: int | None = None
    combatant_id: int | None = None


@dataclass
class MapProp:
    type: str
    x: int
    y: int
    rot: int
    scale: float = 1.0


@dataclass
class MapLight:
    x: int
    y: int
    color: str
    radius_m: float


@dataclass
class MapZone:
    name: str
    biome: str
    rect: tuple[int, int, int, int]


@dataclass
class MapFog:
    color: str
    density: float


@dataclass
class MapGrid:
    w: int
    h: int
    tile_m: float


@dataclass
class MapScene:
    grid: MapGrid
    heightmap: list[list[int]]
    zones: list[MapZone]
    props: list[MapProp]
    lights: list[MapLight]
    fog: MapFog | None
    walkable: list[list[int]] = field(default_factory=list)
    doors: list[MapDoor] = field(default_factory=list)
    corridors: list[MapCorridor] = field(default_factory=list)
    spawn: MapPoint | None = None
    exit: MapPoint | None = None
    tokens: list[MapToken] = field(default_factory=list)
    connected: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return the complete wire/scene shape, including token links."""
        return asdict(self)


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
    scene: MapScene | None = None
    attempts: int = 1


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
        from app.agents.continuity import parse_json_loose

        data = parse_json_loose(raw)
        if not isinstance(data, dict):
            return None
        return self._layout_from_data(data)

    def _layout_from_data(self, data: dict) -> MapLayout | None:
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
    def _seed_for(layout: MapLayout) -> int:
        import hashlib

        payload = json.dumps(
            {
                "width": layout.width,
                "height": layout.height,
                "rooms": [
                    {"x": r.x, "y": r.y, "w": r.w, "h": r.h, "name": r.name}
                    for r in layout.rooms
                ],
            },
            sort_keys=True,
        ).encode("utf-8")
        return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")

    @staticmethod
    def _room_center(room: MapRoom) -> tuple[int, int]:
        cx = min(
            max(room.x + room.w // 2, room.x + min(1, room.w - 1)),
            room.x + max(0, room.w - 2),
        )
        cy = min(
            max(room.y + room.h // 2, room.y + min(1, room.h - 1)),
            room.y + max(0, room.h - 2),
        )
        return cx, cy

    @staticmethod
    def _room_walkable_cells(
        room: MapRoom, walkable: list[list[int]]
    ) -> list[tuple[int, int]]:
        cells: list[tuple[int, int]] = []
        for dy in range(room.h):
            for dx in range(room.w):
                gx, gy = room.x + dx, room.y + dy
                if walkable[gy][gx] == 1:
                    cells.append((gx, gy))
        return cells

    @staticmethod
    def _step_line(
        x0: int, y0: int, x1: int, y1: int
    ) -> list[tuple[int, int]]:
        pts: list[tuple[int, int]] = [(x0, y0)]
        cx, cy = x0, y0
        while cx != x1:
            cx += 1 if x1 > cx else -1
            pts.append((cx, cy))
        while cy != y1:
            cy += 1 if y1 > cy else -1
            pts.append((cx, cy))
        return pts

    @classmethod
    def _corridor_path(
        cls, r0: MapRoom, r1: MapRoom, width: int, height: int
    ) -> list[tuple[int, int]]:
        cx0, cy0 = cls._room_center(r0)
        cx1, cy1 = cls._room_center(r1)
        if abs(cx1 - cx0) >= abs(cy1 - cy0):
            if r0.x + r0.w <= r1.x:
                mid_x = (r0.x + r0.w - 1 + r1.x) // 2
            elif r1.x + r1.w <= r0.x:
                mid_x = (r1.x + r1.w - 1 + r0.x) // 2
            else:
                mid_x = (cx0 + cx1) // 2
            mid_x = max(0, min(width - 1, mid_x))
            seg1 = cls._step_line(cx0, cy0, mid_x, cy0)
            seg2 = cls._step_line(mid_x, cy0, mid_x, cy1)[1:]
            seg3 = cls._step_line(mid_x, cy1, cx1, cy1)[1:]
            return seg1 + seg2 + seg3
        if r0.y + r0.h <= r1.y:
            mid_y = (r0.y + r0.h - 1 + r1.y) // 2
        elif r1.y + r1.h <= r0.y:
            mid_y = (r1.y + r1.h - 1 + r0.y) // 2
        else:
            mid_y = (cy0 + cy1) // 2
        mid_y = max(0, min(height - 1, mid_y))
        seg1 = cls._step_line(cx0, cy0, cx0, mid_y)
        seg2 = cls._step_line(cx0, mid_y, cx1, mid_y)[1:]
        seg3 = cls._step_line(cx1, mid_y, cx1, cy1)[1:]
        return seg1 + seg2 + seg3

    @staticmethod
    def _reachable_from(
        start: tuple[int, int], walkable: list[list[int]]
    ) -> set[tuple[int, int]]:
        h = len(walkable)
        w = len(walkable[0]) if h else 0
        sx, sy = start
        if not (0 <= sx < w and 0 <= sy < h) or walkable[sy][sx] == 0:
            return set()
        visited: set[tuple[int, int]] = {(sx, sy)}
        queue: deque[tuple[int, int]] = deque([(sx, sy)])
        while queue:
            cx, cy = queue.popleft()
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (
                    0 <= nx < w
                    and 0 <= ny < h
                    and walkable[ny][nx] == 1
                    and (nx, ny) not in visited
                ):
                    visited.add((nx, ny))
                    queue.append((nx, ny))
        return visited

    @classmethod
    def derive_scene(
        cls,
        layout: MapLayout,
        *,
        heroes: list[str] | None = None,
        monsters: list[str] | None = None,
        npcs: list[str] | None = None,
        loot: list[str] | None = None,
    ) -> MapScene:
        import random

        rng = random.Random(cls._seed_for(layout))
        heightmap = [[0 for _ in range(layout.width)] for _ in range(layout.height)]
        walkable = [[0 for _ in range(layout.width)] for _ in range(layout.height)]
        was_wall = [[False for _ in range(layout.width)] for _ in range(layout.height)]
        zones: list[MapZone] = []
        props: list[MapProp] = []
        lights: list[MapLight] = []
        doors: list[MapDoor] = []
        corridors: list[MapCorridor] = []
        door_coords: set[tuple[int, int]] = set()

        for room in layout.rooms:
            for dy in range(room.h):
                for dx in range(room.w):
                    gx, gy = room.x + dx, room.y + dy
                    on_border = dx == 0 or dy == 0 or dx == room.w - 1 or dy == room.h - 1
                    heightmap[gy][gx] = 3 if on_border else 1
                    if on_border:
                        was_wall[gy][gx] = True
                    else:
                        walkable[gy][gx] = 1
            cx_room, cy_room = cls._room_center(room)
            walkable[cy_room][cx_room] = 1
            lowered = room.name.lower()
            if any(k in lowered for k in ("tavern", "inn", "warden", "guild")):
                biome = "tavern"
            elif any(k in lowered for k in ("crypt", "dungeon", "vault", "treasure")):
                biome = "vault"
            else:
                biome = "stone"
            zones.append(
                MapZone(
                    name=room.name,
                    biome=biome,
                    rect=(room.x, room.y, room.w, room.h),
                )
            )
            if room.w >= 2 and room.h >= 2 and len(props) < 8:
                cx = room.x + room.w // 2
                cy = room.y + room.h // 2
                prop_type = PROP_TYPES[len(props) % len(PROP_TYPES)]
                rot = rng.choice([0, 90, 180, 270])
                props.append(MapProp(type=prop_type, x=cx, y=cy, rot=rot, scale=1.0))
            if room.w >= 3 and room.h >= 3 and len(lights) < 8:
                lights.append(
                    MapLight(
                        x=room.x + room.w // 2,
                        y=room.y + room.h // 2,
                        color="#ff9a3c",
                        radius_m=3.0,
                    )
                )

        if len(layout.rooms) >= 2:
            for idx in range(len(layout.rooms) - 1):
                r0 = layout.rooms[idx]
                r1 = layout.rooms[idx + 1]
                path = cls._corridor_path(r0, r1, layout.width, layout.height)
                corridor_cells: list[tuple[int, int]] = []
                for step_idx, (px, py) in enumerate(path):
                    prev_wall = was_wall[py][px]
                    prev_empty = heightmap[py][px] == 0
                    walkable[py][px] = 1
                    heightmap[py][px] = 1
                    if prev_wall or prev_empty:
                        corridor_cells.append((px, py))
                    if prev_wall and (px, py) not in door_coords:
                        orientation = "ew"
                        if step_idx > 0:
                            prev_x, prev_y = path[step_idx - 1]
                            if prev_y != py:
                                orientation = "ns"
                        door_coords.add((px, py))
                        doors.append(
                            MapDoor(x=px, y=py, orientation=orientation, kind="wood")
                        )
                if corridor_cells:
                    corridors.append(MapCorridor(cells=corridor_cells))
        elif len(layout.rooms) == 1:
            r0 = layout.rooms[0]
            dx = r0.w // 2
            dy = r0.h - 1
            gx, gy = r0.x + dx, r0.y + dy
            walkable[gy][gx] = 1
            if (gx, gy) not in door_coords:
                door_coords.add((gx, gy))
                doors.append(MapDoor(x=gx, y=gy, orientation="ns", kind="wood"))

        for secret in layout.secret_features:
            if "door" in secret.type.lower():
                walkable[secret.y][secret.x] = 1
                if (secret.x, secret.y) not in door_coords:
                    door_coords.add((secret.x, secret.y))
                    doors.append(
                        MapDoor(
                            x=secret.x,
                            y=secret.y,
                            orientation="ew",
                            kind="secret",
                        )
                    )

        spawn: MapPoint | None = None
        exit_pt: MapPoint | None = None
        tokens: list[MapToken] = []
        connected = True

        if layout.rooms:
            prop_cells = {(p.x, p.y) for p in props}
            r0_walk = cls._room_walkable_cells(layout.rooms[0], walkable)
            sx, sy = next(
                (pt for pt in r0_walk if pt not in prop_cells),
                cls._room_center(layout.rooms[0]),
            )
            spawn = MapPoint(x=sx, y=sy)
            if len(layout.rooms) >= 2:
                rl_walk = cls._room_walkable_cells(layout.rooms[-1], walkable)
                ex, ey = next(
                    (pt for pt in reversed(rl_walk) if pt not in prop_cells),
                    cls._room_center(layout.rooms[-1]),
                )
                exit_pt = MapPoint(x=ex, y=ey)
            elif doors:
                exit_pt = MapPoint(x=doors[0].x, y=doors[0].y)
            else:
                exit_pt = MapPoint(x=sx, y=sy)

            all_walkable: list[tuple[int, int]] = [
                (x, y)
                for y in range(layout.height)
                for x in range(layout.width)
                if walkable[y][x] == 1
            ]
            if (
                exit_pt.x == spawn.x
                and exit_pt.y == spawn.y
                and len(all_walkable) >= 2
            ):
                alt = next(
                    (pt for pt in reversed(all_walkable) if pt != (spawn.x, spawn.y)),
                    (spawn.x, spawn.y),
                )
                exit_pt = MapPoint(x=alt[0], y=alt[1])

            used_cells: set[tuple[int, int]] = set()

            def _pick_cell(
                preferred: list[tuple[int, int]],
            ) -> tuple[int, int]:
                for pool in (preferred, all_walkable):
                    for candidate in pool:
                        if candidate not in used_cells and candidate not in prop_cells:
                            used_cells.add(candidate)
                            return candidate
                    for candidate in pool:
                        if candidate not in used_cells:
                            used_cells.add(candidate)
                            return candidate
                fallback = preferred[0] if preferred else (spawn.x, spawn.y)
                used_cells.add(fallback)
                return fallback

            room0_cells = [(spawn.x, spawn.y)] + [
                pt
                for pt in cls._room_walkable_cells(layout.rooms[0], walkable)
                if pt != (spawn.x, spawn.y)
            ]
            later_rooms = layout.rooms[1:] if len(layout.rooms) >= 2 else layout.rooms
            encounter_cells: list[tuple[int, int]] = []
            for rm in later_rooms:
                for pt in cls._room_walkable_cells(rm, walkable):
                    if pt != (spawn.x, spawn.y) and pt not in encounter_cells:
                        encounter_cells.append(pt)
            vault_cells = [
                pt
                for pt in cls._room_walkable_cells(layout.rooms[-1], walkable)
                if pt != (spawn.x, spawn.y)
            ]

            hero_list = list(heroes) if heroes is not None else ["Hero"]
            if npcs is not None:
                npc_list = list(npcs)
            else:
                npc_list = [
                    f"{r.name} Keeper"
                    for r in layout.rooms
                    if any(
                        k in r.name.lower()
                        for k in ("tavern", "inn", "warden", "guild", "hall", "shop")
                    )
                ][:2]
                if not npc_list:
                    npc_list = [f"{layout.rooms[0].name} Guide"]

            if monsters is not None:
                monster_list = list(monsters)
            else:
                monster_list = [
                    f"{r.name} Guardian"
                    for r in later_rooms
                    if not any(k in r.name.lower() for k in ("tavern", "inn"))
                ][:4]
                if not monster_list:
                    monster_list = [f"{layout.rooms[-1].name} Ambush"]

            if loot is not None:
                loot_list = list(loot)
            else:
                loot_list = [
                    s.name
                    for s in layout.secret_features
                    if any(
                        k in s.type.lower()
                        for k in ("treasure", "loot", "chest", "hoard")
                    )
                ]
                if not loot_list:
                    loot_list = [f"{layout.rooms[-1].name} Cache"]

            for idx_h, h_name in enumerate(hero_list):
                tx, ty = _pick_cell(room0_cells)
                tokens.append(
                    MapToken(
                        id=f"hero-{idx_h + 1}",
                        name=h_name,
                        kind="hero",
                        x=tx,
                        y=ty,
                        z=round(max(1, heightmap[ty][tx]) * 0.5, 2),
                        color=TOKEN_COLORS["hero"],
                    )
                )

            for idx_n, n_name in enumerate(npc_list):
                tx, ty = _pick_cell(room0_cells[1:] or room0_cells)
                tokens.append(
                    MapToken(
                        id=f"npc-{idx_n + 1}",
                        name=n_name,
                        kind="npc",
                        x=tx,
                        y=ty,
                        z=round(max(1, heightmap[ty][tx]) * 0.5, 2),
                        color=TOKEN_COLORS["npc"],
                    )
                )

            for idx_m, m_name in enumerate(monster_list):
                tx, ty = _pick_cell(encounter_cells or room0_cells)
                tokens.append(
                    MapToken(
                        id=f"monster-{idx_m + 1}",
                        name=m_name,
                        kind="monster",
                        x=tx,
                        y=ty,
                        z=round(max(1, heightmap[ty][tx]) * 0.5, 2),
                        color=TOKEN_COLORS["monster"],
                    )
                )

            for idx_l, l_name in enumerate(loot_list):
                tx, ty = _pick_cell(vault_cells or encounter_cells or room0_cells)
                tokens.append(
                    MapToken(
                        id=f"loot-{idx_l + 1}",
                        name=l_name,
                        kind="loot",
                        x=tx,
                        y=ty,
                        z=round(max(1, heightmap[ty][tx]) * 0.5, 2),
                        color=TOKEN_COLORS["loot"],
                    )
                )

            reachable = cls._reachable_from((spawn.x, spawn.y), walkable)
            required_pts = {(spawn.x, spawn.y), (exit_pt.x, exit_pt.y)}
            for rm in layout.rooms:
                required_pts.add(cls._room_center(rm))
            for tok in tokens:
                required_pts.add((tok.x, tok.y))
            connected = required_pts.issubset(reachable)

        fog = MapFog(color="#0a0d14", density=0.02) if layout.rooms else None
        return MapScene(
            grid=MapGrid(w=layout.width, h=layout.height, tile_m=1.0),
            heightmap=heightmap,
            zones=zones,
            props=props,
            lights=lights,
            fog=fog,
            walkable=walkable,
            doors=doors,
            corridors=corridors,
            spawn=spawn,
            exit=exit_pt,
            tokens=tokens,
            connected=connected,
        )

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

    @staticmethod
    def entities_from_campaign(
        repo: Any, campaign_id: int
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        if repo is None or not repo.campaign_exists(campaign_id):
            return [], [], [], []
        snap = repo.get_campaign_snapshot(campaign_id)
        combatants = repo.get_combatants(campaign_id, active_only=True)
        heroes = [c.name for c in combatants if c.kind == "hero"]
        if not heroes:
            heroes = [
                str(p.get("name"))
                for p in snap.get("party", [])
                if p.get("name")
            ]
        monsters = [c.name for c in combatants if c.kind == "monster"]
        npcs = [
            str(n.get("name"))
            for n in snap.get("npcs", [])
            if n.get("name") and str(n.get("name")) not in heroes
        ]
        for c in combatants:
            if c.kind == "npc" and c.name not in npcs:
                npcs.append(c.name)
        loot: list[str] = [
            str(it.get("name"))
            for it in snap.get("items", [])
            if it.get("name")
        ]
        for q in snap.get("quests", []):
            for rw in q.get("rewards", []) or []:
                desc = rw.get("description") if isinstance(rw, dict) else str(rw)
                if desc and desc not in loot:
                    loot.append(str(desc))
        return heroes, monsters, npcs, loot

    @staticmethod
    def link_tokens_to_combatants(
        scene: MapScene,
        encounter_id: int,
        combatants: list[Any],
    ) -> int:
        """Attach encounter/combatant IDs to matching scene tokens.

        The map generator emits tokens in the same kind/name order as the
        campaign entity lists. Matching on ``(kind, name)`` with a FIFO queue
        therefore assigns distinct IDs to duplicate monster names instead of
        collapsing every copy onto the first combatant row. Tokens without an
        active combatant (loot, scenery NPCs) keep ``combatant_id=None``.
        Returns the number of linked tokens.
        """
        available: dict[tuple[str, str], deque[int]] = {}
        for combatant in combatants:
            kind = getattr(combatant, "kind", None)
            name = getattr(combatant, "name", None)
            combatant_id = getattr(combatant, "id", None)
            if kind not in TOKEN_KINDS or name is None or combatant_id is None:
                continue
            available.setdefault((str(kind), str(name)), deque()).append(
                int(combatant_id)
            )

        linked = 0
        for token in scene.tokens:
            queue = available.get((token.kind, token.name))
            if not queue:
                continue
            token.encounter_id = encounter_id
            token.combatant_id = queue.popleft()
            linked += 1
        return linked

    async def build(
        self,
        prompt: str,
        grid_enabled: bool = True,
        *,
        heroes: list[str] | None = None,
        monsters: list[str] | None = None,
        npcs: list[str] | None = None,
        loot: list[str] | None = None,
    ) -> BuildResult:
        full_prompt = SYSTEM_PROMPT + "\n\nUser request: " + prompt.strip()
        validated: dict[str, MapLayout] = {}

        def _validate(data: object) -> list[str]:
            if not isinstance(data, dict):
                return ["LLM returned a JSON value that is not an object"]
            layout = self._layout_from_data(data)
            if layout is None:
                return ["LLM returned invalid JSON or invalid layout"]
            validated["layout"] = layout
            return []

        outcome = await generate_validated_json(
            self._llm,
            prompt=full_prompt,
            model=self._settings.model_for("builders"),
            temperature=0.3,
            num_predict=800,
            validate=_validate,
        )
        if outcome.data is None or "layout" not in validated:
            logger.error("MapMaker LLM failed: %s", "; ".join(outcome.errors))
            return BuildResult(
                False, None, None, None,
                "; ".join(outcome.errors) or "LLM returned invalid JSON or invalid layout",
                attempts=outcome.attempts,
            )
        layout = validated["layout"]

        try:
            # render() is fully synchronous Pillow work - two 2500x2500 RGBA
            # images plus PNG encoding, measured at 318 ms - called directly
            # from an async def. That blocked the event loop for a third of a
            # second per map request, stalling /health and every WS stream.
            gm_b64, player_b64 = await asyncio.to_thread(
                self.render, layout, grid_enabled
            )
        except Exception as e:
            logger.error(f"Map rendering failed: {e}")
            return BuildResult(False, None, None, None, f"Map rendering failed: {e}", attempts=outcome.attempts)

        return BuildResult(
            valid=True,
            layout=layout,
            gm_base64_png=gm_b64,
            player_base64_png=player_b64,
            error=None,
            scene=self.derive_scene(
                layout,
                heroes=heroes,
                monsters=monsters,
                npcs=npcs,
                loot=loot,
            ),
            attempts=outcome.attempts,
        )

