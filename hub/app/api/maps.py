# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Map Generator API — LLM + dual-layer Pillow rendering."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.map_maker import MapMakerAgent, MapScene
from app.api.deps import get_repo
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/map", tags=["map"])


class MapRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)
    grid_enabled: bool = True
    campaign_id: int | None = None
    heroes: list[str] | None = None
    monsters: list[str] | None = None
    npcs: list[str] | None = None
    loot: list[str] | None = None


class MapRoomResponse(BaseModel):
    x: int
    y: int
    w: int
    h: int
    name: str


class MapSecretResponse(BaseModel):
    x: int
    y: int
    w: int
    h: int
    type: str
    name: str


class GridResponse(BaseModel):
    w: int
    h: int
    tile_m: float


class ZoneResponse(BaseModel):
    name: str
    biome: str
    rect: list[int]


class PropResponse(BaseModel):
    type: str = Field(pattern="^(crate|brazier|pillar|chest|barrel|altar)$")
    x: int
    y: int
    rot: int = Field(ge=0, le=270)
    scale: float = 1.0


class LightResponse(BaseModel):
    x: int
    y: int
    color: str
    radius_m: float


class FogResponse(BaseModel):
    color: str
    density: float


class PointResponse(BaseModel):
    x: int
    y: int


class DoorResponse(BaseModel):
    x: int
    y: int
    orientation: str = "ew"
    kind: str = "wood"


class CorridorResponse(BaseModel):
    cells: list[list[int]] = Field(default_factory=list)


class TokenResponse(BaseModel):
    id: str
    name: str
    kind: str = Field(pattern="^(hero|monster|npc|loot|door|trap)$")
    x: int
    y: int
    z: float = 0.5
    color: str = "#d4af37"
    encounter_id: int | None = None
    combatant_id: int | None = None
    item_id: int | None = None


class SceneResponse(BaseModel):
    grid: GridResponse
    heightmap: list[list[int]]
    zones: list[ZoneResponse]
    props: list[PropResponse]
    lights: list[LightResponse]
    fog: FogResponse | None = None
    walkable: list[list[int]] = Field(default_factory=list)
    doors: list[DoorResponse] = Field(default_factory=list)
    corridors: list[CorridorResponse] = Field(default_factory=list)
    spawn: PointResponse | None = None
    exit: PointResponse | None = None
    tokens: list[TokenResponse] = Field(default_factory=list)
    connected: bool = True


class MapResponse(BaseModel):
    valid: bool
    gm_base64_png: str | None = None
    player_base64_png: str | None = None
    width: int | None = None
    height: int | None = None
    rooms: list[MapRoomResponse] | None = None
    secret_features: list[MapSecretResponse] | None = None
    scene: SceneResponse | None = None
    error: str | None = None
    attempts: int = 1
    encounter_id: int | None = None


def _scene_response(scene: MapScene) -> SceneResponse:
    """Project the dataclass scene onto the wire contract once."""
    return SceneResponse.model_validate(scene.to_dict())


@router.post("/generate", response_model=MapResponse)
async def generate_map(
    request: MapRequest,
    repo: CampaignRepository = Depends(get_repo),
) -> MapResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    agent = MapMakerAgent(llm)

    heroes = request.heroes
    monsters = request.monsters
    npcs = request.npcs
    loot = request.loot
    if request.campaign_id is not None:
        c_heroes, c_monsters, c_npcs, c_loot = MapMakerAgent.entities_from_campaign(
            repo, request.campaign_id
        )
        if heroes is None and c_heroes:
            heroes = c_heroes
        if monsters is None and c_monsters:
            monsters = c_monsters
        if npcs is None and c_npcs:
            npcs = c_npcs
        if loot is None and c_loot:
            loot = c_loot

    try:
        result = await agent.build(
            request.prompt,
            grid_enabled=request.grid_enabled,
            heroes=heroes,
            monsters=monsters,
            npcs=npcs,
            loot=loot,
        )
    except Exception:
        # Never echo the exception text to the client: it carries filesystem
        # paths, library versions and model output fragments.
        logger.exception("map generation failed")
        raise HTTPException(status_code=500, detail="An internal error occurred.")
    finally:
        await llm.close()

    if not result.valid:
        # result.error can be "LLM generation failed: ...", "Map rendering
        # failed: ..." or "Pillow not available" - all server-side. Reporting
        # them as 400 told the client its request was malformed when the hub was
        # at fault. Only a genuinely invalid layout is a 400.
        error = result.error or "Invalid map layout"
        client_fault = "invalid json" in error.lower() or "out of bounds" in error.lower()
        if not client_fault:
            # Server-side detail stays server-side; log it and return a generic
            # message so internal paths/errors do not reach the client.
            logger.error("map generation produced an invalid layout: %s", error)
            raise HTTPException(status_code=500, detail="An internal error occurred.")
        raise HTTPException(
            status_code=400,
            detail="Invalid map layout",
        )

    active_encounter = None
    linked_count = 0
    if request.campaign_id is not None and result.scene is not None:
        active_encounter = repo.get_active_encounter(request.campaign_id)
        solo_state = repo.get_solo_state(request.campaign_id)
        location_id = (
            active_encounter.location_id
            if active_encounter is not None
            else (solo_state.current_location_id if solo_state else None)
        )
        combatants = (
            repo.get_combatants(request.campaign_id, active_only=True)
            if active_encounter is not None
            and active_encounter.kind == "battle"
            else repo.get_combatants(request.campaign_id)
        )
        linked_count = MapMakerAgent.link_tokens_to_entities(
            result.scene,
            location_id=location_id,
            encounters=repo.list_encounters(request.campaign_id, limit=200),
            items=repo.get_items(request.campaign_id),
            npcs=repo.get_npcs(request.campaign_id),
            combatants=combatants,
            active_encounter=active_encounter,
        )

    scene = _scene_response(result.scene) if result.scene is not None else None
    if scene is not None and active_encounter is not None:
        # Persist the map on the active encounter so reopening the encounter
        # does not require regenerating it, and so token links survive this
        # request. Non-battle kinds use the same persistence shape as battle.
        repo.attach_encounter_map(
            request.campaign_id,
            active_encounter.id,
            {
                "encounter_id": active_encounter.id,
                "grid": scene.grid.model_dump(),
                "scene": scene.model_dump(),
                "linked_token_count": linked_count,
                "linked_tokens": [
                    token.model_dump()
                    for token in scene.tokens
                    if token.combatant_id is not None
                    or token.encounter_id is not None
                    or token.item_id is not None
                ],
            },
        )

    return MapResponse(
        valid=result.valid,
        gm_base64_png=result.gm_base64_png,
        player_base64_png=result.player_base64_png,
        width=result.layout.width if result.layout else None,
        height=result.layout.height if result.layout else None,
        rooms=[
            MapRoomResponse(
                x=r.x,
                y=r.y,
                w=r.w,
                h=r.h,
                name=r.name,
            )
            for r in result.layout.rooms
        ] if result.layout else None,
        secret_features=[
            MapSecretResponse(
                x=s.x,
                y=s.y,
                w=s.w,
                h=s.h,
                type=s.type,
                name=s.name,
            )
            for s in result.layout.secret_features
        ] if result.layout else None,
        scene=scene,
        error=result.error,
        attempts=result.attempts,
        encounter_id=active_encounter.id if active_encounter is not None else None,
    )
