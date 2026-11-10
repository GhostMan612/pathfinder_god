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
from app.rag._fts import build_match_query

# Ceiling on sessions.raw_log, applied in SQL on every turn append. Without it
# the transcript grows without bound, SQLite rewrites the whole TEXT value on
# every append (so write cost is O(n^2) over a session), the auto-fold hands the
# entire log to the LLM, and an unbounded string reaches the system prompt.
# Only the most recent window is kept; durable history lives in the summaries
# and the entity ledger, not in this debugging aid.
_RAW_LOG_MAX_CHARS = 100_000


@dataclass
class Campaign:
    id: int
    name: str
    edition: str
    created_at: str
    updated_at: str
    summary: str | None = None
    combat_json: str | None = None


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


@dataclass
class Combatant:
    id: int
    campaign_id: int
    name: str
    kind: str
    hp: int
    max_hp: int
    temp_hp: int = 0
    ac: int = 10
    initiative: int = 0
    conditions: list[dict] | None = None
    is_active: bool = True
    turn_order: int = 0


@dataclass
class SoloState:
    campaign_id: int
    phase: str = "exploration"
    round_num: int = 1
    current_location_id: int | None = None
    active_combatant_id: int | None = None
    turn_order: list[int] | None = None


@dataclass
class CampaignTurn:
    id: int
    campaign_id: int
    turn_num: int
    actor: str
    action: str
    narration: str
    outcome: dict
    dice: list[dict]


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
                try:
                    conn.execute("ALTER TABLE campaigns ADD COLUMN combat_json TEXT")
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

    def create_campaign(self, name: str, edition: str = "2e") -> Campaign:
        """Create a brand-new campaign row with an auto-assigned id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO campaigns (name, edition) VALUES (?, ?) RETURNING *",
                (name, edition),
            )
            return Campaign(**dict(cur.fetchone()))

    def campaign_exists(self, campaign_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            return row is not None

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
                    raw_log = SUBSTR(
                        COALESCE(sessions.raw_log, '')
                        || char(10) || char(10) || 'USER: ' || ?
                        || char(10) || 'GM: ' || ?,
                        -?
                    )
                """,
                (
                    campaign_id,
                    session_num,
                    f"USER: {prompt}\nGM: {response}",
                    prompt,
                    response,
                    _RAW_LOG_MAX_CHARS,
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

    def get_combat_json(self, campaign_id: int = 1) -> str:
        """Return the live combat scene JSON, or '' if none set."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT combat_json FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            return row[0] if row and row[0] else ""

    def set_combat_json(self, campaign_id: int, scene_json: str) -> None:
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            conn.execute(
                "UPDATE campaigns SET combat_json = ? WHERE id = ?",
                (scene_json, campaign_id),
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

        The query is sanitised with build_match_query before it reaches MATCH.
        It used to be interpolated raw, so an unbalanced quote, a bare
        AND/OR/NOT, or a stray operator in the GM's own search phrasing raised
        sqlite3.OperationalError, which propagated out of the tool handler.
        """
        if not query or not query.strip():
            return []
        match = build_match_query(query)
        if not match:
            return []
        try:
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
                    (match, campaign_id, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            # Defence in depth: build_match_query should make this unreachable,
            # but a MATCH failure must never escape into the GM's tool handler.
            return []
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

    def get_npc_by_id(self, campaign_id: int, npc_id: int) -> NPC | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM npcs WHERE campaign_id = ? AND id = ?",
                (campaign_id, npc_id),
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

    # ──────────────────────────────────────────────────────────────
    # Hot-path single-connection snapshot (O1)
    # ──────────────────────────────────────────────────────────────

    def get_campaign_snapshot(
        self,
        campaign_id: int | None = None,
        *,
        party_limit: int = 12,
        npc_limit: int = 12,
        location_limit: int = 12,
        item_limit: int = 12,
        quest_limit: int = 8,
    ) -> dict:
        """Assemble the GM's campaign context over a SINGLE connection.

        The live GM's injected context block used to call get_active_campaign_id,
        get_campaign_context, get_combat_json and several list getters in a row,
        and every one of those opened its own sqlite connection (connect, PRAGMA,
        commit, close). That was 7-8 connection cycles on the hot path of every
        /ask and /stream turn.

        This does the same reads in one pass with LIMIT pushed into SQL, so a
        long campaign does not materialise every NPC/quest row just to show the
        GM the first handful. The individual getters are untouched and still
        used elsewhere.
        """
        with self._conn() as conn:
            if campaign_id is None:
                row = conn.execute(
                    "SELECT id FROM campaigns ORDER BY updated_at DESC, id DESC LIMIT 1"
                ).fetchone()
                cid = row[0] if row else 1
            else:
                cid = campaign_id

            campaign = conn.execute(
                "SELECT id, name, summary, combat_json FROM campaigns WHERE id = ?",
                (cid,),
            ).fetchone()

            party = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM party_members WHERE campaign_id = ?"
                    " ORDER BY name LIMIT ?",
                    (cid, party_limit),
                ).fetchall()
            ]

            npcs = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM npcs WHERE campaign_id = ? ORDER BY name LIMIT ?",
                    (cid, npc_limit),
                ).fetchall()
            ]

            locations = []
            for r in conn.execute(
                "SELECT * FROM locations WHERE campaign_id = ? ORDER BY name LIMIT ?",
                (cid, location_limit),
            ).fetchall():
                values = dict(r)
                try:
                    values["facts"] = json.loads(values.pop("facts_json") or "[]")
                except Exception:
                    values["facts"] = []
                locations.append(values)

            items = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM items WHERE campaign_id = ? ORDER BY name LIMIT ?",
                    (cid, item_limit),
                ).fetchall()
            ]

            quests = []
            for r in conn.execute(
                "SELECT * FROM quests WHERE campaign_id = ? AND status = 'active'"
                " ORDER BY name LIMIT ?",
                (cid, quest_limit),
            ).fetchall():
                values = dict(r)
                try:
                    values["objectives"] = json.loads(values.pop("objectives_json") or "[]")
                    values["rewards"] = json.loads(values.pop("rewards_json") or "[]")
                except Exception:
                    values.setdefault("objectives", [])
                    values.setdefault("rewards", [])
                quests.append(values)

        return {
            "campaign_id": cid,
            "name": (campaign["name"] if campaign else "") or "",
            "chronicle": (campaign["summary"] if campaign and campaign["summary"] else "") or "",
            "combat_json": (
                campaign["combat_json"] if campaign and campaign["combat_json"] else ""
            )
            or "",
            "party": party,
            "npcs": npcs,
            "locations": locations,
            "items": items,
            "quests": quests,
        }

    # ──────────────────────────────────────────────────────────────
    # Batch writers (O2): one connection for many rows
    # ──────────────────────────────────────────────────────────────

    def insert_session_notes(self, campaign_id: int, notes: list[tuple]) -> int:
        """Bulk-insert session notes in a single transaction.

        `notes` is a list of (session_num, note_type, content) tuples, already
        int/str-validated by the caller. This replaces a loop that opened one
        sqlite connection per row, so restoring a 500-note campaign went from
        500 connect/commit/close cycles to 1.
        """
        if not notes:
            return 0
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            conn.executemany(
                "INSERT INTO session_notes (campaign_id, session_num, note_type, content)"
                " VALUES (?, ?, ?, ?)",
                [(campaign_id, sn, nt, content) for sn, nt, content in notes],
            )
        return len(notes)

    def upsert_party_batch(self, campaign_id: int, members: list[dict]) -> int:
        """Upsert party members over ONE connection.

        `members` is a list of dicts with the same keys upsert_party_member
        accepts. That method returns `RETURNING id`, which executemany cannot
        surface, so this keeps the per-row statement and only shares the
        connection - the conflict semantics are byte-identical.
        """
        if not members:
            return 0
        written = 0
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            for member in members:
                name = str(member.get("name") or "").strip()
                if not name:
                    continue
                conn.execute(
                    """
                    INSERT INTO party_members (campaign_id, name, player_name, class,
                                               level, ancestry, background, stats_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, name) DO UPDATE SET
                        player_name = excluded.player_name,
                        class = excluded.class,
                        level = excluded.level,
                        ancestry = excluded.ancestry,
                        background = excluded.background,
                        stats_json = excluded.stats_json,
                        updated_at = datetime('now')
                    """,
                    (
                        campaign_id,
                        name,
                        member.get("player_name"),
                        member.get("class_"),
                        member.get("level", 1),
                        member.get("ancestry"),
                        member.get("background"),
                        json.dumps(member["stats"]) if member.get("stats") else None,
                    ),
                )
                written += 1
        return written

    def insert_sessions_batch(self, campaign_id: int, sessions: list[dict]) -> int:
        """Upsert sessions over ONE connection, keeping the FTS index in sync.

        `sessions` is a list of dicts with keys session_num, summary, facts,
        raw_log. The statement is the same INSERT...ON CONFLICT DO UPDATE as
        save_session, so the schema's sessions_fts AFTER INSERT and AFTER UPDATE
        triggers fire exactly as before - that is what keeps imported sessions
        immediately searchable through search_sessions.
        """
        if not sessions:
            return 0
        written = 0
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            for session in sessions:
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
                        session["session_num"],
                        session.get("summary", ""),
                        json.dumps(session.get("facts") or []),
                        session.get("raw_log", ""),
                    ),
                )
                written += 1
        return written

    def upsert_entities_batch(
        self,
        campaign_id: int,
        npcs: list[dict] | None = None,
        locations: list[dict] | None = None,
        items: list[dict] | None = None,
        quests: list[dict] | None = None,
    ) -> dict[str, int]:
        """Upsert a whole extracted entity set over ONE connection.

        Each entity type is written with its own INSERT...ON CONFLICT
        statement, but the whole batch shares a single connection and a single
        commit. Ordering matters and is preserved: locations before items so a
        item can resolve location_name, and npcs before both so an item can
        resolve holder_name. That is why this is not executemany - each row's
        SQL depends on rows written earlier in the same batch.
        """
        counts = {"npcs": 0, "locations": 0, "items": 0, "quests": 0}
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)

            for loc in locations or []:
                name = str(loc.get("name") or "").strip()
                if not name:
                    continue
                parent_id = None
                parent_name = loc.get("parent_name")
                if parent_name:
                    prow = conn.execute(
                        "SELECT id FROM locations WHERE campaign_id = ? AND name = ?",
                        (campaign_id, parent_name),
                    ).fetchone()
                    parent_id = prow[0] if prow else None
                conn.execute(
                    """
                    INSERT INTO locations (campaign_id, name, type, parent_id, description, facts_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, name) DO UPDATE SET
                        type = excluded.type,
                        parent_id = excluded.parent_id,
                        description = excluded.description,
                        updated_at = datetime('now')
                    """,
                    (
                        campaign_id,
                        name,
                        loc.get("type") or "other",
                        parent_id,
                        loc.get("description"),
                        json.dumps({}),
                    ),
                )
                counts["locations"] += 1

            for npc in npcs or []:
                name = str(npc.get("name") or "").strip()
                if not name:
                    continue
                conn.execute(
                    """
                    INSERT INTO npcs (campaign_id, name, alias, role, level, ancestry, class,
                                      disposition, notes, first_seen_session, last_seen_session)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, name) DO UPDATE SET
                        alias = excluded.alias, role = excluded.role,
                        level = excluded.level, ancestry = excluded.ancestry,
                        class = excluded.class, disposition = excluded.disposition,
                        notes = excluded.notes,
                        last_seen_session = excluded.last_seen_session,
                        updated_at = datetime('now')
                    """,
                    (
                        campaign_id,
                        name,
                        npc.get("alias"),
                        npc.get("role") or "unknown",
                        npc.get("level"),
                        npc.get("ancestry"),
                        npc.get("class_") or npc.get("class"),
                        npc.get("disposition") or "unknown",
                        npc.get("notes"),
                        npc.get("session_num"),
                        npc.get("session_num"),
                    ),
                )
                counts["npcs"] += 1

            for item in items or []:
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                holder_id = None
                if item.get("holder_name"):
                    row = conn.execute(
                        "SELECT id FROM npcs WHERE campaign_id = ? AND name = ?",
                        (campaign_id, item["holder_name"]),
                    ).fetchone()
                    holder_id = row[0] if row else None
                location_id = None
                if item.get("location_name"):
                    row = conn.execute(
                        "SELECT id FROM locations WHERE campaign_id = ? AND name = ?",
                        (campaign_id, item["location_name"]),
                    ).fetchone()
                    location_id = row[0] if row else None
                conn.execute(
                    """
                    INSERT INTO items (campaign_id, name, type, level, traits_json,
                                       holder_id, location_id, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, name) DO UPDATE SET
                        type = excluded.type, level = excluded.level,
                        traits_json = excluded.traits_json,
                        holder_id = excluded.holder_id,
                        location_id = excluded.location_id,
                        notes = excluded.notes,
                        updated_at = datetime('now')
                    """,
                    (
                        campaign_id,
                        name,
                        item.get("type") or "other",
                        item.get("level"),
                        json.dumps(item.get("traits") or []),
                        holder_id,
                        location_id,
                        item.get("notes"),
                    ),
                )
                counts["items"] += 1

            for quest in quests or []:
                name = str(quest.get("name") or "").strip()
                if not name:
                    continue
                giver_id = None
                if quest.get("giver_name"):
                    row = conn.execute(
                        "SELECT id FROM npcs WHERE campaign_id = ? AND name = ?",
                        (campaign_id, quest["giver_name"]),
                    ).fetchone()
                    giver_id = row[0] if row else None
                conn.execute(
                    """
                    INSERT INTO quests (campaign_id, name, status, giver_id, description,
                                        objectives_json, rewards_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, name) DO UPDATE SET
                        status = excluded.status, giver_id = excluded.giver_id,
                        description = excluded.description,
                        objectives_json = excluded.objectives_json,
                        rewards_json = excluded.rewards_json,
                        updated_at = datetime('now')
                    """,
                    (
                        campaign_id,
                        name,
                        quest.get("status") or "active",
                        giver_id,
                        quest.get("description"),
                        json.dumps(quest.get("objectives") or []),
                        json.dumps(quest.get("rewards") or []),
                    ),
                )
                counts["quests"] += 1

        return counts

    # ──────────────────────────────────────────────────────────────
    # Solo campaign loop (server-owned play state)
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _combatant_from_row(row: dict) -> Combatant:
        values = dict(row)
        values["conditions"] = json.loads(values.pop("conditions_json") or "[]")
        values["is_active"] = bool(values.get("is_active", 1))
        values.pop("created_at", None)
        values.pop("updated_at", None)
        return Combatant(**values)

    def ensure_solo_state(self, campaign_id: int) -> SoloState:
        """Create the solo_state row if missing, else return the existing one."""
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            conn.execute(
                """
                INSERT INTO solo_state (campaign_id)
                VALUES (?)
                ON CONFLICT(campaign_id) DO NOTHING
                """,
                (campaign_id,),
            )
            row = conn.execute(
                "SELECT * FROM solo_state WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
            values = dict(row)
            values["turn_order"] = json.loads(values.pop("turn_order_json") or "[]")
            values.pop("created_at", None)
            values.pop("updated_at", None)
            return SoloState(**values)

    def get_solo_state(self, campaign_id: int) -> SoloState | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM solo_state WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
            if not row:
                return None
            values = dict(row)
            values["turn_order"] = json.loads(values.pop("turn_order_json") or "[]")
            values.pop("created_at", None)
            values.pop("updated_at", None)
            return SoloState(**values)

    def update_solo_state(
        self,
        campaign_id: int,
        *,
        phase: str | None = None,
        round_num: int | None = None,
        current_location_id: int | None = None,
        active_combatant_id: int | None = None,
        turn_order: list[int] | None = None,
        clear_active: bool = False,
    ) -> SoloState:
        """Patch solo_state fields; only the given fields change."""
        state = self.ensure_solo_state(campaign_id)
        new_phase = phase if phase is not None else state.phase
        new_round = round_num if round_num is not None else state.round_num
        new_location = (
            current_location_id
            if current_location_id is not None
            else state.current_location_id
        )
        new_active = (
            None
            if clear_active
            else (
                active_combatant_id
                if active_combatant_id is not None
                else state.active_combatant_id
            )
        )
        new_order = turn_order if turn_order is not None else (state.turn_order or [])
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE solo_state SET phase = ?, round_num = ?,
                    current_location_id = ?, active_combatant_id = ?,
                    turn_order_json = ?
                WHERE campaign_id = ?
                """,
                (
                    new_phase,
                    new_round,
                    new_location,
                    new_active,
                    json.dumps(new_order),
                    campaign_id,
                ),
            )
        return SoloState(
            campaign_id=campaign_id,
            phase=new_phase,
            round_num=new_round,
            current_location_id=new_location,
            active_combatant_id=new_active,
            turn_order=new_order,
        )

    def set_current_location(self, campaign_id: int, location_id: int) -> SoloState:
        return self.update_solo_state(campaign_id, current_location_id=location_id)

    def upsert_combatant(
        self,
        campaign_id: int,
        name: str,
        kind: str = "monster",
        hp: int = 1,
        max_hp: int = 1,
        temp_hp: int = 0,
        ac: int = 10,
        initiative: int = 0,
        conditions: list[dict] | None = None,
        turn_order: int = 0,
        is_active: bool = True,
    ) -> int:
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            cur = conn.execute(
                """
                INSERT INTO combatants (campaign_id, name, kind, hp, max_hp, temp_hp,
                                       ac, initiative, conditions_json, is_active, turn_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id, name) DO UPDATE SET
                    kind = excluded.kind, hp = excluded.hp, max_hp = excluded.max_hp,
                    temp_hp = excluded.temp_hp, ac = excluded.ac,
                    initiative = excluded.initiative,
                    conditions_json = excluded.conditions_json,
                    is_active = excluded.is_active, turn_order = excluded.turn_order,
                    updated_at = datetime('now')
                RETURNING id
                """,
                (
                    campaign_id,
                    name,
                    kind,
                    max(0, hp),
                    max(1, max_hp),
                    max(0, temp_hp),
                    ac,
                    initiative,
                    json.dumps(conditions or []),
                    1 if is_active else 0,
                    turn_order,
                ),
            )
            return cur.fetchone()[0]

    def get_combatants(self, campaign_id: int, active_only: bool = False) -> list[Combatant]:
        with self._conn() as conn:
            sql = "SELECT * FROM combatants WHERE campaign_id = ?"
            if active_only:
                sql += " AND is_active = 1"
            sql += " ORDER BY turn_order, id"
            rows = conn.execute(sql, (campaign_id,)).fetchall()
            return [self._combatant_from_row(dict(r)) for r in rows]

    def get_combatant(self, campaign_id: int, combatant_id: int) -> Combatant | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM combatants WHERE campaign_id = ? AND id = ?",
                (campaign_id, combatant_id),
            ).fetchone()
            return self._combatant_from_row(dict(row)) if row else None

    def get_combatant_by_name(self, campaign_id: int, name: str) -> Combatant | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM combatants WHERE campaign_id = ? AND name = ?",
                (campaign_id, name),
            ).fetchone()
            return self._combatant_from_row(dict(row)) if row else None

    def update_combatant(
        self,
        combatant_id: int,
        *,
        hp: int | None = None,
        temp_hp: int | None = None,
        conditions: list[dict] | None = None,
        initiative: int | None = None,
        turn_order: int | None = None,
        is_active: bool | None = None,
    ) -> Combatant | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM combatants WHERE id = ?", (combatant_id,)
            ).fetchone()
            if not row:
                return None
            current = self._combatant_from_row(dict(row))
            new_hp = max(0, hp) if hp is not None else current.hp
            new_temp = max(0, temp_hp) if temp_hp is not None else current.temp_hp
            new_conds = conditions if conditions is not None else (current.conditions or [])
            new_init = initiative if initiative is not None else current.initiative
            new_order = turn_order if turn_order is not None else current.turn_order
            new_active = is_active if is_active is not None else current.is_active
            conn.execute(
                """
                UPDATE combatants SET hp = ?, temp_hp = ?, conditions_json = ?,
                    initiative = ?, turn_order = ?, is_active = ?
                WHERE id = ?
                """,
                (
                    new_hp,
                    new_temp,
                    json.dumps(new_conds),
                    new_init,
                    new_order,
                    1 if new_active else 0,
                    combatant_id,
                ),
            )
            return Combatant(
                id=current.id,
                campaign_id=current.campaign_id,
                name=current.name,
                kind=current.kind,
                hp=new_hp,
                max_hp=current.max_hp,
                temp_hp=new_temp,
                ac=current.ac,
                initiative=new_init,
                conditions=new_conds,
                is_active=new_active,
                turn_order=new_order,
            )

    def clear_combatants(self, campaign_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM combatants WHERE campaign_id = ?", (campaign_id,)
            )

    def get_next_turn_num(self, campaign_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_num), 0) FROM campaign_turns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            return (row[0] if row else 0) + 1

    def record_turn(
        self,
        campaign_id: int,
        turn_num: int,
        actor: str,
        action: str,
        narration: str,
        outcome: dict | None = None,
        dice: list[dict] | None = None,
    ) -> int:
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            cur = conn.execute(
                """
                INSERT INTO campaign_turns (campaign_id, turn_num, actor, action,
                                           narration, outcome_json, dice_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    campaign_id,
                    turn_num,
                    actor,
                    action,
                    narration,
                    json.dumps(outcome or {}),
                    json.dumps(dice or []),
                ),
            )
            return cur.fetchone()[0]

    def get_recent_turns(self, campaign_id: int, limit: int = 10) -> list[CampaignTurn]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM campaign_turns WHERE campaign_id = ?"
                " ORDER BY turn_num DESC LIMIT ?",
                (campaign_id, limit),
            ).fetchall()
            out = []
            for r in rows:
                values = dict(r)
                values["outcome"] = json.loads(values.pop("outcome_json") or "{}")
                values["dice"] = json.loads(values.pop("dice_json") or "[]")
                values.pop("created_at", None)
                out.append(CampaignTurn(**values))
            return list(reversed(out))

    def get_quests(self, campaign_id: int) -> list[Quest]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quests WHERE campaign_id = ? ORDER BY name",
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

    def set_quest_objective(
        self, campaign_id: int, quest_name: str, objective_description: str
    ) -> dict | None:
        """Mark one objective of a quest completed; complete the quest when all are done.

        Returns {"quest": name, "objective": description, "quest_completed": bool}
        or None when the quest/objective was not found. Objective matching is
        case-insensitive substring on the objective description.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM quests WHERE campaign_id = ? AND name = ?",
                (campaign_id, quest_name),
            ).fetchone()
            if not row:
                return None
            values = dict(row)
            objectives = json.loads(values.get("objectives_json") or "[]")
            needle = objective_description.strip().lower()
            matched = False
            for obj in objectives:
                if not isinstance(obj, dict):
                    continue
                desc = str(obj.get("description", ""))
                if needle and needle in desc.lower():
                    obj["completed"] = True
                    matched = True
            if not matched:
                return None
            all_done = bool(objectives) and all(
                bool(o.get("completed")) for o in objectives if isinstance(o, dict)
            )
            status = "completed" if all_done else values.get("status", "active")
            conn.execute(
                """
                UPDATE quests SET objectives_json = ?, status = ?,
                    completed_session = CASE WHEN ? = 'completed'
                        THEN COALESCE(completed_session, 1) ELSE completed_session END,
                    updated_at = datetime('now')
                WHERE campaign_id = ? AND name = ?
                """,
                (json.dumps(objectives), status, status, campaign_id, quest_name),
            )
            return {
                "quest": quest_name,
                "objective": objective_description,
                "quest_completed": all_done,
            }

    def mirror_combat_json(self, campaign_id: int) -> str:
        """Rebuild the legacy opaque combat_json from solo combatants + state.

        The spoke still reads campaigns.combat_json; this keeps that mirror
        current without making it the source of truth.
        """
        state = self.get_solo_state(campaign_id)
        combatants = self.get_combatants(campaign_id)
        scene = {
            "phase": state.phase if state else "exploration",
            "round": state.round_num if state else 1,
            "active_combatant_id": state.active_combatant_id if state else None,
            "combatants": [
                {
                    "id": c.id,
                    "name": c.name,
                    "kind": c.kind,
                    "hp": c.hp,
                    "max_hp": c.max_hp,
                    "temp_hp": c.temp_hp,
                    "ac": c.ac,
                    "initiative": c.initiative,
                    "conditions": c.conditions or [],
                    "is_active": c.is_active,
                }
                for c in combatants
            ],
        }
        scene_json = json.dumps(scene)
        self.set_combat_json(campaign_id, scene_json)
        return scene_json

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
        db_path = str(settings.data_dir / "campaign.db")
    return CampaignRepository(str(db_path))