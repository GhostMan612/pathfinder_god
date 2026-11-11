# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Minimal standalone 3D encounter-stage page.

This is deliberately not an API: it is one static HTML file plus one static JS
island. It is excluded from OpenAPI. The scene shape is the existing
``SceneResponse`` emitted by ``/map/generate`` and the ``encounter_stage``
WebSocket frame.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

router = APIRouter(tags=["stage"])


@router.get("/stage", include_in_schema=False, response_class=FileResponse)
async def stage_page() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "stage.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/stage/stage.js",
    include_in_schema=False,
    response_class=FileResponse,
)
async def stage_script() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "stage.js",
        media_type="text/javascript",
        headers={"Cache-Control": "no-store"},
    )
