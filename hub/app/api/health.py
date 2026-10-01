# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Health check response model.

This module used to declare its own ``GET /health`` returning a bare dict with
four fields, and ``main.py`` registered this router *before* ``monitoring.router``,
so FastAPI matched the four-field version first. ``shared/openapi.yaml`` requires
six - it also lists ``timestamp`` and ``uptime_seconds``, because the exported
schema came from ``monitoring.HealthResponse`` when the duplicate won.

The spec and the served payload had therefore diverged: a strict Kotlin
deserializer saw missing required fields on every health poll.

The route now lives solely in ``monitoring.router``. This module keeps only the
re-export so existing imports of ``app.api.health.HealthResponse`` keep working.
"""

from app.api.monitoring import HealthResponse

__all__ = ["HealthResponse"]