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

from app.api import health, ask, generate, rules, campaign, monitoring
from app.api.security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
)
from app.config import settings
from app.db.repository import CampaignRepository
from app.api.monitoring import MetricsMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    CampaignRepository(str(settings.data_dir / "campaign.db"))
    yield
    # Shutdown: cleanup if needed


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

    # CORS for Spoke (phone on LAN)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router)
    app.include_router(ask.router)
    app.include_router(generate.router)
    app.include_router(rules.router)
    app.include_router(campaign.router)
    app.include_router(monitoring.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)