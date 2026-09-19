# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Map Generator API — LLM + dual-layer Pillow rendering."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.map_maker import MapMakerAgent
from app.config import get_settings
from app.llm.ollama_client import OllamaClient

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


class MapResponse(BaseModel):
    valid: bool
    gm_base64_png: str | None = None
    player_base64_png: str | None = None
    width: int | None = None
    height: int | None = None
    rooms: list[MapRoomResponse] | None = None
    secret_features: list[MapSecretResponse] | None = None
    error: str | None = None


@router.post("/generate", response_model=MapResponse)
async def generate_map(request: MapRequest) -> MapResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    agent = MapMakerAgent(llm)

    try:
        result = await agent.build(request.prompt, grid_enabled=request.grid_enabled)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Map generation failed: {e}")
    finally:
        await llm.close()

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.error or "Invalid map layout")

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
        error=result.error,
    )
