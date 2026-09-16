# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for MapMakerAgent dual-layer rendering."""

import base64
import json

import pytest

from app.agents.map_maker import MapMakerAgent, MapLayout, MapRoom


LAYOUT_JSON = json.dumps(
    {
        "width": 10,
        "height": 8,
        "rooms": [{"x": 1, "y": 1, "w": 4, "h": 3, "name": "Tavern"}],
        "secret_features": [
            {"x": 6, "y": 2, "w": 1, "h": 1, "type": "trap", "name": "Pit"}
        ],
    }
)


class _FakeLlm:
    def __init__(self, payload: str):
        self._payload = payload

    async def generate(self, **kwargs):
        return self._payload


def _agent(payload: str = LAYOUT_JSON) -> MapMakerAgent:
    return MapMakerAgent(_FakeLlm(payload))


def _is_png(b64: str) -> bool:
    return base64.b64decode(b64)[:8] == b"\x89PNG\r\n\x1a\n"


class TestParseLayout:
    def test_parses_rooms_and_secrets(self):
        layout = _agent()._parse_layout(LAYOUT_JSON)
        assert layout is not None
        assert layout.width == 10
        assert layout.height == 8
        assert len(layout.rooms) == 1
        assert layout.rooms[0].name == "Tavern"
        assert len(layout.secret_features) == 1
        assert layout.secret_features[0].type == "trap"
        assert layout.secret_features[0].name == "Pit"

    def test_rejects_out_of_bounds_secret(self):
        bad = json.dumps(
            {
                "width": 5,
                "height": 5,
                "rooms": [],
                "secret_features": [
                    {"x": 9, "y": 9, "w": 1, "h": 1, "type": "trap", "name": "Pit"}
                ],
            }
        )
        assert _agent()._parse_layout(bad) is None

    def test_missing_secrets_defaults_empty(self):
        bare = json.dumps(
            {
                "width": 5,
                "height": 5,
                "rooms": [{"x": 0, "y": 0, "w": 2, "h": 2, "name": "Hall"}],
            }
        )
        layout = _agent()._parse_layout(bare)
        assert layout is not None
        assert layout.secret_features == []


class TestDualLayerRender:
    @pytest.mark.asyncio
    async def test_build_returns_dual_png_payload(self):
        result = await _agent().build("A tavern with a pit trap")
        assert result.valid is True
        assert result.gm_base64_png is not None
        assert result.player_base64_png is not None
        assert _is_png(result.gm_base64_png)
        assert _is_png(result.player_base64_png)
        assert result.layout is not None
        assert result.layout.width == 10
        assert result.layout.height == 8

    @pytest.mark.asyncio
    async def test_gm_differs_from_player_with_secrets(self):
        result = await _agent().build("A tavern with a pit trap")
        assert result.gm_base64_png != result.player_base64_png

    def test_identical_without_rooms_or_secrets(self):
        agent = _agent()
        layout = MapLayout(width=4, height=4, rooms=[], secret_features=[])
        gm_b64, player_b64 = agent.render(layout, grid_enabled=True)
        assert gm_b64 == player_b64

    def test_grid_toggle_changes_pixels(self):
        agent = _agent()
        layout = MapLayout(width=4, height=4, rooms=[], secret_features=[])
        _, with_grid = agent.render(layout, grid_enabled=True)
        _, without_grid = agent.render(layout, grid_enabled=False)
        assert with_grid != without_grid

    def test_room_labels_only_on_gm(self):
        agent = _agent()
        layout = MapLayout(
            width=6,
            height=6,
            rooms=[MapRoom(x=1, y=1, w=3, h=3, name="Vault")],
            secret_features=[],
        )
        gm_b64, player_b64 = agent.render(layout, grid_enabled=False)
        assert gm_b64 != player_b64
