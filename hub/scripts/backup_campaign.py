# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Snapshot data/campaign.db so a campaign is never lost to one bad file.

BP-07 Stage 6. Every piece of GM continuity lives in this one SQLite file:
the evergreen chronicle (campaigns.summary), the live combat scene
(campaigns.combat_json), all sessions with their raw logs and facts, and the
entity ledger (npcs/locations/items/quests/decisions/party). Since Stage 4 the
hub writes to it automatically every eighth turn, so a corrupt or truncated
write now costs you real campaign history rather than nothing.

Uses sqlite3's online backup API rather than shutil.copy: the source file may be
mid-transaction or in WAL mode, and a plain file copy can capture a torn page.
The backup API takes a consistent snapshot of a live database.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "data" / "campaign.db"
DEFAULT_OUT = REPO_ROOT / "data" / "backups"


def backup_once(db_path: Path, out_dir: Path) -> Path:
    """Write one consistent timestamped snapshot. Returns the new path."""
    if not db_path.exists():
        raise FileNotFoundError(f"no campaign database at {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"campaign-{stamp}.db"
    # Two launches inside the same second would otherwise resolve to the same
    # path and the second snapshot would silently overwrite the first.
    bump = 2
    while target.exists():
        target = out_dir / f"campaign-{stamp}-{bump}.db"
        bump += 1

    # sqlite3 backup API: consistent snapshot even while the hub is writing.
    # A failure at any point below removes the partial snapshot, so a broken
    # run can never leave a garbage campaign-*.db that prune would keep.
    try:
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            dst = sqlite3.connect(str(target))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        # Prove the snapshot is a real, readable database with our tables before we
        # call it a backup. A file that exists but cannot be opened is not a backup.
        check = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        try:
            names = {r[0] for r in check.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            check.close()
        for required in ("campaigns", "sessions", "npcs"):
            if required not in names:
                raise RuntimeError(f"snapshot missing expected table {required!r}")
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return target


def prune(out_dir: Path, keep: int) -> list[Path]:
    """Keep the newest `keep` snapshots; delete the rest. Returns deleted."""
    snaps = sorted(out_dir.glob("campaign-*.db"), key=lambda p: p.name, reverse=True)
    removed = []
    for old in snaps[keep:]:
        try:
            old.unlink()
            removed.append(old)
        except OSError as exc:  # a locked snapshot is not worth crashing over
            print(f"  ! could not remove {old.name}: {exc}", file=sys.stderr)
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="Back up the Pathfinder God campaign DB.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="campaign.db to snapshot")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="backup directory")
    ap.add_argument("--keep", type=int, default=10, help="snapshots to retain")
    args = ap.parse_args()

    try:
        target = backup_once(args.db, args.out)
    except FileNotFoundError as exc:
        print(f"skip: {exc}")
        return 0
    except Exception as exc:
        print(f"backup FAILED: {exc}", file=sys.stderr)
        return 1

    size_mb = target.stat().st_size / (1024 * 1024)
    removed = prune(args.out, max(1, args.keep))
    print(f"backup ok: {target} ({size_mb:.2f} MB)")
    if removed:
        print(f"pruned {len(removed)} old snapshot(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())