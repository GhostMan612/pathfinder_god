# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# Pathfinder 2 SQLite (jrmiller82) YAML Importer — true schema
# Source: https://github.com/jrmiller82/pathfinder-2-sqlite | License: OGL
# Layout: data/*.yaml as {<listkey>: [{name, descr, source:[{abbr,
# page_start}], traits, level, ...}]} plus data/spells|monsters/*.yaml
# single-entity docs. data/sources.yaml maps abbr -> full book title.
# Inserts new rows and UPGRADES legacy Unknown Source rows.
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db_normalize import UNKNOWN, canonical_category, clean_content

FILE_CATEGORY = {
    "feats": "feat",
    "conditions": "condition",
    "backgrounds": "background",
    "weapons": "equipment",
    "armor": "equipment",
    "gear": "equipment",
    "items-staves": "equipment",
    "ammunition": "equipment",
    "weapongroups": "equipment",
    "itemcategories": None,
    "classes": "class",
    "classesadvancement": "classfeature",
    "actions": "action",
    "skills": "skill",
    "traits": "trait",
    "senses": "rule",
    "damage": "rule",
    "triggers": "rule",
    "requirements": "rule",
    "langs": "rule",
    "bulks": "rule",
    "basics": "rule",
    "familiars": "familiar abilities",
    "ancestriesheritages": "ancestry",
    "spells": "spell",
    "monsters": "bestiary",
    "sources": None,
}

ENTRY_FIELDS = (
    "actioncost", "level", "traditions", "cast", "range", "targets",
    "area", "duration", "trigger", "requirement", "frequency",
)


def flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for v in value:
            if isinstance(v, dict):
                d = v.get("descr") or v.get("name") or v.get("feat")
                parts.append(str(d) if d else "")
            else:
                parts.append(str(v))
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        return value.get("descr") or value.get("name") or ""
    return str(value)


class Pathfinder2SqliteImporter:
    def __init__(self, data_root: Path, db_path: Path):
        self.data_root = data_root
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.stats = {"seen": 0, "inserted": 0, "upgraded": 0, "skipped": 0, "errors": 0}
        self.abbr_map: dict[str, str] = {}

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

    def _load_abbr(self) -> None:
        p = self.data_root / "sources.yaml"
        if not p.exists():
            return
        try:
            doc = yaml.safe_load(open(p, encoding="utf-8"))
        except Exception:
            return
        items = doc if isinstance(doc, list) else doc.get("sources", doc.get("source", []))
        if isinstance(items, dict):
            items = [{"abbr": k, **(v if isinstance(v, dict) else {"name": v})} for k, v in items.items()]
        for item in items or []:
            if not isinstance(item, dict):
                continue
            abbr = str(item.get("abbr", "")).strip()
            name = str(item.get("name", "") or item.get("title", "")).strip()
            if abbr and name:
                self.abbr_map[abbr] = name

    def _source_book(self, entry: dict, fallback_file: str = "") -> str:
        sources = entry.get("source") or []
        if isinstance(sources, dict):
            sources = [sources]
        if sources and isinstance(sources[0], dict):
            abbr = str(sources[0].get("abbr", "")).strip()
            page = sources[0].get("page_start")
            base = self.abbr_map.get(abbr, abbr) if abbr else ""
            if base and page:
                return f"{base} p.{page}"
            return base or fallback_file
        if isinstance(sources, str) and sources.strip():
            return sources.strip()
        return fallback_file or "Pathfinder 2e OGL"

    def _content(self, name: str, source: str, entry: dict) -> str:
        chunks = [f"# {name}", f"**Source:** {source}"]
        traits = flatten(entry.get("traits"))
        if traits:
            chunks.append(f"**Traits:** {clean_content(traits)}")
        for field in ENTRY_FIELDS:
            value = flatten(entry.get(field))
            if value:
                chunks.append(f"**{field.replace('_', ' ').title()}:** {clean_content(value)}")
        prereqs = flatten(entry.get("prereqs"))
        if prereqs:
            chunks.append(f"**Prerequisites:** {clean_content(prereqs)}")
        descr = clean_content(entry.get("descr") or entry.get("description") or "")
        if descr:
            chunks.append(descr)
        short_d = clean_content(entry.get("short_descr") or "")
        if short_d and short_d not in descr:
            chunks.append(short_d)
        return "\n\n".join(chunks)

    def _handle(self, entry: Any, category: str, fallback_name: str = "") -> None:
        if not isinstance(entry, dict):
            self.stats["skipped"] += 1
            return
        name = str(entry.get("name", "") or fallback_name).strip()
        if not name:
            self.stats["skipped"] += 1
            return
        self.stats["seen"] += 1
        try:
            source = self._source_book(entry)
            content = self._content(name, source, entry)
            if len(content) < 40:
                self.stats["skipped"] += 1
                return
            cur = self.conn.execute(
                "SELECT rowid, source_book FROM rules"
                " WHERE system = '2E' AND name = ? COLLATE NOCASE LIMIT 1",
                (name,),
            ).fetchone()
            if cur is None:
                self.conn.execute(
                    "INSERT INTO rules (system, category, name, source_book, raw_content)"
                    " VALUES ('2E', ?, ?, ?, ?)",
                    (category, name, source, content),
                )
                self.stats["inserted"] += 1
            elif (cur[1] or UNKNOWN) == UNKNOWN:
                self.conn.execute(
                    "UPDATE rules SET category = ?, source_book = ?, raw_content = ?"
                    " WHERE rowid = ?",
                    (category, source, content, cur[0]),
                )
                self.stats["upgraded"] += 1
            else:
                self.stats["skipped"] += 1
        except Exception:
            self.stats["errors"] += 1

    def import_data(self, yaml_data_dir: Path) -> dict:
        self.connect()
        try:
            self._load_abbr()
            batch = 0
            for path in sorted(yaml_data_dir.glob("*.yaml")):
                category = FILE_CATEGORY.get(path.stem, canonical_category(path.stem))
                if category is None:
                    continue
                try:
                    doc = yaml.safe_load(open(path, encoding="utf-8"))
                except Exception:
                    self.stats["errors"] += 1
                    continue
                items: list = []
                if isinstance(doc, list):
                    items = doc
                elif isinstance(doc, dict):
                    for value in doc.values():
                        if isinstance(value, list):
                            items.extend(v for v in value if isinstance(v, dict))
                    if not items:
                        items = [doc]
                for entry in items:
                    self._handle(entry, category)
                    batch += 1
                    if batch % 2000 == 0:
                        self.conn.commit()
            for sub, category in (("spells", "spell"), ("monsters", "bestiary")):
                subdir = yaml_data_dir / sub
                if not subdir.exists():
                    continue
                for path in sorted(subdir.glob("*.yaml")):
                    try:
                        doc = yaml.safe_load(open(path, encoding="utf-8"))
                    except Exception:
                        self.stats["errors"] += 1
                        continue
                    fallback = path.stem.replace("_", " ").strip().title()
                    if isinstance(doc, list):
                        for entry in doc:
                            self._handle(entry, category, fallback)
                    else:
                        self._handle(doc, category, fallback)
                    batch += 1
                    if batch % 2000 == 0:
                        self.conn.commit()
            self.conn.commit()
            print(f"pfsqlite YAML import: {self.stats}")
            return self.stats
        finally:
            self.close()


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Import jrmiller82 YAML data")
    ap.add_argument("--yaml-path", required=True)
    ap.add_argument("--db-path", required=True)
    args = ap.parse_args()
    Pathfinder2SqliteImporter(Path(args.yaml_path), Path(args.db_path)).import_data(
        Path(args.yaml_path)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
