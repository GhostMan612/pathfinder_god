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
    loot,
    maps,
    monitoring,
    rules,
)
from app.api.monitoring import MetricsMiddleware
from app.api.security import (
    API_KEY_HEADER_NAME,
    AUTHORIZATION_HEADER,
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
    # This used to be allow_origins=["*"] with allow_credentials=True, on a service
    # bound to 0.0.0.0 and therefore reachable at http://<laptop-lan-ip>:8000.
    # Starlette's CORSMiddleware does NOT emit a literal "*" in that combination -
    # it does something worse. From starlette/middleware/cors.py:
    #
    #     # If credentials are allowed, then we must respond with the specific origin instead of '*'.
    #     if self.allow_all_origins and self.allow_credentials:
    #         self.allow_explicit_origin(headers, origin)
    #
    # so it reflects the caller's own Origin back verbatim and sets
    # Access-Control-Allow-Credentials: true. That is a *valid* CORS response, so
    # the browser lets the attacker's JavaScript read it: any web page the user
    # visited could issue cross-origin fetches to the laptop's LAN address and read
    # the replies. /ask and /rules/search need no credentials at all, so the answers
    # were readable directly. This is a published Starlette advisory, not a
    # theoretical concern (GHSA-9jfm-9rc6-2hfq). Starlette's own docs agree the
    # config was invalid: "allow_origins, allow_methods and allow_headers cannot be
    # set to ['*'] for credentials to be allowed, all of them must be explicitly
    # specified."
    #
    # The Spoke is a native Android client and does not use CORS at all; only the
    # Command Center and local tooling are browser origins, and they run on
    # localhost. Pinned to real origins, and credentials are off - the API key
    # travels in an explicit header, never as a cookie.
    allowed_origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://10.0.2.2:8000",  # emulator -> host loopback
    ]
    # The configured bind host is only useful as an origin when it is a real,
    # dialable address. It defaults to 0.0.0.0 (and may be ::), which no browser
    # can navigate to, so adding it verbatim would just put a junk entry in the
    # allow-list. A real address (e.g. a LAN IP pinned in .env) is honoured.
    bind_host = settings.host.strip()
    if bind_host and bind_host not in ("0.0.0.0", "::", "[::]", "*"):
        allowed_origins.append(f"http://{bind_host}:{settings.port}")
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