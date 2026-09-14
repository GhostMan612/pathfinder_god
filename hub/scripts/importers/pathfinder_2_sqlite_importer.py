# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# Pathfinder 2 SQLite (jrmiller82) YAML Importer
# Source: https://github.com/jrmiller82/pathfinder-2-sqlite | License: OGL/Community Use

import yaml
import sqlite3
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class Pathfinder2SqliteImporter:
    """Imports jrmiller82/pathfinder-2-sqlite YAML data into Pathfinder RAG database."""

    def __init__(self, yaml_root: Path, db_path: Path):
        self.yaml_root = yaml_root
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.stats = {
            "total": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "by_category": {}
        }

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _get_category_from_filename(self, filename: str) -> str:
        """Map YAML filename to category."""
        stem = filename.stem.lower()
        mapping = {
            "class": "class",
            "ancestry": "ancestry",
            "background": "background",
            "feat": "feat",
            "spell": "spell",
            "item": "equipment",
            "weapon": "equipment",
            "armor": "equipment",
            "shield": "equipment",
            "condition": "condition",
            "action": "action",
            "creature": "bestiary",
            "deity": "deity",
            "skill": "skill",
            "archetype": "archetype",
            "background": "background",
            "classfeature": "classfeature",
            "ancestryfeature": "ancestryfeature",
        }
        for key, cat in mapping.items():
            if key in stem:
                return cat
        return "unknown"

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _build_content(self, data: Dict[str, Any], category: str) -> str:
        parts = []

        name = data.get("name", "")
        if name:
            parts.append(f"# {name}")

        source = data.get("source", data.get("sourceBook", ""))
        if source:
            parts.append(f"**Source:** {source}")

        level = data.get("level")
        if level is not None:
            parts.append(f"**Level:** {level}")

        traits = data.get("traits", [])
        if traits:
            if isinstance(traits, list):
                parts.append(f"**Traits:** {', '.join(traits)}")
            else:
                parts.append(f"**Traits:** {traits}")

        # Description fields
        for field in ["description", "description_short", "entries", "text", "benefit", "normal", "special", "requirements", "prerequisites", "trigger", "effect"]:
            value = data.get(field)
            if value:
                if isinstance(value, list):
                    value = "\n".join(str(v) for v in value)
                if isinstance(value, str) and value.strip():
                    parts.append(self._clean_text(value))
                    break

        # Spell-specific
        for field in ["tradition", "school", "cast", "range", "targets", "area", "duration", "savingThrow", "heightened"]:
            value = data.get(field)
            if value:
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                parts.append(f"**{field.replace('_', ' ').title()}:** {value}")

        # Equipment-specific
        for field in ["price", "bulk", "hands", "damage", "damage_type", "category", "group", "reload", "range", "capacity"]:
            value = data.get(field)
            if value:
                parts.append(f"**{field.replace('_', ' ').title()}:** {value}")

        return "\n\n".join(parts)

    def _extract_source_book(self, data: Dict[str, Any]) -> str:
        for field in ["source", "sourceBook", "book", "source_book"]:
            value = data.get(field)
            if value:
                if isinstance(value, dict):
                    return value.get("name", value.get("abbreviation", str(value)))
                return str(value)
        return "Pathfinder 2e OGL"

    def _process_yaml_entry(self, data: Dict[str, Any], category: str) -> Optional[Dict[str, Any]]:
        name = data.get("name", "")
        if not name:
            return None

        content = self._build_yaml_content(data, category)
        if not content or len(content) < 10:
            return None

        source_book = data.get("source", data.get("sourceBook", "Pathfinder 2e OGL"))
        if isinstance(source_book, dict):
            source_book = source_book.get("name", source_book.get("abbreviation", str(source_book)))

        return {
            "system": "2e",
            "category": category,
            "name": data.get("name", ""),
            "source_book": str(source_book),
            "raw_content": content
        }

    def _build_yaml_content(self, data: Dict[str, Any], category: str) -> str:
        parts = []

        name = data.get("name", "")
        if name:
            parts.append(f"# {name}")

        source = data.get("source", "")
        if source:
            parts.append(f"**Source:** {source}")

        level = data.get("level")
        if level is not None:
            parts.append(f"**Level:** {level}")

        traits = data.get("traits", [])
        if traits:
            if isinstance(traits, list):
                parts.append(f"**Traits:** {', '.join(traits)}")
            else:
                parts.append(f"**Traits:** {traits}")

        # Description
        for field in ["description", "description_short", "entries", "text", "benefit", "normal", "special", "requirements", "prerequisites", "trigger", "effect"]:
            value = data.get(field)
            if value:
                if isinstance(value, list):
                    value = "\n".join(str(v) for v in value)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
                    break

        # Spell fields
        for field in ["tradition", "school", "cast", "range", "targets", "area", "duration", "savingThrow", "heightened"]:
            value = data.get(field)
            if value:
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                parts.append(f"**{field.replace('_', ' ').title()}:** {value}")

        # Equipment fields
        for field in ["price", "bulk", "hands", "damage", "damage_type", "category", "group", "reload", "range", "capacity"]:
            value = data.get(field)
            if value:
                parts.append(f"**{field.replace('_', ' ').title()}:** {value}")

        return "\n\n".join(parts)

    def import_data(self, yaml_data_dir: Path):
        self.connect()
        try:
            for yaml_file in yaml_data_dir.rglob("*.yaml"):
                self._process_yaml_file(yaml_file)
            for yaml_file in yaml_data_dir.rglob("*.yml"):
                self._process_file(yaml_file)

            print(f"\n=== Pathfinder 2 SQLite Import Complete ===")
            print(f"Total processed: {self.stats['total']}")
            print(f"Imported: {self.stats['imported']}")
            print(f"Skipped: {self.stats['skipped']}")
            print(f"Errors: {self.stats['errors']}")
            print(f"By category: {self.stats['by_category']}")

        finally:
            self.close()

    def _process_yaml_file(self, yaml_file: Path):
        """Process a single YAML file."""
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to parse {yaml_file}: {e}")
            self.stats["errors"] += 1
            return

        category = self._get_category_from_filename(yaml_file)

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ["entries", "data", "items", "results"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items:
                items = [data]
        else:
            return

        for entry in items:
            self.stats["total"] += 1
            try:
                processed = self._process_yaml_entry(entry, category)
                if processed:
                    self._insert_entry(processed)
                    self.stats["imported"] += 1
                    cat = processed["category"]
                    self.stats["by_category"][cat] = self.stats["by_category"].get(cat, 0) + 1
                else:
                    self.stats["skipped"] += 1
            except Exception as e:
                self.stats["errors"] += 1
                print(f"Error processing entry in {yaml_file}: {e}")

    def _process_file(self, yaml_file: Path):
        self._process_yaml_file(yaml_file)

    def _insert_entry(self, entry: Dict[str, Any]):
        cursor = self.conn.execute(
            "SELECT 1 FROM rules WHERE system = ? AND name = ? AND source_book = ?",
            (entry["system"], entry["name"], entry["source_book"])
        )
        if cursor.fetchone():
            self.stats["skipped"] += 1
            return

        self.conn.execute(
            """INSERT INTO rules (system, category, name, source_book, raw_content)
               VALUES (?, ?, ?, ?, ?)""",
            (entry["system"], entry["category"], entry["name"], entry["source_book"], entry["raw_content"])
        )
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import jrmiller82/pathfinder-2-sqlite YAML data")
    parser.add_argument("--yaml-path", required=True, help="Path to pathfinder-2-sqlite data/yaml directory")
    parser.add_argument("--db-path", required=True, help="Path to output SQLite database")
    args = parser.parse_args()

    yaml_path = Path(args.yaml_path)
    if not yaml_path.exists():
        print(f"Error: YAML path does not exist: {yaml_path}")
        sys.exit(1)

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    importer = Pathfinder2SqliteImporter(yaml_path, db_path)
    importer.import_data(yaml_path)


if __name__ == "__main__":
    main()