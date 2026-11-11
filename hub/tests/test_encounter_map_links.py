# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Encounter-to-map links: token IDs, cell coordinates, and persistence.

The map generator already emits deterministic token positions. These tests pin
the next layer: battle tokens carry the encounter and combatant IDs they belong
to, and the linked scene is stored on the encounter instead of disappearing with
the HTTP response. No LLM is involved.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.map_maker import (
    BuildResult,
    MapLayout,
    MapMakerAgent,
    MapRoom,
    MapSecretFeature,
)
from app.agents.solo_loop import SoloLoop
from app.db.repository import CampaignRepository
from app.llm.orchestrator import LLMOrchestrator

LAYOUT = MapLayout(
    width=10,
    height=8,
    rooms=[
        MapRoom(x=1, y=1, w=4, h=3, name="Tavern"),
        MapRoom(x=6, y=2, w=3, h=3, name="Vault"),
    ],
    secret_features=[],
)


def _stats(kind: str, name: str, combatant_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=combatant_id, name=name, kind=kind)


def test_link_tokens_assigns_distinct_combatant_ids_and_cells() -> None:
    scene = MapMakerAgent.derive_scene(
        LAYOUT,
        heroes=["SAMPLE HERO", "SAMPLE HERO"],
        monsters=["SAMPLE GOBLIN", "SAMPLE GOBLIN"],
        npcs=["SAMPLE ELDER"],
        loot=["Sample Gem"],
    )
    combatants = [
        _stats("hero", "SAMPLE HERO", 11),
        _stats("hero", "SAMPLE HERO", 12),
        _stats("monster", "SAMPLE GOBLIN", 21),
        _stats("monster", "SAMPLE GOBLIN", 22),
        _stats("npc", "SAMPLE ELDER", 31),
    ]

    linked = MapMakerAgent.link_tokens_to_combatants(scene, 77, combatants)

    assert linked == 5
    assert [t.combatant_id for t in scene.tokens if t.kind == "hero"] == [11, 12]
    assert [t.combatant_id for t in scene.tokens if t.kind == "monster"] == [21, 22]
    assert [t.combatant_id for t in scene.tokens if t.kind == "npc"] == [31]
    for token in scene.tokens:
        assert token.x >= 0 and token.y >= 0
        if token.kind in ("hero", "monster", "npc"):
            assert token.encounter_id == 77
        else:
            assert token.encounter_id is None
            assert token.combatant_id is None


