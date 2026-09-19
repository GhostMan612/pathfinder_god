# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Health check and monitoring endpoints for production deployment.
Provides liveness, readiness, and detailed health checks.
"""
from __future__ import annotations

import platform
import sys
import time
from datetime import datetime

import psutil
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.config import Settings, get_settings
from app.db.repository import CampaignRepository, get_repo

router = APIRouter(tags=["monitoring"])


# ─── Response Models ───

class HealthResponse(BaseModel):
    status: str
    version: str
    ollama_model: str
    databases_found: list[str]
    timestamp: str
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]
    timestamp: str


class MetricsResponse(BaseModel):
    requests_total: int
    requests_per_second: float
    average_response_time_ms: float
    error_rate: float
    uptime_seconds: float
    memory_usage_mb: float
    cpu_percent: float
    disk_usage_percent: float
    active_connections: int


class DetailedHealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    ollama_model: str
    databases_found: list[str]
    timestamp: str
    uptime_seconds: float
    system: dict
    database: dict
    ollama: dict
    checks: dict[str, str]


# ─── Global Metrics ───

_start_time = time.time()
_request_count = 0
_error_count = 0
_total_response_time = 0.0


def record_request(duration_ms: float, is_error: bool = False):
    """Record request metrics."""
    global _request_count, _error_count, _total_response_time
    _request_count += 1
    if is_error:
        _error_count += 1
    _total_response_time += duration_ms


def get_metrics() -> dict:
    """Get current metrics snapshot."""
    uptime = time.time() - _start_time
    rps = _request_count / uptime if uptime > 0 else 0
    avg_response = _total_response_time / _request_count if _request_count > 0 else 0
    error_rate = _error_count / _request_count if _request_count > 0 else 0
    
    process = psutil.Process()
    mem = process.memory_info()
    cpu = process.cpu_percent()
    disk = psutil.disk_usage('/')
    
    return {
        "requests_total": _request_count,
        "requests_per_second": round(rps, 2),
        "average_response_time_ms": round(avg_response, 2),
        "error_rate": round(error_rate, 4),
        "uptime_seconds": round(uptime, 1),
        "memory_usage_mb": round(mem.rss / 1024 / 1024, 1),
        "cpu_percent": round(cpu, 1),
        "disk_usage_percent": round(disk.percent, 1),
        "active_connections": 0,  # Would need connection pool tracking
    }


# ─── Health Check Functions ───

async def check_database(repo: CampaignRepository) -> tuple[bool, str]:
    """Check database connectivity."""
    try:
        with repo._conn() as conn:
            conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as e:
        return False, str(e)


async def check_ollama(settings) -> tuple[bool, str]:
    """Check Ollama connectivity."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            if r.status_code == 200:
                return True, "ok"
            return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


async def check_rules_db(settings) -> tuple[bool, str]:
    """Check rules database accessibility."""
    try:
        from app.rag.retriever import Retriever
        retriever = Retriever(settings.db_paths, rag_limit=1)
        hits = retriever.search("test", edition="2e", limit=1)
        return True, f"ok ({len(hits)} hits)"
    except Exception as e:
        return False, str(e)


async def check_disk_space() -> tuple[bool, str]:
    """Check available disk space."""
    disk = psutil.disk_usage('/')
    free_gb = disk.free / (1024**3)
    if free_gb < 1.0:
        return False, f"Low disk space: {free_gb:.1f}GB free"
    return True, f"{free_gb:.1f}GB free"


# ─── Endpoints ───

