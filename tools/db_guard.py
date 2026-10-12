# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Inspect the live campaign DB for synthetic test data, then snapshot it."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "campaign.db"
DEFAULT_OUT = REPO_ROOT / "data" / "backups"

sys.path.insert(0, str(REPO_ROOT / "hub" / "scripts"))
from backup_campaign import backup_once, prune

SYNTHETIC_MARKERS = (
    "waffle iron",
    "norgorber",
    "bake a cake",
    "swim action",
    "synthetic",
    "verification",
    "test turn",
)


def _preview(text: str | None, limit: int = 120) -> str:
    if not text:
        return "-"
    flat = " ".join(str(text).split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 3] + "..."


def _tail(text: str | None, limit: int = 160) -> str:
    if not text:
        return "-"
    flat = " ".join(str(text).split())
    if len(flat) <= limit:
        return flat
    return "..." + flat[-limit:]


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _inspect_campaigns(conn: sqlite3.Connection) -> None:
    print("\n[Latest Campaigns]")
    rows = conn.execute(
        """
        SELECT id, name, updated_at,
               length(coalesce(summary, '')) AS summary_len,
               length(coalesce(combat_json, '')) AS combat_len
        FROM campaigns
        ORDER BY updated_at DESC, id DESC
        LIMIT 3
        """
    ).fetchall()
    if not rows:
        print("  (none)")
    for row in rows:
        print(
            f"  - id={row['id']} name={row['name']!r} "
            f"updated_at={row['updated_at']} "
            f"summary_len={row['summary_len']} combat_len={row['combat_len']}"
        )


def _inspect_sessions(conn: sqlite3.Connection) -> None:
    print("\n[Latest Sessions]")
    rows = conn.execute(
        """
        SELECT id, campaign_id, session_num, started_at, ended_at,
               summary, raw_log
        FROM sessions
        ORDER BY id DESC
        LIMIT 5
        """
    ).fetchall()
    if not rows:
        print("  (none)")
    for row in rows:
        print(
            f"  - id={row['id']} campaign_id={row['campaign_id']} "
            f"session_num={row['session_num']} started_at={row['started_at']} "
            f"ended_at={row['ended_at'] or '-'}"
        )
        print(f"    summary: {_preview(row['summary'])}")
        print(f"    raw_log_tail: {_tail(row['raw_log'])}")


def _inspect_notes(conn: sqlite3.Connection, tables: set[str]) -> None:
    if "session_notes" not in tables:
        return
    print("\n[Latest Session Notes]")
    rows = conn.execute(
        """
        SELECT id, campaign_id, session_num, note_type, created_at, content
        FROM session_notes
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()
    if not rows:
        print("  (none)")
    for row in rows:
        print(
            f"  - id={row['id']} campaign_id={row['campaign_id']} "
            f"session_num={row['session_num']} type={row['note_type']} "
            f"created_at={row['created_at']}"
        )
        print(f"    {_preview(row['content'])}")


def _report_suspects(conn: sqlite3.Connection, tables: set[str]) -> None:
    checks: list[tuple[str, str, str]] = [
        ("campaigns", "id", "name"),
        ("campaigns", "id", "summary"),
        ("campaigns", "id", "combat_json"),
        ("sessions", "id", "summary"),
        ("sessions", "id", "raw_log"),
    ]
    if "session_notes" in tables:
        checks.append(("session_notes", "id", "content"))

    matches = 0
    print("\n[Suspected Synthetic Rows]")
    for table, id_col, col in checks:
        if table not in tables:
            continue
        for marker in SYNTHETIC_MARKERS:
            rows = conn.execute(
                f"SELECT {id_col} AS row_id, {col} AS value "
                f"FROM {table} WHERE lower(coalesce({col}, '')) LIKE ? "
                f"ORDER BY {id_col} LIMIT 10",
                (f"%{marker}%",),
            ).fetchall()
            for row in rows:
                matches += 1
                if matches <= 20:
                    print(
                        f"  - {table}.id={row['row_id']} col={col} "
                        f"marker={marker!r} value={_preview(row['value'], 180)}"
                    )
    if not matches:
        print("  (none)")
    elif matches > 20:
        print(f"  ... {matches - 20} more suppressed")


def inspect_db(db_path: Path) -> None:
    print(f"--- Inspecting {db_path} ---")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = _table_names(conn)
        print(f"tables: {', '.join(sorted(tables))}")
        for table in ("campaigns", "sessions", "npcs", "session_notes"):
            if table not in tables:
                print(f"missing table: {table}")
        _inspect_campaigns(conn)
        _inspect_sessions(conn)
        _inspect_notes(conn, tables)
        _report_suspects(conn, tables)
    finally:
        conn.close()


def backup_and_rotate(db_path: Path, out_dir: Path, keep: int) -> None:
    target = backup_once(db_path, out_dir)
    removed = prune(out_dir, max(1, keep))
    print(f"\n[Backup] Created: {target}")
    if removed:
        print(f"[Rotation] Removed {len(removed)} old backup(s)")
    else:
        print(f"[Rotation] No pruning needed (limit {keep})")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inspect and back up the Pathfinder God campaign DB."
    )
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--keep", type=int, default=5)
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}", file=sys.stderr)
        return 1

    inspect_db(args.db)
    if not args.no_backup:
        backup_and_rotate(args.db, args.out, args.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
