# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Portable campaign and character SQLite snapshots.

The live hub keeps every campaign in one ``campaign.db``. These helpers build a
standalone file from ``schema.sql`` for one campaign or one character, and import
that file into a new (or replacement) campaign with fresh row ids. The exported
campaign row always uses ``id = 1`` inside the file; import remaps ids rather
than trusting the source ids.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"

#: All campaign-scoped tables required in an exported campaign file. The order
#: here is only the export copy order; import uses its own dependency order.
CAMPAIGN_TABLES = (
    "campaigns",
    "sessions",
    "npcs",
    "locations",
    "items",
    "quests",
    "player_decisions",
    "party_members",
    "session_notes",
    "combatants",
    "campaign_turns",
    "solo_state",
    "encounters",
    "location_edges",
    "campaign_events",
)

REQUIRED_TABLES = set(CAMPAIGN_TABLES)

#: Keys in encounter/event JSON that point at rows remapped during import.
_JSON_ID_KEYS = {
    "npc_id": "npcs",
    "combatant_id": "combatants",
    "item_id": "items",
    "location_id": "locations",
    "encounter_id": "encounters",
}


class PortabilityError(ValueError):
    """A .db file is corrupt, the wrong version, or missing required tables."""


def _schema_sql() -> str:
    return (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    ]


def _insert_row(
    conn: sqlite3.Connection,
    table: str,
    row: dict[str, Any],
    *,
    campaign_id: int | None = None,
    drop: tuple[str, ...] = (),
    overrides: dict[str, Any] | None = None,
) -> int | None:
    data = {key: value for key, value in row.items() if key not in drop}
    if campaign_id is not None:
        data["campaign_id"] = campaign_id
    if overrides:
        data.update(overrides)
    columns = [column for column in _table_columns(conn, table) if column in data]
    if not columns:
        return None
    placeholders = ", ".join("?" for _ in columns)
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    )
    cursor = conn.execute(sql, [data[column] for column in columns])
    return int(cursor.lastrowid) if cursor.lastrowid is not None else None