def test_attach_encounter_map_preserves_existing_state(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    encounter = repo.create_encounter(
        campaign.id,
        "battle",
        summary="SAMPLE BATTLE",
        state={"round": 3, "combatant_ids": [11, 12]},
    )
    map_state = {
        "encounter_id": encounter.id,
        "grid": {"w": 10, "h": 8, "tile_m": 1.0},
        "linked_token_count": 1,
        "linked_tokens": [
            {"id": "hero-1", "combatant_id": 11, "x": 1, "y": 1}
        ],
    }

    updated = repo.attach_encounter_map(campaign.id, encounter.id, map_state)

    assert updated.status == "pending"
    assert updated.state["round"] == 3
    assert updated.state["combatant_ids"] == [11, 12]
    stored = repo.get_encounter(campaign.id, encounter.id)
    assert stored is not None
    assert stored.state["map"] == map_state

    with pytest.raises(ValueError, match="no encounter"):
        repo.attach_encounter_map(campaign.id, 99999, map_state)


@pytest.mark.asyncio
async def test_generate_map_tool_links_active_battle(
    tmp_path: Path, monkeypatch
) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    loop = SoloLoop(repo)
    started = await loop.start_combat(campaign.id, seed=3)
    combatants = repo.get_combatants(campaign.id, active_only=True)
    scene = MapMakerAgent.derive_scene(
        LAYOUT,
        heroes=[c.name for c in combatants if c.kind == "hero"],
        monsters=[c.name for c in combatants if c.kind == "monster"],
        npcs=[],
        loot=[],
    )

    async def fake_build(
        self,
        prompt: str,
        grid_enabled: bool = True,
        *,
        heroes=None,
        monsters=None,
        npcs=None,
        loot=None,
    ) -> BuildResult:
        return BuildResult(
            valid=True,
            layout=LAYOUT,
            gm_base64_png=None,
            player_base64_png=None,
            error=None,
            scene=scene,
            attempts=1,
        )

    monkeypatch.setattr(MapMakerAgent, "build", fake_build)

    orchestrator = LLMOrchestrator(repo)
    result = await orchestrator.handle_tool_call(
        "generate_map", {"prompt": "SAMPLE CRYPT"}, campaign_id=campaign.id
    )

    assert result["encounter_id"] == started.encounter_id
    assert result["linked_token_count"] == len(combatants)
    linked = [
        token
        for token in result["scene"]["tokens"]
        if token["combatant_id"] is not None
    ]
    assert {token["combatant_id"] for token in linked} == {c.id for c in combatants}
    encounter = repo.get_encounter(campaign.id, started.encounter_id)
    assert encounter is not None
    assert encounter.state["map"]["encounter_id"] == started.encounter_id
    assert encounter.state["map"]["linked_token_count"] == len(combatants)


@pytest.mark.asyncio
async def test_map_generate_links_active_battle_and_persists_scene(
    authenticated_client, monkeypatch
) -> None:
    from app.api.deps import get_repo

    get_repo.cache_clear()
    repo = get_repo()
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    loop = SoloLoop(repo)
    started = await loop.start_combat(campaign.id, seed=3)
    combatants = repo.get_combatants(campaign.id, active_only=True)
    scene = MapMakerAgent.derive_scene(
        LAYOUT,
        heroes=[c.name for c in combatants if c.kind == "hero"],
        monsters=[c.name for c in combatants if c.kind == "monster"],
        npcs=[],
        loot=["Sample Gem"],
    )

    async def fake_build(
        self,
        prompt: str,
        grid_enabled: bool = True,
        *,
        heroes=None,
        monsters=None,
        npcs=None,
        loot=None,
    ) -> BuildResult:
        return BuildResult(
            valid=True,
            layout=LAYOUT,
            gm_base64_png="Z20=",
            player_base64_png="cGxheWVy",
            error=None,
            scene=scene,
            attempts=1,
        )

    monkeypatch.setattr(MapMakerAgent, "build", fake_build)

    response = authenticated_client.post(
        "/map/generate",
        json={"prompt": "SAMPLE CRYPT", "campaign_id": campaign.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["encounter_id"] == started.encounter_id
    assert body["scene"] is not None

    tokens = body["scene"]["tokens"]
    linked_tokens = [t for t in tokens if t["combatant_id"] is not None]
    assert {"hero", "monster"} <= {t["kind"] for t in linked_tokens}
    assert {t["combatant_id"] for t in linked_tokens} == {
        c.id for c in combatants
    }
    assert all(t["encounter_id"] == started.encounter_id for t in linked_tokens)
    assert all(isinstance(t["x"], int) and isinstance(t["y"], int) for t in tokens)

    detail = authenticated_client.get(
        f"/campaign/{campaign.id}/encounters/{started.encounter_id}"
    )
    assert detail.status_code == 200, detail.text
    map_state = detail.json()["state"]["map"]
    assert map_state["encounter_id"] == started.encounter_id
    assert map_state["grid"]["w"] == LAYOUT.width
    assert map_state["linked_token_count"] == len(linked_tokens)
    assert {t["combatant_id"] for t in map_state["linked_tokens"]} == {
        c.id for c in combatants
    }
    assert map_state["scene"]["tokens"] == tokens


# ── Non-battle entity links ───────────────────────────────────

def _campaign(tmp_path: Path):
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town = repo.upsert_location(campaign.id, "SAMPLE TOWN", type_="settlement")
    other = repo.upsert_location(campaign.id, "SAMPLE ROAD", type_="wilderness")
    repo.set_current_location(campaign.id, town)
    return repo, campaign, town, other


def _link(repo, campaign, location_id, scene, active_encounter=None):
    return MapMakerAgent.link_tokens_to_entities(
        scene,
        location_id=location_id,
        encounters=repo.list_encounters(campaign.id, limit=200),
        items=repo.get_items(campaign.id),
        npcs=repo.get_npcs(campaign.id),
        combatants=repo.get_combatants(campaign.id),
        active_encounter=active_encounter,
    )


def test_npc_token_links_combatant_and_npcs_encounter(tmp_path: Path) -> None:
    repo, campaign, town, _other = _campaign(tmp_path)
    npc_id = repo.upsert_npc(campaign.id, "SAMPLE MERCHANT", disposition="wary")
    combatant_id = repo.upsert_combatant(
        campaign.id, "SAMPLE MERCHANT", kind="npc", hp=10, max_hp=10
    )
    encounter = repo.create_encounter(
        campaign.id,
        "npc",
        summary="SAMPLE CONVERSATION",
        state={
            "npc_id": npc_id,
            "npc_name": "SAMPLE MERCHANT",
            "disposition": "wary",
            "topic": None,
        },
        location_id=town,
    )
    scene = MapMakerAgent.derive_scene(LAYOUT, npcs=["SAMPLE MERCHANT"])

    linked = _link(repo, campaign, town, scene)

    token = next(t for t in scene.tokens if t.kind == "npc")
    assert token.combatant_id == combatant_id
    assert token.encounter_id == encounter.id
    assert linked >= 1


def test_loot_token_links_items_row_and_loot_encounter(tmp_path: Path) -> None:
    repo, campaign, town, _other = _campaign(tmp_path)
    item_id = repo.upsert_item(
        campaign.id,
        "SAMPLE SWORD",
        type_="weapon",
        level=1,
        location_name="SAMPLE TOWN",
    )
    encounter = repo.create_encounter(
        campaign.id,
        "loot",
        summary="SAMPLE CACHE",
        state={"items": [{"name": "SAMPLE SWORD"}], "claimed": False},
        location_id=town,
    )
    scene = MapMakerAgent.derive_scene(LAYOUT, loot=["SAMPLE SWORD"])

    linked = _link(repo, campaign, town, scene)

    token = next(t for t in scene.tokens if t.kind == "loot")
    assert token.item_id == item_id
    assert token.encounter_id == encounter.id
    assert linked >= 1


def test_door_and_trap_tokens_link_their_encounters(tmp_path: Path) -> None:
    repo, campaign, town, _other = _campaign(tmp_path)
    door = repo.create_encounter(
        campaign.id,
        "door",
        summary="SAMPLE DOOR",
        state={"locked": False, "key": None, "barred": False, "dc": None},
        location_id=town,
    )
    trap = repo.create_encounter(
        campaign.id,
        "trap",
        summary="SAMPLE TRAP",
        state={"dc": 15, "damage": "1d6", "armed": True},
        location_id=town,
    )
    layout = MapLayout(
        width=10,
        height=8,
        rooms=LAYOUT.rooms,
        secret_features=[
            MapSecretFeature(
                x=7, y=3, w=1, h=1, type="trap", name="SAMPLE TRAP"
            )
        ],
    )
    scene = MapMakerAgent.derive_scene(layout)

    _link(repo, campaign, town, scene)

    door_token = next(t for t in scene.tokens if t.kind == "door")
    trap_token = next(t for t in scene.tokens if t.kind == "trap")
    assert door_token.encounter_id == door.id
    assert trap_token.encounter_id == trap.id


def test_unlinked_door_and_trap_tokens_stay_null(tmp_path: Path) -> None:
    repo, campaign, town, _other = _campaign(tmp_path)
    layout = MapLayout(
        width=10,
        height=8,
        rooms=LAYOUT.rooms,
        secret_features=[
            MapSecretFeature(
                x=7, y=3, w=1, h=1, type="trap", name="SAMPLE TRAP"
            )
        ],
    )
    scene = MapMakerAgent.derive_scene(layout)

    _link(repo, campaign, town, scene)

    assert all(t.encounter_id is None for t in scene.tokens if t.kind in ("door", "trap"))


def test_location_filter_keeps_other_rooms_unlinked(tmp_path: Path) -> None:
    repo, campaign, town, other = _campaign(tmp_path)
    repo.upsert_item(
        campaign.id,
        "SAMPLE SWORD",
        type_="weapon",
        location_name="SAMPLE ROAD",
    )
    repo.create_encounter(
        campaign.id,
        "door",
        summary="SAMPLE DOOR",
        state={"locked": False, "key": None, "barred": False, "dc": None},
        location_id=other,
    )
    scene = MapMakerAgent.derive_scene(LAYOUT, loot=["SAMPLE SWORD"])

    _link(repo, campaign, town, scene)

    loot = next(t for t in scene.tokens if t.kind == "loot")
    assert loot.item_id is None
    assert loot.encounter_id is None
    assert all(t.encounter_id is None for t in scene.tokens if t.kind == "door")


@pytest.mark.asyncio
async def test_generate_map_tool_links_active_loot_encounter(
    tmp_path: Path, monkeypatch
) -> None:
    repo, campaign, town, _other = _campaign(tmp_path)
    item_id = repo.upsert_item(
        campaign.id,
        "SAMPLE SWORD",
        type_="weapon",
        location_name="SAMPLE TOWN",
    )
    encounter = repo.create_encounter(
        campaign.id,
        "loot",
        status="active",
        summary="SAMPLE CACHE",
        state={"items": [{"name": "SAMPLE SWORD"}], "claimed": False},
        location_id=town,
    )
    scene = MapMakerAgent.derive_scene(LAYOUT, loot=["SAMPLE SWORD"])

    async def fake_build(
        self,
        prompt: str,
        grid_enabled: bool = True,
        *,
        heroes=None,
        monsters=None,
        npcs=None,
        loot=None,
    ) -> BuildResult:
        return BuildResult(
            valid=True,
            layout=LAYOUT,
            gm_base64_png=None,
            player_base64_png=None,
            error=None,
            scene=scene,
            attempts=1,
        )

    monkeypatch.setattr(MapMakerAgent, "build", fake_build)

    orchestrator = LLMOrchestrator(repo)
    result = await orchestrator.handle_tool_call(
        "generate_map", {"prompt": "SAMPLE CACHE"}, campaign_id=campaign.id
    )

    assert result["encounter_id"] == encounter.id
    loot = next(t for t in result["scene"]["tokens"] if t["kind"] == "loot")
    assert loot["item_id"] == item_id
    assert loot["encounter_id"] == encounter.id
    stored = repo.get_encounter(campaign.id, encounter.id)
    assert stored is not None
    assert stored.state["map"]["scene"]["tokens"] == result["scene"]["tokens"]


@pytest.mark.asyncio
async def test_map_generate_links_active_loot_encounter(
    authenticated_client, tmp_path: Path, monkeypatch
) -> None:
    from app.api.deps import get_repo

    get_repo.cache_clear()
    repo = get_repo()
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town = repo.upsert_location(campaign.id, "SAMPLE TOWN", type_="settlement")
    repo.set_current_location(campaign.id, town)
    item_id = repo.upsert_item(
        campaign.id,
        "SAMPLE SWORD",
        type_="weapon",
        location_name="SAMPLE TOWN",
    )
    encounter = repo.create_encounter(
        campaign.id,
        "loot",
        status="active",
        summary="SAMPLE CACHE",
        state={"items": [{"name": "SAMPLE SWORD"}], "claimed": False},
        location_id=town,
    )
    scene = MapMakerAgent.derive_scene(LAYOUT, loot=["SAMPLE SWORD"])

    async def fake_build(
        self,
        prompt: str,
        grid_enabled: bool = True,
        *,
        heroes=None,
        monsters=None,
        npcs=None,
        loot=None,
    ) -> BuildResult:
        return BuildResult(
            valid=True,
            layout=LAYOUT,
            gm_base64_png="Z20=",
            player_base64_png="cGxheWVy",
            error=None,
            scene=scene,
            attempts=1,
        )

    monkeypatch.setattr(MapMakerAgent, "build", fake_build)

    response = authenticated_client.post(
        "/map/generate",
        json={"prompt": "SAMPLE CACHE", "campaign_id": campaign.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["encounter_id"] == encounter.id
    loot = next(t for t in body["scene"]["tokens"] if t["kind"] == "loot")
    assert loot["item_id"] == item_id
    assert loot["encounter_id"] == encounter.id

    detail = authenticated_client.get(
        f"/campaign/{campaign.id}/encounters/{encounter.id}"
    )
    assert detail.status_code == 200, detail.text
    map_state = detail.json()["state"]["map"]
    assert map_state["scene"]["tokens"] == body["scene"]["tokens"]
    assert map_state["linked_token_count"] >= 1
