# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Hermetic tests for the campaign.db snapshot script (BP-07 Stage 6)."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("backup_campaign", SCRIPTS_DIR / "backup_campaign.py")
assert _spec is not None and _spec.loader is not None
backup_campaign = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backup_campaign)

_TABLE_DDL = {
    "campaigns": "CREATE TABLE campaigns (id INTEGER PRIMARY KEY, summary TEXT)",
    "sessions": "CREATE TABLE sessions (id INTEGER PRIMARY KEY, raw_log TEXT)",
    "npcs": "CREATE TABLE npcs (id INTEGER PRIMARY KEY, name TEXT)",
}


def _make_campaign_db(path: Path, tables: tuple[str, ...] = ("campaigns", "sessions", "npcs")) -> None:
    conn = sqlite3.connect(path)
    for table in tables:
        conn.execute(_TABLE_DDL[table])
    if "campaigns" in tables:
        conn.execute("INSERT INTO campaigns (id, summary) VALUES (1, 'evergreen chronicle')")
    if "sessions" in tables:
        conn.execute("INSERT INTO sessions (id, raw_log) VALUES (1, 'the party met a goblin')")
    if "npcs" in tables:
        conn.execute("INSERT INTO npcs (id, name) VALUES (1, 'SAMPLE NPC A')")
    conn.commit()
    conn.close()


def test_backup_once_snapshots_content(tmp_path: Path) -> None:
    source = tmp_path / "campaign.db"
    _make_campaign_db(source)
    out = tmp_path / "backups"
    target = backup_campaign.backup_once(source, out)
    assert target.parent == out
    assert target.exists()
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        summary = conn.execute("SELECT summary FROM campaigns WHERE id = 1").fetchone()
        raw_log = conn.execute("SELECT raw_log FROM sessions WHERE id = 1").fetchone()
        npc = conn.execute("SELECT name FROM npcs WHERE id = 1").fetchone()
    finally:
        conn.close()
    assert summary == ("evergreen chronicle",)
    assert raw_log == ("the party met a goblin",)
    assert npc == ("SAMPLE NPC A",)


def test_backup_once_same_second_never_overwrites(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "campaign.db"
    _make_campaign_db(source)
    out = tmp_path / "backups"

    class FixedClock:
        @staticmethod
        def now() -> datetime:
            return datetime(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr(backup_campaign, "datetime", FixedClock)
    first = backup_campaign.backup_once(source, out)
    second = backup_campaign.backup_once(source, out)
    assert first != second
    assert first.name == "campaign-20260101-120000.db"
    assert second.name == "campaign-20260101-120000-2.db"


def test_backup_once_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        backup_campaign.backup_once(tmp_path / "nope.db", tmp_path / "backups")


def test_backup_once_missing_table_cleans_partial_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "campaign.db"
    _make_campaign_db(source, tables=("campaigns", "sessions"))
    out = tmp_path / "backups"
    with pytest.raises(RuntimeError):
        backup_campaign.backup_once(source, out)
    assert list(out.glob("campaign-*.db")) == []


def test_prune_keeps_newest(tmp_path: Path) -> None:
    out = tmp_path / "backups"
    out.mkdir()
    names = [
        "campaign-20260101-000000.db",
        "campaign-20260102-000000.db",
        "campaign-20260103-000000.db",
    ]
    for name in names:
        (out / name).write_bytes(b"snapshot")
    removed = backup_campaign.prune(out, keep=2)
    assert removed == [out / "campaign-20260101-000000.db"]
    assert sorted(p.name for p in out.glob("campaign-*.db")) == names[1:]


def test_main_skips_when_db_absent(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "backups"
    monkeypatch.setattr(
        sys, "argv",
        ["backup_campaign.py", "--db", str(tmp_path / "nope.db"), "--out", str(out)],
    )
    assert backup_campaign.main() == 0
    assert not out.exists()


def test_main_rotation_applies_keep(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "campaign.db"
    _make_campaign_db(source)
    out = tmp_path / "backups"
    monkeypatch.setattr(
        sys, "argv",
        ["backup_campaign.py", "--db", str(source), "--out", str(out), "--keep", "1"],
    )
    assert backup_campaign.main() == 0
    assert backup_campaign.main() == 0
    assert len(list(out.glob("campaign-*.db"))) == 1