def _create_standalone(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(_schema_sql())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_embeddings (
            campaign_id INTEGER NOT NULL,
            session_num INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            vector_blob BLOB NOT NULL,
            PRIMARY KEY (campaign_id, session_num)
        )
        """
    )
    conn.execute("PRAGMA user_version = 1")
    return conn


def _set_meta(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    conn.execute("DELETE FROM meta")
    conn.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        list(values.items()),
    )


def _source_rows(
    conn: sqlite3.Connection,
    table: str,
    where: str = "campaign_id = ?",
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    if table not in _table_names(conn):
        return []
    return [
        dict(row)
        for row in conn.execute(f"SELECT * FROM {table} WHERE {where}", params)
    ]


def _read_export_bytes(conn: sqlite3.Connection) -> bytes:
    conn.commit()
    check = conn.execute("PRAGMA foreign_key_check").fetchall()
    if check:
        raise PortabilityError("exported file has foreign key violations")
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise PortabilityError("exported file failed integrity_check")
    path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    conn.close()
    try:
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


def export_campaign_db(repo: Any, campaign_id: int) -> bytes:
    """Build a standalone SQLite file for one campaign."""
    with closing(sqlite3.connect(repo.db_path)) as source:
        source.row_factory = sqlite3.Row
        campaign = source.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if campaign is None:
            raise PortabilityError(f"no campaign {campaign_id}")
        rows = {
            table: (
                [dict(campaign)]
                if table == "campaigns"
                else _source_rows(source, table, params=(campaign_id,))
            )
            for table in CAMPAIGN_TABLES
        }
        embeddings = _source_rows(
            source, "session_embeddings", params=(campaign_id,)
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        temp_path = handle.name
    dest = _create_standalone(temp_path)
    try:
        for table in CAMPAIGN_TABLES:
            for row in rows[table]:
                if table == "campaigns":
                    row = dict(row)
                    row["id"] = 1
                    _insert_row(dest, table, row)
                else:
                    _insert_row(
                        dest,
                        table,
                        row,
                        campaign_id=1,
                    )
        for row in embeddings:
            _insert_row(dest, "session_embeddings", row, campaign_id=1)
        _set_meta(
            dest,
            {
                "schema_version": SCHEMA_VERSION,
                "exported_from": str(campaign["name"]),
                "exported_at": datetime.now(UTC).isoformat(),
                "source_campaign_id": str(campaign_id),
            },
        )
        return _read_export_bytes(dest)
    except Exception:
        dest.close()
        Path(temp_path).unlink(missing_ok=True)
        raise


def _load_export(path: str) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise PortabilityError(f"not a valid SQLite file: {exc}") from exc
        if integrity is None or integrity[0] != "ok":
            raise PortabilityError("SQLite integrity_check failed")
        tables = _table_names(conn)
        missing = REQUIRED_TABLES - tables
        if missing:
            raise PortabilityError(
                "missing required tables: " + ", ".join(sorted(missing))
            )
        meta = {
            str(row["key"]): str(row["value"])
            for row in conn.execute("SELECT key, value FROM meta").fetchall()
        }
        version = meta.get("schema_version")
        if version != SCHEMA_VERSION:
            raise PortabilityError(
                f"schema version {version!r} does not match {SCHEMA_VERSION!r}"
            )
        campaign_rows = conn.execute("SELECT * FROM campaigns").fetchall()
        if len(campaign_rows) != 1:
            raise PortabilityError(
                "campaign file must contain exactly one campaign row"
            )
        campaign = dict(campaign_rows[0])
        rows = {
            table: (
                []
                if table == "campaigns"
                else _source_rows(conn, table, where="1 = 1")
            )
            for table in CAMPAIGN_TABLES
        }
        rows["session_embeddings"] = _source_rows(
            conn, "session_embeddings", where="1 = 1"
        )
        return campaign, rows
    finally:
        conn.close()


def _remap_json(value: Any, maps: dict[str, dict[int, int]]) -> Any:
    if isinstance(value, dict):
        remapped: dict[str, Any] = {}
        for key, item in value.items():
            target = maps.get(_JSON_ID_KEYS.get(key))
            if target is not None and isinstance(item, int):
                remapped[key] = target.get(item, item)
            else:
                remapped[key] = _remap_json(item, maps)
        return remapped
    if isinstance(value, list):
        return [_remap_json(item, maps) for item in value]
    return value


def _remap_json_text(
    text: str | None, maps: dict[str, dict[int, int]]
) -> str | None:
    if not text:
        return text
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return text
    return json.dumps(_remap_json(value, maps))


def _remap_id_list(
    text: str | None, mapping: dict[int, int]
) -> str | None:
    if not text:
        return text
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return text
    if not isinstance(value, list):
        return text
    remapped = [
        mapping.get(item, item) if isinstance(item, int) else item
        for item in value
    ]
    return json.dumps(remapped)


def import_campaign_db(
    repo: Any,
    source_path: str,
    *,
    campaign_id: int = 1,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Import a standalone campaign file as a new campaign or replacement."""
    campaign, rows = _load_export(source_path)
    source_id = int(campaign["id"])

    with closing(sqlite3.connect(repo.db_path)) as dest:
        dest.row_factory = sqlite3.Row
        dest.execute("PRAGMA foreign_keys = ON")
        if replace_existing:
            dest.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
            dest.execute(
                """
                INSERT INTO campaigns
                    (id, name, edition, summary, combat_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, COALESCE(?, datetime('now')),
                        COALESCE(?, datetime('now')))
                """,
                (
                    campaign_id,
                    campaign.get("name") or f"Campaign {campaign_id}",
                    campaign.get("edition") or "2e",
                    campaign.get("summary"),
                    campaign.get("combat_json"),
                    campaign.get("created_at"),
                    campaign.get("updated_at"),
                ),
            )
            target_id = campaign_id
        else:
            cursor = dest.execute(
                "INSERT INTO campaigns (name, edition, summary, combat_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    campaign.get("name") or "Imported Campaign",
                    campaign.get("edition") or "2e",
                    campaign.get("summary"),
                    campaign.get("combat_json"),
                ),
            )
            target_id = int(cursor.lastrowid)
            dest.execute(
                """
                UPDATE campaigns SET created_at = COALESCE(?, created_at),
                    updated_at = COALESCE(?, updated_at)
                WHERE id = ?
                """,
                (
                    campaign.get("created_at"),
                    campaign.get("updated_at"),
                    target_id,
                ),
            )

        maps: dict[str, dict[int, int]] = {
            table: {} for table in REQUIRED_TABLES
        }
        source_rows_by_id: dict[str, dict[int, dict[str, Any]]] = {
            "locations": {
                int(row["id"]): row for row in rows["locations"]
            }
        }

        for row in rows["locations"]:
            new_id = _insert_row(
                dest,
                "locations",
                row,
                campaign_id=target_id,
                drop=("id", "campaign_id", "parent_id"),
            )
            if new_id is not None:
                maps["locations"][int(row["id"])] = new_id

        for row in rows["npcs"]:
            new_id = _insert_row(
                dest,
                "npcs",
                row,
                campaign_id=target_id,
                drop=("id", "campaign_id", "location_id"),
                overrides={
                    "location_id": maps["locations"].get(row.get("location_id"))
                },
            )
            if new_id is not None:
                maps["npcs"][int(row["id"])] = new_id

        for row in rows["items"]:
            new_id = _insert_row(
                dest,
                "items",
                row,
                campaign_id=target_id,
                drop=("id", "campaign_id", "holder_id", "location_id"),
                overrides={
                    "holder_id": maps["npcs"].get(row.get("holder_id")),
                    "location_id": maps["locations"].get(row.get("location_id")),
                },
            )
            if new_id is not None:
                maps["items"][int(row["id"])] = new_id

        for row in rows["quests"]:
            _insert_row(
                dest,
                "quests",
                row,
                campaign_id=target_id,
                drop=("id", "campaign_id", "giver_id"),
                overrides={"giver_id": maps["npcs"].get(row.get("giver_id"))},
            )

        for table in (
            "party_members",
            "sessions",
            "player_decisions",
            "session_notes",
            "combatants",
            "campaign_turns",
        ):
            for row in rows[table]:
                new_id = _insert_row(
                    dest,
                    table,
                    row,
                    campaign_id=target_id,
                    drop=("id", "campaign_id"),
                )
                if table == "combatants" and new_id is not None:
                    maps["combatants"][int(row["id"])] = new_id

        if rows["solo_state"]:
            row = dict(rows["solo_state"][0])
            _insert_row(
                dest,
                "solo_state",
                row,
                campaign_id=target_id,
                drop=("campaign_id", "current_location_id", "active_combatant_id"),
                overrides={
                    "current_location_id": maps["locations"].get(
                        row.get("current_location_id")
                    ),
                    "active_combatant_id": maps["combatants"].get(
                        row.get("active_combatant_id")
                    ),
                    "turn_order_json": _remap_id_list(
                        row.get("turn_order_json"), maps["combatants"]
                    ),
                },
            )

        for row in rows["encounters"]:
            state_json = _remap_json_text(row.get("state_json"), maps)
            new_id = _insert_row(
                dest,
                "encounters",
                row,
                campaign_id=target_id,
                drop=("id", "campaign_id", "location_id"),
                overrides={
                    "location_id": maps["locations"].get(row.get("location_id")),
                    "state_json": state_json or "{}",
                },
            )
            if new_id is not None:
                maps["encounters"][int(row["id"])] = new_id

        for row in rows["location_edges"]:
            _insert_row(
                dest,
                "location_edges",
                row,
                campaign_id=target_id,
                drop=(
                    "id",
                    "campaign_id",
                    "from_location_id",
                    "to_location_id",
                ),
                overrides={
                    "from_location_id": maps["locations"].get(
                        row.get("from_location_id")
                    ),
                    "to_location_id": maps["locations"].get(
                        row.get("to_location_id")
                    ),
                },
            )

        for row in rows["campaign_events"]:
            _insert_row(
                dest,
                "campaign_events",
                row,
                campaign_id=target_id,
                drop=("id", "campaign_id", "location_id", "encounter_id"),
                overrides={
                    "location_id": maps["locations"].get(row.get("location_id")),
                    "encounter_id": maps["encounters"].get(
                        row.get("encounter_id")
                    ),
                    "data_json": _remap_json_text(row.get("data_json"), maps)
                    or "{}",
                },
            )

        for row in rows["session_embeddings"]:
            _insert_row(
                dest,
                "session_embeddings",
                row,
                campaign_id=target_id,
                drop=("campaign_id",),
            )

        # location parent_id is a self-reference, so it is applied after every
        # location has a new id.
        for old_id, new_id in maps["locations"].items():
            old_parent = source_rows_by_id["locations"][old_id].get("parent_id")
            new_parent = maps["locations"].get(old_parent)
            dest.execute(
                "UPDATE locations SET parent_id = ? WHERE id = ?",
                (new_parent, new_id),
            )

        violations = dest.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise PortabilityError(
                f"import produced {len(violations)} foreign key violation(s)"
            )
        dest.execute(
            "INSERT INTO meta (key, value) VALUES ('imported_from', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(campaign.get("name") or "Imported Campaign"),),
        )
        dest.execute(
            "INSERT INTO meta (key, value) VALUES ('imported_at', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (datetime.now(UTC).isoformat(),),
        )
        dest.execute("PRAGMA user_version = 1")
        dest.commit()

    return {
        "campaign_id": target_id,
        "name": str(campaign.get("name") or "Imported Campaign"),
        "replaced": replace_existing,
        "source_campaign_id": source_id,
    }


