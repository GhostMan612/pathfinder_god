# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# Pf2ools Data Importer - PF2e open JSON, true schema
# Source: https://github.com/Pf2ools/pf2ools-data | License: MIT (scripts),
# Paizo content under Community Use Policy. Only data/core (Paizo) is read;
# data/homebrew is skipped. True file shape: {type, name{name.primary},
# source{page, ID}, data{entries[...]}}. Inserts new rows and UPGRADES
# legacy Unknown Source rows with sourced content.
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

TAG_RE = re.compile(r"\{@\w+\s+([^}|]+)(?:\|([^}]+))?\}")
UNKNOWN = "Unknown Source"

DATATYPE_CATEGORY = {
    "background": "background",
    "condition": "condition",
    "skill": "skill",
    "divineIntercession": "deity",
    "familiarAbility": "familiar abilities",
    "relicGift": "equipment",
}

SKIP_DATATYPES = {"event"}


def strip_tags(text: str) -> str:
    def repl(m: re.Match) -> str:
        return (m.group(2) or m.group(1)).strip()

    text = TAG_RE.sub(repl, text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("�", "")
    return re.sub(r"\s+", " ", text).strip()


class Pf2oolsImporter:
    def __init__(self, pf2ools_root: Path, db_path: Path):
        self.pf2ools_root = pf2ools_root
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.stats = {"seen": 0, "inserted": 0, "upgraded": 0, "skipped": 0, "errors": 0}

    def connect(self) -> None:
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=OFF")
        self.conn.execute("PRAGMA synchronous=OFF")
        self.conn.execute("PRAGMA cache_size=-64000")

    def close(self) -> None:
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def _row(self, path: Path) -> Optional[dict]:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(doc, dict):
            return None
        datatype = path.parent.name
        if datatype in SKIP_DATATYPES or datatype not in DATATYPE_CATEGORY:
            return None
        name_obj = doc.get("name") or {}
        name = (name_obj.get("primary") or name_obj.get("display") or "").strip()
        if not name:
            return None
        source_book = path.parents[1].name
        page = (doc.get("source") or {}).get("page")
        if page:
            source_book = f"{source_book} p.{page}"
        data = doc.get("data") or {}
        entries = data.get("entries") or []
        if isinstance(entries, str):
            entries = [entries]
        body = "\n\n".join(
            strip_tags(str(e)) for e in entries if str(e).strip()
        )
        if len(body) < 20:
            return None
        content = f"# {name}\n\n**Source:** {source_book}\n\n{body}"
        return {
            "system": "2E",
            "category": DATATYPE_CATEGORY[datatype],
            "name": name,
            "source_book": source_book,
            "raw_content": content,
        }

    def import_data(self) -> dict:
        self.connect()
        try:
            core = self.pf2ools_root / "data" / "core"
            files = sorted(core.rglob("*.json")) if core.exists() else []
            batch = 0
            for path in files:
                if len(path.relative_to(core).parts) < 3:
                    continue
                self.stats["seen"] += 1
                try:
                    row = self._row(path)
                except Exception:
                    self.stats["errors"] += 1
                    continue
                if row is None:
                    self.stats["skipped"] += 1
                    continue
                cur = self.conn.execute(
                    "SELECT rowid, source_book, length(raw_content) FROM rules"
                    " WHERE system = '2E' AND name = ? COLLATE NOCASE LIMIT 1",
                    (row["name"],),
                ).fetchone()
                if cur is None:
                    self.conn.execute(
                        "INSERT INTO rules (system, category, name, source_book, raw_content)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (row["system"], row["category"], row["name"],
                         row["source_book"], row["raw_content"]),
                    )
                    self.stats["inserted"] += 1
                elif (cur[1] or UNKNOWN) == UNKNOWN:
                    self.conn.execute(
                        "UPDATE rules SET category = ?, source_book = ?, raw_content = ?"
                        " WHERE rowid = ?",
                        (row["category"], row["source_book"], row["raw_content"], cur[0]),
                    )
                    self.stats["upgraded"] += 1
                else:
                    self.stats["skipped"] += 1
                batch += 1
                if batch % 2000 == 0:
                    self.conn.commit()
            self.conn.commit()
            print(f"Pf2ools import: {self.stats}")
            return self.stats
        finally:
            self.close()


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Import Pf2ools open data")
    ap.add_argument("--pf2ools-path", required=True)
    ap.add_argument("--db-path", required=True)
    args = ap.parse_args()
    Pf2oolsImporter(Path(args.pf2ools_path), Path(args.db_path)).import_data()
    return 0


if __name__ == "__main__":
    sys.exit(main())