@router.get("/health", response_model=HealthResponse, tags=["monitoring"])
async def health(settings: Settings = Depends(get_settings)):
    """
    Basic liveness probe - indicates the service is running.
    Does NOT check dependencies.
    """
    uptime = time.time() - _start_time
    
    return HealthResponse(
        status="ok",
        version=settings.version,
        ollama_model=settings.ollama_model,
        databases_found=[p.name for p in settings.db_paths if p.exists()],
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@router.get("/ready", response_model=ReadinessResponse, tags=["monitoring"])
async def readiness(
    settings: Settings = Depends(get_settings),
    repo: CampaignRepository = Depends(get_repo),
):
    """
    Readiness probe - checks if service can handle requests.
    Verifies all critical dependencies.
    """
    checks = {}
    all_healthy = True
    
    # Database
    db_ok, db_msg = await check_database(repo)
    checks["database"] = db_msg
    if not db_ok:
        all_healthy = False
    
    # Ollama
    ollama_ok, ollama_msg = await check_ollama(settings)
    checks["ollama"] = ollama_msg
    if not ollama_ok:
        all_healthy = False
    
    # Rules DB
    rules_ok, rules_msg = await check_rules_db(settings)
    checks["rules_db"] = rules_msg
    if not rules_ok:
        all_healthy = False
    
    # Disk space
    disk_ok, disk_msg = await check_disk_space()
    checks["disk_space"] = disk_msg
    if not disk_ok:
        all_healthy = False
    
    status = "ready" if all_healthy else "not_ready"
    
    return ReadinessResponse(
        status=status,
        checks=checks,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse, tags=["monitoring"])
async def detailed_health(
    settings: Settings = Depends(get_settings),
    repo: CampaignRepository = Depends(get_repo),
):
    """
    Detailed health check with system info and dependency status.
    """
    checks = {}
    all_healthy = True
    
    # Database
    db_ok, db_msg = await check_database(repo)
    checks["database"] = db_msg
    if not db_ok:
        all_healthy = False
    
    # Ollama
    ollama_ok, ollama_msg = await check_ollama(settings)
    checks["ollama"] = ollama_msg
    if not ollama_ok:
        all_healthy = False
    
    # Rules DB
    rules_ok, rules_msg = await check_rules_db(settings)
    checks["rules_db"] = rules_msg
    if not rules_ok:
        all_healthy = False
    
    # Disk space
    disk_ok, disk_msg = await check_disk_space()
    checks["disk_space"] = disk_msg
    if not disk_ok:
        all_healthy = False
    
    # System info
    process = psutil.Process()
    mem = process.memory_info()
    disk = psutil.disk_usage('/')
    cpu = psutil.cpu_percent(interval=0.1)
    
    system_info = {
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": disk.percent,
        "process_memory_mb": round(mem.rss / 1024 / 1024, 1),
    }
    
    database_info = {
        "path": str(settings.db_paths[0]) if settings.db_paths else "none",
        "exists": settings.db_paths[0].exists() if settings.db_paths else False,
        "size_mb": round(settings.db_paths[0].stat().st_size / 1024 / 1024, 1) if settings.db_paths and settings.db_paths[0].exists() else 0,
    }
    
    ollama_info = {
        "host": settings.ollama_host,
        "model": settings.ollama_model,
        "connected": await check_ollama(settings)[0],
    }
    
    return DetailedHealthResponse(
        status="ok" if all_healthy else "degraded",
        version=settings.version,
        environment=settings.environment,
        ollama_model=settings.ollama_model,
        databases_found=[p.name for p in settings.db_paths if p.exists()],
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=round(time.time() - _start_time, 1),
        system=system_info,
        database=database_info,
        ollama=ollama_info,
        checks=checks,
    )


@router.get("/metrics", response_class=PlainTextResponse, tags=["monitoring"])
async def metrics():
    """
    Prometheus-compatible metrics endpoint.
    """
    metrics = get_metrics()
    lines = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
        f"http_requests_total {_request_count}",
        "# HELP http_requests_per_second Requests per second",
        "# TYPE http_requests_per_second gauge",
        f"http_requests_per_second {_request_count / (time.time() - _start_time) if time.time() > _start_time else 0:.2f}",
        "# HELP http_request_duration_ms Average response time in milliseconds",
        "# TYPE http_request_duration_ms gauge",
        f"http_request_duration_ms {_total_response_time / _request_count if _request_count > 0 else 0:.2f}",
        "# HELP http_error_rate Error rate",
        "# TYPE http_error_rate gauge",
        f"http_error_rate {_error_count / _request_count if _request_count > 0 else 0:.4f}",
        "# HELP process_uptime_seconds Process uptime in seconds",
        "# TYPE process_uptime_seconds gauge",
        f"process_uptime_seconds {time.time() - _start_time:.1f}",
        "# HELP process_memory_mb Process memory usage in MB",
        "# TYPE process_memory_mb gauge",
        f"process_memory_mb {psutil.Process().memory_info().rss / 1024 / 1024:.1f}",
        "# HELP process_cpu_percent Process CPU usage",
        "# TYPE process_cpu_percent gauge",
        f"process_cpu_percent {psutil.cpu_percent()}",
        "# HELP system_memory_percent System memory usage",
        "# TYPE system_memory_percent gauge",
        f"system_memory_percent {psutil.virtual_memory().percent}",
        "# HELP system_disk_percent System disk usage",
        "# TYPE system_disk_percent gauge",
        f"system_disk_percent {psutil.disk_usage('/').percent}",
    ]
    
    return PlainTextResponse("\n".join(lines) + "\n")


@router.get("/metrics/json", response_model=MetricsResponse, tags=["monitoring"])
async def metrics_json():
    """JSON format metrics for programmatic consumption."""
    return MetricsResponse(**get_metrics())


@router.get("/version", tags=["monitoring"])
async def version(settings: Settings = Depends(get_settings)):
    """Version information."""
    return {
        "version": settings.version,
        "environment": settings.environment,
        "ollama_model": settings.ollama_model,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "build_date": datetime.utcnow().isoformat(),
    }


# ─── Request Tracking Middleware Integration ───

class MetricsMiddleware:
    """Middleware to track request metrics."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start = time.time()
        error = False
        
        async def send_wrapper(message):
            nonlocal error
            if message["type"] == "http.response.start":
                error = message.get("status", 200) >= 400
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            error = True
            raise
        finally:
            duration = (time.time() - start) * 1000
            record_request(duration, error)