# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Campaign Repository — SQLite CRUD + queries for Campaign & Continuity data.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.config import settings


@dataclass
class Campaign:
    id: int
    name: str
    edition: str
    created_at: str
    updated_at: str


@dataclass
class Session:
    id: int
    campaign_id: int
    session_num: int
    started_at: str
    ended_at: str | None
    summary: str | None
    facts: list[dict]
    raw_log: str | None


@dataclass
class NPC:
    id: int
    campaign_id: int
    name: str
    alias: str | None
    role: str
    level: int | None
    ancestry: str | None
    class_: str | None
    location_id: int | None
    disposition: str
    notes: str | None
    first_seen_session: int | None
    last_seen_session: int | None


@dataclass
class Location:
    id: int
    campaign_id: int
    name: str
    type: str
    parent_id: int | None
    description: str | None
    facts: list[dict]


@dataclass
class Item:
    id: int
    campaign_id: int
    name: str
    type: str
    level: int | None
    traits: list[str]
    holder_id: int | None
    location_id: int | None
    notes: str | None


@dataclass
class Quest:
    id: int
    campaign_id: int
    name: str
    status: str
    giver_id: int | None
    description: str | None
    objectives: list[dict]
    rewards: list[dict]
    started_session: int | None
    completed_session: int | None


@dataclass
class Decision:
    id: int
    campaign_id: int
    session_num: int
    decision: str
    context: str | None
    consequences: list[str]
    made_by: str | None


class CampaignRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(settings.data_dir / "campaign.db")
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Run schema.sql to create tables."""
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            with self._conn() as conn:
                conn.executescript(schema_path.read_text())

    # ──────────────────────────────────────────────────────────────
    # Campaigns
    # ──────────────────────────────────────────────────────────────

    def get_or_create_campaign(self, campaign_id: int = 1, name: str | None = None) -> Campaign:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
            if row:
                return Campaign(**dict(row))
            name = name or f"Campaign {campaign_id}"
            cur = conn.execute(
                "INSERT INTO campaigns (id, name) VALUES (?, ?) RETURNING *",
                (campaign_id, name),
            )
            row = cur.fetchone()
            return Campaign(**dict(row))

    def reset_campaign(self, campaign_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
            # Cascade deletes handle related tables

    # ──────────────────────────────────────────────────────────────
    # Sessions
    # ──────────────────────────────────────────────────────────────

    def get_latest_session(self, campaign_id: int) -> Session | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE campaign_id = ? ORDER BY session_num DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if not row:
                return None
            return Session(
                **dict(row),
                facts=json.loads(row["facts_json"]) if row["facts_json"] else [],
            )

    def get_session(self, campaign_id: int, session_num: int) -> Session | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE campaign_id = ? AND session_num = ?",
                (campaign_id, session_num),
            ).fetchone()
            if not row:
                return None
            return Session(
                **dict(row),
                facts=json.loads(row["facts_json"]) if row["facts_json"] else [],
            )

    def get_latest_session_num(self, campaign_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(session_num), 0) FROM sessions WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            return row[0] if row else 0

    def save_session(
        self,
        campaign_id: int,
        session_num: int,
        summary: str,
        facts: list[dict],
        raw_log: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions (campaign_id, session_num, summary, facts_json, raw_log)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, session_num) DO UPDATE SET
                    summary = excluded.summary,
                    facts_json = excluded.facts_json,
                    raw_log = excluded.raw_log,
                    ended_at = datetime('now')
                """,
                (
                    campaign_id,
                    session_num,
                    summary,
                    json.dumps(facts),
                    raw_log,
                ),
            )

    def add_session_note(self, campaign_id: int, session_num: int, prompt: str, response: str) -> None:
        """Append a note to the session's raw log."""
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET raw_log = COALESCE(raw_log, '') || '\n\nUSER: ' || ? || '\nGM: ' || ?
                WHERE campaign_id = ? AND session_num = ?
                """,
                (prompt, response, campaign_id, session_num),
            )

    # ──────────────────────────────────────────────────────────────
    # NPCs
    # ──────────────────────────────────────────────────────────────

    def upsert_npc(
        self,
        campaign_id: int,
        name: str,
        alias: str | None = None,
        role: str = "unknown",
        level: int | None = None,
        ancestry: str | None = None,
        class_: str | None = None,
        disposition: str = "unknown",
        notes: str | None = None,
        session_num: int | None = None,
    ) -> int:
        with self._conn() as conn:
            # Get location_id if parent_name provided
            location_id = None
            # (caller can pass location_id directly if needed)

            cur = conn.execute(
                """
                INSERT INTO npcs (campaign_id, name, alias, role, level, ancestry, class,
                                 disposition, notes, first_seen_session, last_seen_session)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, name) DO UPDATE SET
                    alias = excluded.alias,
                    role = excluded.role,
                    level = excluded.level,
                    ancestry = excluded.ancestry,
                    class = excluded.class,
                    disposition = excluded.disposition,
                    notes = excluded.notes,
                    last_seen_session = excluded.last_seen_session,
                    updated_at = datetime('now')
                RETURNING id
                """,
                (
                    campaign_id,
                    name,
                    alias,
                    role,
                    level,
                    ancestry,
                    class_,
                    disposition,
                    notes,
                    session_num,
                    session_num,
                ),
            )
            return cur.fetchone()[0]

    def get_npcs(self, campaign_id: int) -> list[NPC]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM npcs WHERE campaign_id = ? ORDER BY name",
                (campaign_id,),
            ).fetchall()
            return [NPC(**dict(r)) for r in rows]

    def get_npc(self, campaign_id: int, name: str) -> NPC | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM npcs WHERE campaign_id = ? AND name = ?",
                (campaign_id, name),
            ).fetchone()
            return NPC(**dict(row)) if row else None

    # ──────────────────────────────────────────────────────────────
    # Locations
    # ──────────────────────────────────────────────────────────────

    def upsert_location(
        self,
        campaign_id: int,
        name: str,
        type_: str = "other",
        parent_name: str | None = None,
        description: str | None = None,
        session_num: int | None = None,
    ) -> int:
        with self._conn() as conn:
            parent_id = None
            if parent_name:
                prow = conn.execute(
                    "SELECT id FROM locations WHERE campaign_id = ? AND name = ?",
                    (campaign_id, parent_name),
                ).fetchone()
                parent_id = prow[0] if prow else None

            facts_json = json.dumps({})
            cur = conn.execute(
                """
                INSERT INTO locations (campaign_id, name, type, parent_id, description, facts_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, name) DO UPDATE SET
                    type = excluded.type,
                    parent_id = excluded.parent_id,
                    description = excluded.description,
                    updated_at = datetime('now')
                RETURNING id
                """,
                (campaign_id, name, type_, parent_id, description, facts_json),
            )
            return cur.fetchone()[0]

    def get_locations(self, campaign_id: int) -> list[Location]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM locations WHERE campaign_id = ? ORDER BY name",
                (campaign_id,),
            ).fetchall()
            return [Location(**dict(r), facts=json.loads(r["facts_json"] or "[]")) for r in rows]

    # ──────────────────────────────────────────────────────────────
    # Items
    # ──────────────────────────────────────────────────────────────

    def upsert_item(
        self,
        campaign_id: int,
        name: str,
        type_: str = "other",
        level: int | None = None,
        traits: list[str] | None = None,
        holder_name: str | None = None,
        location_name: str | None = None,
        notes: str | None = None,
        session_num: int | None = None,
    ) -> int:
        with self._conn() as conn:
            holder_id = None
            if holder_name:
                row = conn.execute(
                    "SELECT id FROM npcs WHERE campaign_id = ? AND name = ?",
                    (campaign_id, holder_name),
                ).fetchone()
                holder_id = row[0] if row else None

            location_id = None
            if location_name:
                row = conn.execute(
                    "SELECT id FROM locations WHERE campaign_id = ? AND name = ?",
                    (campaign_id, location_name),
                ).fetchone()
                location_id = row[0] if row else None

            cur = conn.execute(
                """
                INSERT INTO items (campaign_id, name, type, level, traits_json, holder_id, location_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, name) DO UPDATE SET
                    type = excluded.type,
                    level = excluded.level,
                    traits_json = excluded.traits_json,
                    holder_id = excluded.holder_id,
                    location_id = excluded.location_id,
                    notes = excluded.notes,
                    updated_at = datetime('now')
                RETURNING id
                """,
                (
                    campaign_id,
                    name,
                    type_,
                    level,
                    json.dumps(traits or []),
                    holder_id,
                    location_id,
                    notes,
                ),
            )
            return cur.fetchone()[0]

    # ──────────────────────────────────────────────────────────────
    # Quests
    # ──────────────────────────────────────────────────────────────

    def upsert_quest(
        self,
        campaign_id: int,
        name: str,
        status: str = "active",
        giver_name: str | None = None,
        description: str | None = None,
        objectives: list[dict] | None = None,
        rewards: list[dict] | None = None,
        session_num: int | None = None,
    ) -> int:
        with self._conn() as conn:
            giver_id = None
            if giver_name:
                row = conn.execute(
                    "SELECT id FROM npcs WHERE campaign_id = ? AND name = ?",
                    (campaign_id, giver_name),
                ).fetchone()
                giver_id = row[0] if row else None

            cur = conn.execute(
                """
                INSERT INTO quests (campaign_id, name, status, giver_id, description,
                                   objectives_json, rewards_json, started_session)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, name) DO UPDATE SET
                    status = excluded.status,
                    giver_id = excluded.giver_id,
                    description = excluded.description,
                    objectives_json = excluded.objectives_json,
                    rewards_json = excluded.rewards_json,
                    updated_at = datetime('now')
                RETURNING id
                """,
                (
                    campaign_id,
                    name,
                    status,
                    giver_id,
                    description,
                    json.dumps(objectives or []),
                    json.dumps(rewards or []),
                    session_num,
                ),
            )
            return cur.fetchone()[0]

    def get_active_quests(self, campaign_id: int) -> list[Quest]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quests WHERE campaign_id = ? AND status = 'active' ORDER BY name",
                (campaign_id,),
            ).fetchall()
            return [
                Quest(
                    **dict(r),
                    objectives=json.loads(r["objectives_json"] or "[]"),
                    rewards=json.loads(r["rewards_json"] or "[]"),
                )
                for r in rows
            ]

    # ──────────────────────────────────────────────────────────────
    # Decisions
    # ──────────────────────────────────────────────────────────────

    def add_decision(
        self,
        campaign_id: int,
        session_num: int,
        decision: str,
        context: str | None = None,
        consequences: list[str] | None = None,
        made_by: str | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO player_decisions (campaign_id, session_num, decision, context, consequences_json, made_by)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    campaign_id,
                    session_num,
                    decision,
                    context,
                    json.dumps(consequences or []),
                    made_by,
                ),
            )
            return cur.fetchone()[0]

    # ──────────────────────────────────────────────────────────────
    # Party Members
    # ──────────────────────────────────────────────────────────────

    def upsert_party_member(
        self,
        campaign_id: int,
        name: str,
        player_name: str | None = None,
        class_: str | None = None,
        level: int = 1,
        ancestry: str | None = None,
        background: str | None = None,
        stats: dict | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO party_members (campaign_id, name, player_name, class, level, ancestry, background, stats_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, name) DO UPDATE SET
                    player_name = excluded.player_name,
                    class = excluded.class,
                    level = excluded.level,
                    ancestry = excluded.ancestry,
                    background = excluded.background,
                    stats_json = excluded.stats_json,
                    updated_at = datetime('now')
                RETURNING id
                """,
                (
                    campaign_id,
                    name,
                    player_name,
                    class_,
                    level,
                    ancestry,
                    background,
                    json.dumps(stats or {}),
                ),
            )
            return cur.fetchone()[0]

    def get_party(self, campaign_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM party_members WHERE campaign_id = ? ORDER BY name",
                (campaign_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ──────────────────────────────────────────────────────────────
    # Campaign State (for /campaign GET)
    # ──────────────────────────────────────────────────────────────

    def get_campaign_state(self, campaign_id: int = 1) -> dict:
        """Get full campaign state for API response."""
        party = self.get_party(campaign_id)
        notes = self.get_session_notes(campaign_id)
        return {"party": party, "notes": notes}

    def get_session_notes(self, campaign_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT session_num, summary, facts_json FROM sessions WHERE campaign_id = ? ORDER BY session_num",
                (campaign_id,),
            ).fetchall()
            return [
                {
                    "session_num": r["session_num"],
                    "summary": r["summary"],
                    "facts": json.loads(r["facts_json"] or "[]"),
                }
                for r in rows
            ]


def get_repo(data_dir: Optional[str] = None) -> CampaignRepository:
    """Factory function to create a CampaignRepository instance."""
    if data_dir is None:
        from app.config import settings
        data_dir = str(settings.data_dir)
    return CampaignRepository(data_dir)