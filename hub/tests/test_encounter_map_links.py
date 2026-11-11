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

from app.agents.map_maker import BuildResult, MapLayout, MapMakerAgent, MapRoom
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
        if token.kind == "loot":
            assert token.encounter_id is None
            assert token.combatant_id is None
        else:
            assert token.encounter_id == 77


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
