# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Attach the current location's deterministic map scene to an encounter.

The map generator already persists its scene under ``state.map.scene``.  The
3D stage uses the same scene object under ``state.scene`` so a client can switch
without a second fetch.  When no map exists yet, this module derives one with
the same deterministic ``MapMakerAgent.derive_scene`` the GM tool uses; no LLM
call and no second map path.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from app.agents.map_maker import MapLayout, MapMakerAgent, MapRoom

logger = logging.getLogger(__name__)


def _scene_from_state(state: dict | None) -> dict | None:
    """Return the scene stored on an encounter state, if any."""
    if not isinstance(state, dict):
        return None
    existing = state.get("scene")
    if isinstance(existing, dict):
        return copy.deepcopy(existing)
    map_scene = (state.get("map") or {}).get("scene")
    if isinstance(map_scene, dict):
        return copy.deepcopy(map_scene)
    return None


def stage_scene_for_location(
    repo: Any, campaign_id: int, location_id: int | None
) -> dict | None:
    """Return an existing scene at this location, or a deterministic fallback."""
    if location_id is None:
        return None

    # The active encounter owns the stage: its scene wins even when a newer
    # resolved encounter at the same location already has one. This is a
    # direct query, so it also survives campaigns with more than 200
    # encounters (list_encounters caps at 200).
    active = repo.get_active_encounter(campaign_id)
    if active is not None and active.location_id == location_id:
        scene = _scene_from_state(active.state)
        if scene is not None:
            return scene

    for encounter in repo.list_encounters(campaign_id, limit=200):
        if encounter.location_id != location_id:
            continue
        scene = _scene_from_state(encounter.state)
        if scene is not None:
            return scene

    location = repo.get_location(campaign_id, location_id)
    name = location.name if location is not None else "SAMPLE LOCATION"
    width, height = 12, 10
    layout = MapLayout(
        width=width,
        height=height,
        rooms=[MapRoom(x=1, y=1, w=width - 2, h=height - 2, name=name)],
        secret_features=[],
    )
    heroes, monsters, npcs, loot = MapMakerAgent.entities_from_campaign(
        repo, campaign_id
    )
    scene = MapMakerAgent.derive_scene(
        layout,
        heroes=heroes,
        monsters=monsters,
        npcs=npcs,
        loot=loot,
    )
    return scene.to_dict()


def attach_stage_scene(
    repo: Any,
    campaign_id: int,
    encounter: Any,
) -> dict | None:
    """Persist the location scene on an encounter without changing status."""
    existing = (encounter.state or {}).get("scene")
    if isinstance(existing, dict):
        return copy.deepcopy(existing)

    scene = stage_scene_for_location(
        repo, campaign_id, getattr(encounter, "location_id", None)
    )
    if scene is None:
        return None
    try:
        updated = repo.attach_encounter_map(
            campaign_id,
            encounter.id,
            {
                "encounter_id": encounter.id,
                "grid": scene.get("grid"),
                "scene": scene,
                "linked_token_count": 0,
                "linked_tokens": [],
                "source": "encounter_stage",
            },
        )
        stored = (updated.state or {}).get("scene")
        if isinstance(stored, dict):
            return copy.deepcopy(stored)
    except (TypeError, ValueError):
        logger.exception(
            "could not attach stage scene to encounter %s", encounter.id
        )
    return scene


def stage_event(encounter: Any, scene: dict) -> dict:
    """Build the WS frame that tells a client to switch to the 3D stage."""
    return {
        "type": "encounter_stage",
        "encounter_id": encounter.id,
        "kind": encounter.kind,
        "scene": scene,
    }
