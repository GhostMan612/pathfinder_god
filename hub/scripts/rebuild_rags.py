# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Rebuild the local Pathfinder RAG databases.

Mirrors the flow described in the original ``LOCAL_RAG_GUIDE.md``: run the two
builder scripts (which you provide) to regenerate the databases into ``data/``.

    python hub/scripts/rebuild_rags.py

Drop your ``build_rag.py`` and ``build_2e_rag.py`` next to this file. They are the
source of truth for the 500MB+ databases, which is why *they* are committed and the
``.db`` files are not.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPTS_DIR.parents[1] / "data"
NEW_DB = DATA_DIR / "pathfinder_rag.db.new"
LIVE_DB = DATA_DIR / "pathfinder_rag.db"
BAK_DB = DATA_DIR / "pathfinder_rag.db.bak"
BUILDERS = ["build_rag.py", "build_2e_rag.py"]


def main() -> int:
    missing = [b for b in BUILDERS if not (SCRIPTS_DIR / b).exists()]
    if missing:
        print("Missing builder script(s):", ", ".join(missing))
        print(f"Place them in {SCRIPTS_DIR} (see data/SCHEMA.md).")
        return 1

    if NEW_DB.exists():
        NEW_DB.unlink()

    for builder in BUILDERS:
        path = SCRIPTS_DIR / builder
        print(f"=== Running {builder} ===", flush=True)
        try:
            runpy.run_path(str(path), run_name="__main__")
        except SystemExit as e:
            if e.code not in (None, 0):
                print(f"{builder} exited with code {e.code}; aborting.")
                return int(e.code or 1)

    if not NEW_DB.exists():
        print("Rebuild failed: no pathfinder_rag.db.new produced.")
        return 1

    import sqlite3

    conn = sqlite3.connect(str(NEW_DB))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
        by_sys = list(conn.execute("SELECT system, COUNT(*) FROM rules GROUP BY system"))
        by_cat = list(
            conn.execute(
                "SELECT category, COUNT(*) c FROM rules GROUP BY category ORDER BY c DESC LIMIT 15"
            )
        )
        unknown = conn.execute(
            "SELECT COUNT(*) FROM rules WHERE source_book = 'Unknown Source'"
        ).fetchone()[0]
    finally:
        conn.close()
    print(f"New DB integrity: {integrity} rows={total} by_system={by_sys}")
    print(f"Top categories: {by_cat}")
    print(f"Unknown Source rows: {unknown}")
    if integrity != "ok" or total == 0:
        print("Rebuild failed validation; live DB untouched.")
        return 1

    if LIVE_DB.exists():
        if BAK_DB.exists():
            BAK_DB.unlink()
        LIVE_DB.rename(BAK_DB)
        print(f"Backed up live DB to {BAK_DB.name}")
    NEW_DB.rename(LIVE_DB)

    conn = sqlite3.connect(str(LIVE_DB))
    try:
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()
    print("Done. Live pathfinder_rag.db rebuilt, vacuumed, analyzed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
