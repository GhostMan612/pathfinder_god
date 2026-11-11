# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""The detailed health endpoint reports the one completed dependency probe."""
from __future__ import annotations

import pytest

from app.api import monitoring


@pytest.mark.parametrize("ollama_healthy", [True, False])
async def test_detailed_health_awaits_ollama_once(
    monkeypatch: pytest.MonkeyPatch, settings, ollama_healthy: bool
) -> None:
    calls = 0

    async def fake_check_database(_repo):
        return True, "ok"

    async def fake_check_ollama(_settings):
        nonlocal calls
        calls += 1
        return ollama_healthy, "ok" if ollama_healthy else "unavailable"

    async def fake_check_rules(_settings):
        return True, "ok (1 hits)"

    async def fake_check_disk():
        return True, "1.0GB free"

    monkeypatch.setattr(monitoring, "check_database", fake_check_database)
    monkeypatch.setattr(monitoring, "check_ollama", fake_check_ollama)
    monkeypatch.setattr(monitoring, "check_rules_db", fake_check_rules)
    monkeypatch.setattr(monitoring, "check_disk_space", fake_check_disk)

    result = await monitoring.detailed_health(settings=settings, repo=None)
    assert result.ollama["connected"] is ollama_healthy
    assert result.status == ("ok" if ollama_healthy else "degraded")
    assert calls == 1
