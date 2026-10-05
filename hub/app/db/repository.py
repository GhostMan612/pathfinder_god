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
from dataclasses import dataclass, fields
from pathlib import Path

from app.config import settings


@dataclass
class Campaign:
    id: int
    name: str
    edition: str
    created_at: str
    updated_at: str
    summary: str | None = None


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
        # SQLite ignores ON DELETE CASCADE unless foreign keys are enabled per
        # connection. Without this, reset_campaign() deleted the campaigns row
        # and left every child row orphaned.
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _ensure_campaign(conn, campaign_id: int) -> None:
        """Make sure the parent campaign row exists.

        Foreign keys are enforced (see _conn). Every child table declares
        REFERENCES campaigns(id), but the ContinuityKeeper and agent tools
        write children against a hard-coded campaign id without ever creating
        the parent. That only went unnoticed because foreign-key enforcement was
        off, which is also why ON DELETE CASCADE was inert.
        """
        conn.execute(
            """
            INSERT INTO campaigns (id, name, created_at, updated_at)
            VALUES (?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(id) DO NOTHING
            """,
            (campaign_id, f"Campaign {campaign_id}"),
        )

    def _init_db(self) -> None:
        """Run schema.sql to create tables."""
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            with self._conn() as conn:
                conn.executescript(schema_path.read_text(encoding="utf-8"))
                # Older campaign.db files predate the evergreen campaign summary
                # column; ALTER idempotently so reused DBs gain it in place.
                try:
                    conn.execute("ALTER TABLE campaigns ADD COLUMN summary TEXT")
                except sqlite3.OperationalError:
                    pass
                # Index any already-saved sessions into the recall FTS table so
                # long campaigns are searchable from the very first run after
                # the schema upgrade. For content= external tables this is safe
                # to re-run -- 'rebuild' drops and rebuilds the index.
                try:
                    conn.execute("INSERT INTO sessions_fts(sessions_fts) VALUES('rebuild')")
                except sqlite3.OperationalError:
                    pass

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
            values = dict(row)
            # pop unconditionally: leaving it inside the conditional meant a
            # NULL facts_json skipped the pop and leaked into Session(**values)
            # as an unexpected keyword argument.
            raw_facts = values.pop("facts_json", None)
            values["facts"] = json.loads(raw_facts) if raw_facts else []
            return Session(**values)

    def get_session(self, campaign_id: int, session_num: int) -> Session | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE campaign_id = ? AND session_num = ?",
                (campaign_id, session_num),
            ).fetchone()
            if not row:
                return None
            values = dict(row)
            raw_facts = values.pop("facts_json", None)
            values["facts"] = json.loads(raw_facts) if raw_facts else []
            return Session(**values)

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
            self._ensure_campaign(conn, campaign_id)
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
        """Append a note to the session's raw log, creating the row if needed.

        This used to be a bare UPDATE, so on a campaign with no sessions yet it
        matched zero rows. The caller ignored rowcount and returned 200, and the
        only thing that ever created the row was ContinuityKeeper, three LLM
        calls later - so with Ollama down the note was lost for good.
        """
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            conn.execute(
                """
                INSERT INTO sessions (campaign_id, session_num, raw_log)
                VALUES (?, ?, ?)
                ON CONFLICT(campaign_id, session_num) DO UPDATE SET
                    raw_log = COALESCE(sessions.raw_log, '')
                               || '\n\nUSER: ' || ? || '\nGM: ' || ?
                """,
                (
                    campaign_id,
                    session_num,
                    f"USER: {prompt}\nGM: {response}",
                    prompt,
                    response,
                ),
            )

    def get_campaign_summary(self, campaign_id: int = 1) -> str:
        """Return the evergreen campaign chronicle, or '' if none yet."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT summary FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            return row[0] if row and row[0] else ""

    def update_campaign_summary(self, campaign_id: int, summary: str) -> None:
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            conn.execute(
                "UPDATE campaigns SET summary = ? WHERE id = ?",
                (summary, campaign_id),
            )

    def get_active_campaign_id(self) -> int:
        """Return the most recently touched campaign (fallback: 1).

        The continuity agent tools receive an explicit campaign_id from the
        player's app, but the live GM's injected campaign block does not - so
        it reasons about the campaign that has seen the most recent save/summary
        rather than blindly reading id=1.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM campaigns ORDER BY updated_at DESC, id DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else 1

    def search_sessions(self, query: str, campaign_id: int = 1, limit: int = 5) -> list[dict]:
        """Full-text search across saved session summaries/facts/logs.

        This is the long-campaign recall primitive: instead of dumping every
        historical turn into the LLM prompt, the GM retrieves the few sessions
        that match its current question. The FTS5 table mirrors `sessions` and
        is kept in sync by triggers declared in schema.sql.
        """
        if not query or not query.strip():
            return []
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT s.campaign_id, s.session_num, s.summary, s.facts_json,
                       substr(s.raw_log, 1, 1200) AS excerpt
                FROM sessions s
                JOIN sessions_fts ON sessions_fts.rowid = s.id
                WHERE sessions_fts MATCH ? AND s.campaign_id = ?
                ORDER BY bm25(sessions_fts)
                LIMIT ?
                """,
                (query, campaign_id, limit),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["facts_json"] = json.loads(d.get("facts_json") or "[]")
                except Exception:
                    d["facts_json"] = []
                out.append(d)
            return out

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

            self._ensure_campaign(conn, campaign_id)

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

    @staticmethod
    def _npc_from_row(row: dict) -> NPC:
        known = {f.name for f in fields(NPC)}
        values = dict(row)
        values["class_"] = values.pop("class", None)
        return NPC(**{k: v for k, v in values.items() if k in known})

    def get_npcs(self, campaign_id: int) -> list[NPC]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM npcs WHERE campaign_id = ? ORDER BY name",
                (campaign_id,),
            ).fetchall()
            return [self._npc_from_row(dict(r)) for r in rows]

    def get_npc(self, campaign_id: int, name: str) -> NPC | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM npcs WHERE campaign_id = ? AND name = ?",
                (campaign_id, name),
            ).fetchone()
            return self._npc_from_row(dict(row)) if row else None

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
            self._ensure_campaign(conn, campaign_id)
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
            # SELECT * returns the *_json columns too, which the dataclass does
            # not accept. Decode them into their real fields and drop the rest.
            out = []
            for r in rows:
                values = dict(r)
                values["facts"] = json.loads(values.pop("facts_json") or "[]")
                values.pop("created_at", None)
                values.pop("updated_at", None)
                out.append(Location(**values))
            return out

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
            self._ensure_campaign(conn, campaign_id)
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
            self._ensure_campaign(conn, campaign_id)
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
            out = []
            for r in rows:
                values = dict(r)
                values["objectives"] = json.loads(values.pop("objectives_json") or "[]")
                values["rewards"] = json.loads(values.pop("rewards_json") or "[]")
                values.pop("created_at", None)
                values.pop("updated_at", None)
                out.append(Quest(**values))
            return out

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
            self._ensure_campaign(conn, campaign_id)
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
            self._ensure_campaign(conn, campaign_id)
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


def get_repo(db_path: str | None = None) -> CampaignRepository:
    """Factory for a CampaignRepository.

    NOT a FastAPI dependency - use app.api.deps.get_repo for that. This takes a
    single scalar argument, so FastAPI would otherwise treat it as a query
    parameter and let a caller pass any writable path to create a database in.
    """
    if db_path is None:
        from app.config import settings
        db_path = str(settings.data_dir / "campaign.db")
    return CampaignRepository(str(db_path))