def export_character_db(repo: Any, campaign_id: int, name: str) -> bytes:
    """Build a standalone file for one hero, party row, items, and decisions."""
    with closing(sqlite3.connect(repo.db_path)) as source:
        source.row_factory = sqlite3.Row
        campaign = source.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if campaign is None:
            raise PortabilityError(f"no campaign {campaign_id}")
        party = source.execute(
            "SELECT * FROM party_members WHERE campaign_id = ? AND name = ?",
            (campaign_id, name),
        ).fetchone()
        if party is None:
            raise PortabilityError(f"no character {name!r} in campaign {campaign_id}")
        combatant = source.execute(
            "SELECT * FROM combatants WHERE campaign_id = ? AND name = ? "
            "AND kind = 'hero' ORDER BY id LIMIT 1",
            (campaign_id, name),
        ).fetchone()
        npc = source.execute(
            "SELECT * FROM npcs WHERE campaign_id = ? AND name = ?",
            (campaign_id, name),
        ).fetchone()
        item_rows = source.execute(
            "SELECT * FROM items WHERE campaign_id = ? AND ("
            "holder_id = ? OR notes LIKE ?)",
            (campaign_id, npc["id"] if npc else -1, f"%{name}%"),
        ).fetchall()
        decision_rows = source.execute(
            "SELECT * FROM player_decisions WHERE campaign_id = ? AND made_by = ?",
            (campaign_id, name),
        ).fetchall()
        note_rows = source.execute(
            "SELECT * FROM session_notes WHERE campaign_id = ? AND content LIKE ?",
            (campaign_id, f"%{name}%"),
        ).fetchall()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        temp_path = handle.name
    dest = _create_standalone(temp_path)
    try:
        campaign_data = dict(campaign)
        campaign_data["id"] = 1
        _insert_row(dest, "campaigns", campaign_data)
        _insert_row(dest, "party_members", dict(party), campaign_id=1)
        if combatant is not None:
            _insert_row(dest, "combatants", dict(combatant), campaign_id=1)
        if npc is not None:
            # The npc row travels in the file so item ownership survives
            # the round trip. Its id is preserved so the items below can
            # reference it; its location is nulled because the location
            # row is not part of a single-character file.
            _insert_row(
                dest,
                "npcs",
                dict(npc),
                campaign_id=1,
                overrides={"location_id": None},
            )
        npc_id = npc["id"] if npc else -1
        for row in item_rows:
            # An item keeps its holder only when the holder IS this
            # character's npc row (which is in the file now). Any other
            # holder is nulled because that npc is not in the file, and
            # the location is always nulled for the same reason.
            holder_id = (
                row["holder_id"] if row["holder_id"] == npc_id else None
            )
            _insert_row(
                dest,
                "items",
                dict(row),
                campaign_id=1,
                overrides={"holder_id": holder_id, "location_id": None},
            )
        for row in decision_rows:
            _insert_row(dest, "player_decisions", dict(row), campaign_id=1)
        for row in note_rows:
            _insert_row(dest, "session_notes", dict(row), campaign_id=1)
        _set_meta(
            dest,
            {
                "schema_version": SCHEMA_VERSION,
                "exported_from": name,
                "exported_at": datetime.now(UTC).isoformat(),
                "source_campaign_id": str(campaign_id),
            },
        )
        return _read_export_bytes(dest)
    except Exception:
        dest.close()
        Path(temp_path).unlink(missing_ok=True)
        raise


