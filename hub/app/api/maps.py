# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Map Generator API — LLM + dual-layer Pillow rendering."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.map_maker import MapMakerAgent
from app.config import get_settings
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/map", tags=["map"])


class MapRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)
    grid_enabled: bool = True


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


class SceneResponse(BaseModel):
    grid: GridResponse
    heightmap: list[list[int]]
    zones: list[ZoneResponse]
    props: list[PropResponse]
    lights: list[LightResponse]
    fog: FogResponse | None = None


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


@router.post("/generate", response_model=MapResponse)
async def generate_map(request: MapRequest) -> MapResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    agent = MapMakerAgent(llm)

    try:
        result = await agent.build(request.prompt, grid_enabled=request.grid_enabled)
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

    scene = None
    if result.scene is not None:
        scene = SceneResponse(
            grid=GridResponse(
                w=result.scene.grid.w,
                h=result.scene.grid.h,
                tile_m=result.scene.grid.tile_m,
            ),
            heightmap=result.scene.heightmap,
            zones=[
                ZoneResponse(name=z.name, biome=z.biome, rect=list(z.rect))
                for z in result.scene.zones
            ],
            props=[
                PropResponse(type=p.type, x=p.x, y=p.y, rot=p.rot, scale=p.scale)
                for p in result.scene.props
            ],
            lights=[
                LightResponse(x=l.x, y=l.y, color=l.color, radius_m=l.radius_m)
                for l in result.scene.lights
            ],
            fog=(
                FogResponse(color=result.scene.fog.color, density=result.scene.fog.density)
                if result.scene.fog is not None
                else None
            ),
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
    )
