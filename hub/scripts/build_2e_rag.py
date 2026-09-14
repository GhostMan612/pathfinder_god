# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Build the 2e side of the unified Pathfinder RAG database.

Appends normalized + deduped legacy 2E rows into data/pathfinder_rag.db.new
(created by build_rag.py). rebuild_rags.py validates and swaps into place.

Optional: --pf2ools PATH --yaml PATH import open data first (legacy dupes
of imported rows are skipped).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from db_normalize import (
    UNKNOWN,
    canonical_category,
    clean_content,
    dedupe_key,
    normalize_edition,
    pick_winner,
    repair_source,
)

REPO_ROOT = SCRIPTS_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data"
LEGACY_DB = DATA_DIR / "pathfinder_rag.db"
NEW_DB = DATA_DIR / "pathfinder_rag.db.new"

SCHEMA_SQL = """CREATE VIRTUAL TABLE IF NOT EXISTS rules USING fts5(
    name, raw_content, system, category, source_book
)"""


def load_legacy_rows() -> list[tuple]:
    if not LEGACY_DB.exists():
        print("build_2e_rag: no legacy DB, 2e side empty")
        return []
    src = sqlite3.connect(f"file:{LEGACY_DB}?mode=ro", uri=True)
    try:
        rows = src.execute(
            "SELECT system, category, name, source_book, raw_content "
            "FROM rules WHERE system = '2E'"
        ).fetchall()
    finally:
        src.close()
    print(f"build_2e_rag: read {len(rows)} legacy 2E rows")
    return rows


def normalize_rows(rows: list[tuple]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for system, category, name, source_book, raw_content in rows:
        if not (name or "").strip():
            continue
        content = clean_content(raw_content)
        if len(content) < 20:
            continue
        cat, src = repair_source(category, source_book)
        sys_ed = normalize_edition(system)
        row = {
            "system": sys_ed,
            "category": cat,
            "name": (name or "").strip(),
            "source_book": src,
            "raw_content": content,
        }
        groups[dedupe_key(sys_ed, row["name"], cat)].append(row)
    winners = [pick_winner(g) for g in groups.values()]
    print(f"build_2e_rag: {len(rows)} -> {len(winners)} after normalize+dedupe")
    return winners


def tune(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA locking_mode=EXCLUSIVE")


def insert_winners(conn: sqlite3.Connection, winners: list[dict]) -> tuple[int, int]:
    existing = {
        (r[0], (r[1] or "").lower())
        for r in conn.execute("SELECT system, name FROM rules")
    }
    fresh, skipped = [], 0
    for w in winners:
        if (w["system"], w["name"].lower()) in existing:
            skipped += 1
            continue
        existing.add((w["system"], w["name"].lower()))
        fresh.append(
            (w["system"], w["category"], w["name"], w["source_book"], w["raw_content"])
        )
    for i in range(0, len(fresh), 2000):
        conn.executemany(
            "INSERT INTO rules (system, category, name, source_book, raw_content)"
            " VALUES (?, ?, ?, ?, ?)",
            fresh[i : i + 2000],
        )
        conn.commit()
    return len(fresh), skipped


def maybe_import_external(new_db: Path, pf2ools: str | None, yaml_dir: str | None) -> None:
    if pf2ools:
        from importers.pf2ools_importer import Pf2oolsImporter

        print(f"build_2e_rag: importing Pf2ools from {pf2ools}")
        Pf2oolsImporter(Path(pf2ools), new_db).import_data()
    if yaml_dir:
        from importers.pathfinder_2_sqlite_importer import Pathfinder2SqliteImporter

        print(f"build_2e_rag: importing YAML from {yaml_dir}")
        Pathfinder2SqliteImporter(Path(yaml_dir), new_db).import_data(Path(yaml_dir))


def main() -> int:
    ap = argparse.ArgumentParser(description="Build 2e side of unified RAG DB")
    ap.add_argument("--pf2ools", default=None)
    ap.add_argument("--yaml", default=None)
    args = ap.parse_args()

    if not NEW_DB.exists():
        c0 = sqlite3.connect(str(NEW_DB))
        try:
            tune(c0)
            c0.execute(SCHEMA_SQL)
            c0.commit()
        finally:
            c0.close()
    conn = sqlite3.connect(str(NEW_DB))
    try:
        tune(conn)
        conn.execute(SCHEMA_SQL)
        maybe_import_external(NEW_DB, args.pf2ools, args.yaml)
        winners = normalize_rows(load_legacy_rows())
        inserted, skipped = insert_winners(conn, winners)
        print(f"build_2e_rag: inserted={inserted} skipped-dup={skipped}", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
