# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

import json

import pytest

from app.agents.map_maker import MapLayout, MapMakerAgent, MapRoom

LAYOUT_JSON = json.dumps(
    {
        "width": 10,
        "height": 8,
        "rooms": [
            {"x": 1, "y": 1, "w": 4, "h": 3, "name": "Tavern"},
            {"x": 6, "y": 2, "w": 3, "h": 3, "name": "Vault"},
        ],
        "secret_features": [],
    }
)


class _FakeLlm:
    def __init__(self, payload: str):
        self._payload = payload

    async def generate(self, **kwargs):
        return self._payload


def _agent(payload: str = LAYOUT_JSON) -> MapMakerAgent:
    return MapMakerAgent(_FakeLlm(payload))


class TestDeriveScene:
    def test_heightmap_dimensions_and_wall_ring(self):
        layout = _agent()._parse_layout(LAYOUT_JSON)
        assert layout is not None
        scene = MapMakerAgent.derive_scene(layout)
        assert scene.grid.w == 10
        assert scene.grid.h == 8
        assert scene.grid.tile_m == 1.0
        assert len(scene.heightmap) == 8
        assert all(len(row) == 10 for row in scene.heightmap)
        assert scene.heightmap[1][1] == 3
        assert scene.heightmap[2][2] == 1
        assert scene.heightmap[0][0] == 0

    def test_deterministic_same_layout_same_scene(self):
        layout = _agent()._parse_layout(LAYOUT_JSON)
        assert layout is not None
        first = MapMakerAgent.derive_scene(layout)
        second = MapMakerAgent.derive_scene(layout)
        assert first.heightmap == second.heightmap
        assert [(p.type, p.x, p.y, p.rot) for p in first.props] == [
            (p.type, p.x, p.y, p.rot) for p in second.props
        ]
        assert first.zones == second.zones

    def test_props_closed_enum_and_lights_capped(self):
        layout = _agent()._parse_layout(LAYOUT_JSON)
        assert layout is not None
        scene = MapMakerAgent.derive_scene(layout)
        assert scene.props
        for prop in scene.props:
            assert prop.type in ("crate", "brazier", "pillar", "chest", "barrel", "altar")
            assert prop.rot in (0, 90, 180, 270)
            assert 0 <= prop.x < layout.width
            assert 0 <= prop.y < layout.height
        assert len(scene.lights) <= 8
        assert len(scene.props) <= 8

    def test_zones_carry_room_names_and_rects(self):
        layout = _agent()._parse_layout(LAYOUT_JSON)
        assert layout is not None
        scene = MapMakerAgent.derive_scene(layout)
        assert [z.name for z in scene.zones] == ["Tavern", "Vault"]
        assert scene.zones[0].biome == "tavern"
        assert scene.zones[1].biome == "vault"
        assert list(scene.zones[0].rect) == [1, 1, 4, 3]

    def test_empty_layout_no_fog_no_props(self):
        layout = MapLayout(width=4, height=4, rooms=[], secret_features=[])
        scene = MapMakerAgent.derive_scene(layout)
        assert scene.fog is None
        assert scene.props == []
        assert scene.lights == []
        assert all(cell == 0 for row in scene.heightmap for cell in row)


class TestBuildScene:
    @pytest.mark.asyncio
    async def test_build_returns_scene_alongside_pngs(self):
        result = await _agent().build("A tavern")
        assert result.valid is True
        assert result.scene is not None
        assert result.scene.grid.w == 10
        assert result.gm_base64_png is not None

    def test_wall_ring_survives_render_path(self):
        layout = MapLayout(
            width=6,
            height=6,
            rooms=[MapRoom(x=1, y=1, w=3, h=3, name="Vault")],
            secret_features=[],
        )
        scene = MapMakerAgent.derive_scene(layout)
        walls = sum(1 for row in scene.heightmap for cell in row if cell >= 3)
        assert walls >= 8
        gm_b64, player_b64 = _agent().render(layout, grid_enabled=False)
        assert gm_b64 is not None and player_b64 is not None