def import_character_db(
    repo: Any, campaign_id: int, source_path: str
) -> dict[str, Any]:
    """Add a hero + party row from a character file; reject name conflicts."""
    campaign, rows = _load_export(source_path)
    party_rows = rows["party_members"]
    if not party_rows:
        raise PortabilityError("character file has no party_members row")
    party = dict(party_rows[0])
    name = str(party.get("name") or "")
    if not name:
        raise PortabilityError("character file has no character name")
    heroes = [
        row for row in rows["combatants"] if str(row.get("kind")) == "hero"
    ]
    hero = dict(heroes[0]) if heroes else None
    npc_rows = rows.get("npcs") or []
    npc = dict(npc_rows[0]) if npc_rows else None
    old_npc_id = npc.get("id") if npc is not None else None

    try:
        with closing(sqlite3.connect(repo.db_path)) as dest:
            dest.row_factory = sqlite3.Row
            dest.execute("PRAGMA foreign_keys = ON")
            conflict = dest.execute(
                "SELECT 1 FROM party_members WHERE campaign_id = ? AND name = ? "
                "UNION SELECT 1 FROM combatants WHERE campaign_id = ? AND name = ?",
                (campaign_id, name, campaign_id, name),
            ).fetchone()
            if conflict is not None:
                raise PortabilityError(
                    f"character {name!r} already exists in campaign {campaign_id}"
                )
            party_id = _insert_row(
                dest,
                "party_members",
                party,
                campaign_id=campaign_id,
                drop=("id", "campaign_id"),
            )
            hero_id = None
            if hero is not None:
                hero_id = _insert_row(
                    dest,
                    "combatants",
                    hero,
                    campaign_id=campaign_id,
                    drop=("id", "campaign_id"),
                )
            npc_id = None
            if npc is not None:
                # The character's npc row anchors item ownership. Reuse
                # the target's npc of the same name when one exists (the
                # character is already known there); otherwise insert
                # the row and let it take a fresh id.
                existing_npc = dest.execute(
                    "SELECT id FROM npcs WHERE campaign_id = ? AND name = ?",
                    (campaign_id, name),
                ).fetchone()
                if existing_npc is not None:
                    npc_id = int(existing_npc["id"])
                else:
                    npc_id = _insert_row(
                        dest,
                        "npcs",
                        npc,
                        campaign_id=campaign_id,
                        drop=("id", "campaign_id"),
                        overrides={"location_id": None},
                    )
            for row in rows["items"]:
                item_name = str(row.get("name") or "")
                existing_item = dest.execute(
                    "SELECT 1 FROM items WHERE campaign_id = ? AND name = ?",
                    (campaign_id, item_name),
                ).fetchone()
                if existing_item is not None:
                    continue
                # Remap the holder from the file's npc id to the target's.
                # A holder that is not the character's npc cannot be
                # resolved (that npc is not in the file), so it is nulled.
                holder_id = (
                    npc_id
                    if old_npc_id is not None
                    and row.get("holder_id") == old_npc_id
                    else None
                )
                _insert_row(
                    dest,
                    "items",
                    row,
                    campaign_id=campaign_id,
                    drop=("id", "campaign_id"),
                    overrides={"holder_id": holder_id, "location_id": None},
                )
            for row in rows["player_decisions"]:
                _insert_row(
                    dest,
                    "player_decisions",
                    row,
                    campaign_id=campaign_id,
                    drop=("id", "campaign_id"),
                )
            for row in rows["session_notes"]:
                _insert_row(
                    dest,
                    "session_notes",
                    row,
                    campaign_id=campaign_id,
                    drop=("id", "campaign_id"),
                )
            violations = dest.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise PortabilityError(
                    "character import has foreign key violations"
                )
            dest.commit()
    except sqlite3.IntegrityError as exc:
        raise PortabilityError(f"could not import character: {exc}") from exc

    return {
        "campaign_id": campaign_id,
        "name": name,
        "party_member_id": party_id,
        "combatant_id": hero_id,
        "npc_id": npc_id,
        "source_campaign": campaign.get("name"),
    }
