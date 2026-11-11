# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Rules database readiness must report real availability, not a no-hit success."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.api.monitoring import check_rules_db
from app.config import Settings


async def test_rules_readiness_fails_when_database_is_missing(tmp_path: Path) -> None:
    status, message = await check_rules_db(Settings(data_dir=tmp_path))
    assert status is False
    assert "no readable rules database" in message


async def test_rules_readiness_rejects_unsupported_sqlite_shape(tmp_path: Path) -> None:
    db = tmp_path / "pathfinder_rag.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE unrelated (value TEXT)")
    status, message = await check_rules_db(Settings(data_dir=tmp_path))
    assert status is False
    assert "supported schema" in message


async def test_rules_readiness_rejects_corrupt_sqlite(tmp_path: Path) -> None:
    (tmp_path / "pathfinder_rag.db").write_bytes(b"not a database")
    status, message = await check_rules_db(Settings(data_dir=tmp_path))
    assert status is False
    assert "no readable rules database" in message


async def test_rules_readiness_accepts_valid_fts_fixture(rules_db_dir: Path) -> None:
    status, message = await check_rules_db(Settings(data_dir=rules_db_dir))
    assert status is True
    assert message == "ok (pathfinder_rag.db)"


async def test_rules_readiness_uses_existing_secondary_source(tmp_path: Path) -> None:
    db = tmp_path / "pathfinder_2e_rag.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE VIRTUAL TABLE chunks USING fts5(source, content)")
    status, message = await check_rules_db(Settings(data_dir=tmp_path))
    assert status is True
    assert message == "ok (pathfinder_2e_rag.db)"
