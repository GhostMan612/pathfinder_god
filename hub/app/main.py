# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
FastAPI application factory for Pathfinder God Hub.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ask,
    campaign,
    combat,
    encounter,
    generate,
    health,
    loot,
    maps,
    monitoring,
    rules,
)
from app.api.monitoring import MetricsMiddleware
from app.api.security import (
    AUTHORIZATION_HEADER,
    API_KEY_HEADER_NAME,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.config import settings
from app.db.repository import CampaignRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    CampaignRepository(str(settings.data_dir / "campaign.db"))
    # Zero-config LAN discovery for the phone (no-op if zeroconf missing)
    from app.discovery import start_advertisement, stop_advertisement
    start_advertisement(settings.port, settings.version, settings.ollama_model)
    yield
    # Shutdown: cleanup if needed
    stop_advertisement()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="A local Pathfinder GM (RAG + Ollama) served to the companion app.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Security & observability middleware (order matters - first added = outermost)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
    app.add_middleware(MetricsMiddleware)

    # CORS for the Spoke (phone on the LAN).
    #
    # allow_origins=["*"] with allow_credentials=True meant any web page the user
    # visited could issue cross-origin fetches to http://<laptop-lan-ip>:8000 and
    # read the responses - /ask and /rules/search were unauthenticated, and the
    # /campaign data endpoints were behind the API-key check that has since been
    # closed. Starlette emits Access-Control-Allow-Origin: * together with
    # Access-Control-Allow-Credentials: true, which is the worst of both.
    #
    # The Spoke is a native Android client and does not use CORS at all; only the
    # Command Center and local tooling are browser origins, and they run on
    # localhost. Pinned to real origins, and credentials are off - the API key
    # travels in an explicit header, never as a cookie.
    allowed_origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://10.0.2.2:8000",
        f"http://{settings.host}:{settings.port}",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", API_KEY_HEADER_NAME, AUTHORIZATION_HEADER],
    )

    # Routers
    # /health is served by monitoring.router (HealthResponse has six fields and
    # matches shared/openapi.yaml). app.api.health used to register a second,
    # four-field /health ahead of it, which is the one that won.
    app.include_router(ask.router)
    app.include_router(ask.stream_router)
    app.include_router(loot.router)
    app.include_router(generate.router)
    app.include_router(rules.router)
    app.include_router(campaign.router)
    app.include_router(monitoring.router)
    app.include_router(combat.router)
    app.include_router(encounter.router)
    app.include_router(maps.router)

    # loot.router was registered twice (lines 80 and 88). FastAPI emitted
    #   UserWarning: Duplicate Operation ID generate_loot_generate_loot_post
    # and POST /generate/loot appeared twice in /openapi.json, which breaks
    # strict Kotlin openapi codegen. The first registration is the one that
    # wins for routing, so loot must stay ahead of generate.router.

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)