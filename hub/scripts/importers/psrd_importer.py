# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# PSRD 1e Importer - official Paizo PRD JSON via devonjones/PSRD-Data
# Source: https://github.com/devonjones/PSRD-Data | License: OGL (PRD text)
# Layout: psrd1e/<book>/<section>/*.json with {body|sections[], source,
# url pfsrd://...}. Inserts new rows and UPGRADES legacy Unknown Source
# rows with sourced official content.
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db_normalize import UNKNOWN, canonical_category, clean_content

SECTION_CATEGORY = {
    "spell": "spell",
    "feat": "feat",
    "class": "class",
    "race": "ancestry",
    "skill": "skill",
    "item": "equipment",
    "trap": "hazard",
    "rules": "rule",
    "affliction": "affliction",
    "animal_companion": "bestiary",
    "racial_trait": "ancestry",
    "monster": "bestiary",
    "creature": "bestiary",
    "deity": "deity",
    "archetype": "archetype",
    "prestige_class": "class",
}

SPELL_FIELDS = (
    "school", "level_text", "casting_time", "range", "saving_throw",
    "spell_resistance", "descriptor_text",
)


def pretty_book(dirname: str) -> str:
    return dirname.replace("_", " ").title()


def section_text(doc: dict) -> str:
    parts = []
    sections = doc.get("sections") or []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        label = (sec.get("name") or "").strip()
        body = clean_content(sec.get("body") or "")
        if not body:
            continue
        parts.append(f"**{label}:** {body}" if label else body)
    return "\n\n".join(parts)


class PsrdImporter:
    def __init__(self, psrd_root: Path, db_path: Path):
        self.psrd_root = psrd_root
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

    def _row(self, path: Path, book: str, section: str) -> Optional[dict]:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(doc, dict):
            return None
        name = (doc.get("name") or "").strip()
        if not name:
            name = path.stem.replace("_", " ").strip().title()
        source = (doc.get("source") or "").strip() or pretty_book(book)
        category = SECTION_CATEGORY.get(
            section, canonical_category(section)
        )
        chunks = []
        desc = (doc.get("description") or "").strip()
        if desc:
            chunks.append(clean_content(desc))
        body = clean_content(doc.get("body") or "")
        if body:
            chunks.append(body)
        sec = section_text(doc)
        if sec:
            chunks.append(sec)
        for field in SPELL_FIELDS:
            value = doc.get(field)
            if value:
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                chunks.append(f"**{field.replace('_', ' ').title()}:** {clean_content(str(value))}")
        text = "\n\n".join(c for c in chunks if c)
        if len(text) < 20:
            return None
        return {
            "system": "1E",
            "category": category,
            "name": name,
            "source_book": source,
            "raw_content": f"# {name}\n\n**Source:** {source}\n\n{text}",
        }

    def import_data(self) -> dict:
        self.connect()
        try:
            files = sorted(self.psrd_root.rglob("*.json"))
            batch = 0
            for path in files:
                try:
                    rel = path.relative_to(self.psrd_root)
                except ValueError:
                    continue
                if len(rel.parts) < 3:
                    continue
                book, section = rel.parts[0], rel.parts[1]
                self.stats["seen"] += 1
                try:
                    row = self._row(path, book, section)
                except Exception:
                    self.stats["errors"] += 1
                    continue
                if row is None:
                    self.stats["skipped"] += 1
                    continue
                cur = self.conn.execute(
                    "SELECT rowid, source_book FROM rules"
                    " WHERE system = '1E' AND name = ? COLLATE NOCASE LIMIT 1",
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
            print(f"PSRD import: {self.stats}")
            return self.stats
        finally:
            self.close()


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Import PSRD 1e official JSON")
    ap.add_argument("--psrd-path", required=True)
    ap.add_argument("--db-path", required=True)
    args = ap.parse_args()
    PsrdImporter(Path(args.psrd_path), Path(args.db_path)).import_data()
    return 0


if __name__ == "__main__":
    sys.exit(main())
