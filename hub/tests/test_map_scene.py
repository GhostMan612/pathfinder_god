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


class TestPlayableMapAndTokens:
    def test_corridors_doors_walkable_spawn_exit_and_connectivity(self):
        layout = _agent()._parse_layout(LAYOUT_JSON)
        assert layout is not None
        scene = MapMakerAgent.derive_scene(layout)
        assert scene.connected is True
        assert scene.spawn is not None
        assert scene.exit is not None
        assert (scene.spawn.x, scene.spawn.y) != (scene.exit.x, scene.exit.y)
        assert scene.walkable[scene.spawn.y][scene.spawn.x] == 1
        assert scene.walkable[scene.exit.y][scene.exit.x] == 1
        assert len(scene.corridors) >= 1
        assert len(scene.doors) >= 2
        for door in scene.doors:
            assert door.orientation in ("ns", "ew")
            assert scene.walkable[door.y][door.x] == 1
        reachable = MapMakerAgent._reachable_from(
            (scene.spawn.x, scene.spawn.y), scene.walkable
        )
        assert (scene.exit.x, scene.exit.y) in reachable
        for tok in scene.tokens:
            assert scene.walkable[tok.y][tok.x] == 1
            assert (tok.x, tok.y) in reachable
            assert tok.kind in (
                "hero",
                "monster",
                "npc",
                "loot",
                "door",
                "trap",
            )
            assert tok.z > 0

    def test_links_encounters_npcs_and_loot_to_3d_tokens(self):
        layout = _agent()._parse_layout(LAYOUT_JSON)
        assert layout is not None
        scene = MapMakerAgent.derive_scene(
            layout,
            heroes=["SAMPLE HERO"],
            monsters=["SAMPLE GOBLIN", "SAMPLE WOLF"],
            npcs=["SAMPLE ELDER"],
            loot=["Runed Greatsword", "Ruby Chalice"],
        )
        by_kind: dict[str, list[str]] = {}
        coords: set[tuple[int, int]] = set()
        entity_tokens = 0
        for tok in scene.tokens:
            by_kind.setdefault(tok.kind, []).append(tok.name)
            assert scene.walkable[tok.y][tok.x] == 1
            if tok.kind in ("hero", "monster", "npc", "loot"):
                coords.add((tok.x, tok.y))
                entity_tokens += 1
        assert by_kind["hero"] == ["SAMPLE HERO"]
        assert by_kind["monster"] == ["SAMPLE GOBLIN", "SAMPLE WOLF"]
        assert by_kind["npc"] == ["SAMPLE ELDER"]
        assert by_kind["loot"] == ["Runed Greatsword", "Ruby Chalice"]
        assert len(coords) == entity_tokens
        hero_tok = next(t for t in scene.tokens if t.kind == "hero")
        assert (hero_tok.x, hero_tok.y) == (scene.spawn.x, scene.spawn.y)

    @pytest.mark.asyncio
    async def test_campaign_entities_linked_into_map_tokens(self, tmp_path):
        from app.db.repository import CampaignRepository

        repo = CampaignRepository(str(tmp_path / "campaign.db"))
        campaign = repo.create_campaign("SAMPLE CAMPAIGN")
        cid = campaign.id
        repo.upsert_party_member(cid, name="SAMPLE HERO", class_="Fighter", level=2)
        repo.add_combatant(cid, name="SAMPLE GOBLIN", kind="monster", hp=12, max_hp=12, ac=16)
        repo.upsert_npc(cid, name="SAMPLE SHOPKEEP", role="ally")
        repo.upsert_quest(
            cid,
            name="Recover the Relic",
            status="active",
            objectives=[{"description": "Open the vault"}],
            rewards=[{"description": "Sunblade"}],
        )
        heroes, monsters, npcs, loot = MapMakerAgent.entities_from_campaign(repo, cid)
        assert heroes == ["SAMPLE HERO"]
        assert monsters == ["SAMPLE GOBLIN"]
        assert npcs == ["SAMPLE SHOPKEEP"]
        assert loot == ["Sunblade"]
        result = await _agent().build(
            "A tavern and vault",
            heroes=heroes,
            monsters=monsters,
            npcs=npcs,
            loot=loot,
        )
        assert result.valid is True
        assert result.scene is not None
        names = {(t.kind, t.name) for t in result.scene.tokens}
        assert ("hero", "SAMPLE HERO") in names
        assert ("monster", "SAMPLE GOBLIN") in names
        assert ("npc", "SAMPLE SHOPKEEP") in names
        assert ("loot", "Sunblade") in names
