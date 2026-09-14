# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Health check endpoint.
"""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health", tags=["meta"])
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.version,
        "ollama_model": settings.ollama_model,
        "databases_found": [
            str(p.name) for p in settings.db_paths if p.exists()
        ],
    }