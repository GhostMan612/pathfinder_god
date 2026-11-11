# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Campaign Repository — SQLite CRUD + queries for Campaign & Continuity data.
"""

import hashlib
import json
import logging
import sqlite3
import struct
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path

from app.agents.encounter_state import (
    TERMINAL_STATUSES,
    validate_kind,
    validate_status,
    validate_transition,
)
from app.config import settings
from app.rag._fts import build_match_query

logger = logging.getLogger(__name__)

# Ceiling on sessions.raw_log, applied in SQL on every turn append. Without it
# the transcript grows without bound, SQLite rewrites the whole TEXT value on
# every append (so write cost is O(n^2) over a session), the auto-fold hands the
# entire log to the LLM, and an unbounded string reaches the system prompt.
# Only the most recent window is kept; durable history lives in the summaries
# and the entity ledger, not in this debugging aid.
_RAW_LOG_MAX_CHARS = 100_000

#: Traversable link kinds in the breadcrumb graph. ``trail`` is the lazy edge
#: recorded the first time the party travels between two known locations.
EDGE_KINDS = ("road", "trail", "door", "stairs", "portal", "other")


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
    next_turn_num: int = 1
    world_tick: int = 0


@dataclass
class Encounter:
    id: int
    campaign_id: int
    kind: str
    status: str
    summary: str = ""
    state: dict = field(default_factory=dict)
    location_id: int | None = None
    seed: int | None = None
    resolved_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "kind": self.kind,
            "status": self.status,
            "summary": self.summary,
            "state": self.state,
            "location_id": self.location_id,
            "seed": self.seed,
            "resolved_at": self.resolved_at,
        }


@dataclass
class LocationEdge:
    id: int
    campaign_id: int
    from_location_id: int
    to_location_id: int
    kind: str = "trail"
    label: str = ""
    travel_ticks: int = 1
    description: str | None = None
    state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "from_location_id": self.from_location_id,
            "to_location_id": self.to_location_id,
            "kind": self.kind,
            "label": self.label,
            "travel_ticks": self.travel_ticks,
            "description": self.description,
            "state": self.state,
        }


@dataclass
class CampaignEvent:
    id: int
    campaign_id: int
    tick: int
    kind: str
    summary: str = ""
    location_id: int | None = None
    encounter_id: int | None = None
    data: dict = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "tick": self.tick,
            "kind": self.kind,
            "summary": self.summary,
            "location_id": self.location_id,
            "encounter_id": self.encounter_id,
            "data": self.data,
            "created_at": self.created_at,
        }


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
                # Older solo_state rows predate next_turn_num (the locked turn
                # counter). Add it and backfill from the highest recorded
                # turn, so existing campaigns resume numbering without
                # colliding with turns they already have.
                try:
                    conn.execute(
                        "ALTER TABLE solo_state ADD COLUMN next_turn_num "
                        "INTEGER NOT NULL DEFAULT 1"
                    )
                    conn.execute(
                        """
                        UPDATE solo_state SET next_turn_num = (
                            SELECT COALESCE(MAX(turn_num), 0) + 1
                            FROM campaign_turns
                            WHERE campaign_turns.campaign_id = solo_state.campaign_id
                        )
                        """
                    )
                except sqlite3.OperationalError:
                    pass
                # World clock and encounter location were added with the
                # breadcrumb graph. ALTER is idempotent-by-exception so the
                # same _init_db path upgrades a live campaign.db in place.
                try:
                    conn.execute(
                        "ALTER TABLE solo_state ADD COLUMN world_tick "
                        "INTEGER NOT NULL DEFAULT 0"
                    )
                except sqlite3.OperationalError:
                    pass
                try:
                    conn.execute(
                        "ALTER TABLE encounters ADD COLUMN location_id "
                        "INTEGER REFERENCES locations(id) ON DELETE SET NULL"
                    )
                except sqlite3.OperationalError:
                    pass
                # schema.sql cannot index encounters.location_id before this
                # ALTER runs on an old database, so create it here.
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_encounters_location "
                    "ON encounters(campaign_id, location_id)"
                )
                # Older campaign.db files carry UNIQUE(campaign_id, name) on
                # combatants, which collapsed duplicate monsters into one row:
                # upserting a second "Goblin" overwrote the first one's HP/AC.
                # Rebuild the table without that constraint, preserving rows.
                try:
                    row = conn.execute(
                        "SELECT sql FROM sqlite_master "
                        "WHERE type = 'table' AND name = 'combatants'"
                    ).fetchone()
                    if row and row[0] and "UNIQUE(campaign_id, name)" in row[0]:
                        conn.execute(
                            "ALTER TABLE combatants RENAME TO combatants_legacy"
                        )
                        conn.execute(
                            """
                            CREATE TABLE combatants (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                                name TEXT NOT NULL,
                                kind TEXT CHECK(kind IN ('hero','npc','monster')) DEFAULT 'monster',
                                hp INTEGER NOT NULL DEFAULT 1,
                                max_hp INTEGER NOT NULL DEFAULT 1,
                                temp_hp INTEGER NOT NULL DEFAULT 0,
                                ac INTEGER NOT NULL DEFAULT 10,
                                initiative INTEGER NOT NULL DEFAULT 0,
                                conditions_json TEXT NOT NULL DEFAULT '[]',
                                is_active INTEGER NOT NULL DEFAULT 1,
                                turn_order INTEGER NOT NULL DEFAULT 0,
                                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                            )
                            """
                        )
                        conn.execute(
                            """
                            INSERT INTO combatants
                                (id, campaign_id, name, kind, hp, max_hp, temp_hp, ac,
                                 initiative, conditions_json, is_active, turn_order,
                                 created_at, updated_at)
                            SELECT id, campaign_id, name, kind, hp, max_hp, temp_hp, ac,
                                   initiative, conditions_json, is_active, turn_order,
                                   created_at, updated_at
                            FROM combatants_legacy
                            """
                        )
                        conn.execute("DROP TABLE combatants_legacy")
                        # schema.sql ran before this rebuild, so the old
                        # index/trigger followed the renamed table and were
                        # dropped with it. Recreate them on the new table.
                        conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_combatants_campaign "
                            "ON combatants(campaign_id)"
                        )
                        conn.execute(
                            """
                            CREATE TRIGGER IF NOT EXISTS trigger_combatants_updated
                            AFTER UPDATE ON combatants
                            BEGIN
                                UPDATE combatants SET updated_at = datetime('now')
                                WHERE id = NEW.id;
                            END
                            """
                        )
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

    def search_sessions_lexical(self, query: str, campaign_id: int = 1, limit: int = 5) -> list[dict]:
        """Full-text search across saved session summaries/facts/logs."""
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

    def search_sessions_hybrid(
        self,
        query: str,
        campaign_id: int = 1,
        limit: int = 5,
        embedder: object | None = None,
    ) -> list[dict]:
        bounded_query = (query or "").strip()[:200]
        if not bounded_query or limit <= 0:
            return []
        if not build_match_query(bounded_query):
            return []

        lexical = self.search_sessions_lexical(query, campaign_id=campaign_id, limit=limit)

        try:
            with self._conn() as conn:
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
                sessions_rows = conn.execute(
                    """
                    SELECT session_num, summary, facts_json, substr(raw_log, 1, 1200) AS excerpt
                    FROM sessions
                    WHERE campaign_id = ?
                    ORDER BY session_num ASC
                    """,
                    (campaign_id,),
                ).fetchall()
                if not sessions_rows:
                    return lexical

                cached_rows = conn.execute(
                    "SELECT session_num, content_hash, vector_blob FROM session_embeddings WHERE campaign_id = ?",
                    (campaign_id,),
                ).fetchall()
                cached_embeddings = {r["session_num"]: (r["content_hash"], r["vector_blob"]) for r in cached_rows}

                active_embedder = embedder
                if active_embedder is None:
                    from app.rag.semantic_spine.ollama import OllamaEmbedder
                    active_embedder = OllamaEmbedder(
                        endpoint=settings.ollama_host,
                        model=settings.semantic_model,
                        dimensions=settings.semantic_dimensions,
                        timeout_s=min(getattr(settings, "semantic_timeout_s", 15.0), 10.0),
                        num_ctx=4096,
                    )

                dim = getattr(active_embedder, "dimensions", settings.semantic_dimensions)
                session_vectors: dict[int, tuple[float, ...]] = {}
                to_embed: list[tuple[int, str, str]] = []

                for row in sessions_rows:
                    s_num = row["session_num"]
                    summary = row["summary"] or ""
                    facts = row["facts_json"] or "[]"
                    excerpt = row["excerpt"] or ""
                    doc_text = f"Session {s_num}: {summary}\nKey facts: {facts}\nEvents: {excerpt}"[:1800]
                    h = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

                    if s_num in cached_embeddings and cached_embeddings[s_num][0] == h:
                        blob = cached_embeddings[s_num][1]
                        if len(blob) == dim * 4:
                            session_vectors[s_num] = struct.unpack(f"{dim}f", blob)
                            continue

                    to_embed.append((s_num, h, doc_text))

                if to_embed:
                    texts = [t[2] for t in to_embed]
                    vectors = active_embedder.embed(texts, query=False)
                    for (s_num, h, _), vec in zip(to_embed, vectors):
                        session_vectors[s_num] = vec
                        blob = struct.pack(f"{len(vec)}f", *vec)
                        conn.execute(
                            """
                            INSERT INTO session_embeddings (campaign_id, session_num, content_hash, vector_blob)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(campaign_id, session_num) DO UPDATE SET
                                content_hash = excluded.content_hash,
                                vector_blob = excluded.vector_blob
                            """,
                            (campaign_id, s_num, h, blob),
                        )
                    conn.commit()

                query_vec = active_embedder.embed([bounded_query], query=True)[0]
                scored: list[tuple[int, float]] = []
                for s_num, s_vec in session_vectors.items():
                    dot = sum(a * b for a, b in zip(query_vec, s_vec))
                    scored.append((s_num, dot))
                scored.sort(key=lambda x: -x[1])

                session_dict = {}
                for row in sessions_rows:
                    d = dict(row)
                    d["campaign_id"] = campaign_id
                    try:
                        d["facts_json"] = json.loads(d.get("facts_json") or "[]")
                    except Exception:
                        d["facts_json"] = []
                    session_dict[row["session_num"]] = d

                rrf_scores: dict[int, float] = {}
                rrf_k = 60
                for rank, hit in enumerate(lexical, 1):
                    s_num = hit["session_num"]
                    rrf_scores[s_num] = rrf_scores.get(s_num, 0.0) + 1.0 / (rrf_k + rank)

                for rank, (s_num, _) in enumerate(scored, 1):
                    rrf_scores[s_num] = rrf_scores.get(s_num, 0.0) + 0.8 / (rrf_k + rank)

                fused_order = sorted(rrf_scores.keys(), key=lambda s: -rrf_scores[s])
                return [session_dict[s_num] for s_num in fused_order if s_num in session_dict][:limit]
        except Exception:
            logger.warning("Semantic campaign recall failed, falling back to lexical FTS5", exc_info=True)
            return lexical

    def search_sessions(
        self,
        query: str,
        campaign_id: int = 1,
        limit: int = 5,
        embedder: object | None = None,
    ) -> list[dict]:
        """Recall past sessions. Uses semantic hybrid search when enabled, with lexical fallback."""
        if getattr(settings, "semantic_recall_enabled", False) or getattr(settings, "semantic_enabled", False):
            return self.search_sessions_hybrid(query, campaign_id=campaign_id, limit=limit, embedder=embedder)
        return self.search_sessions_lexical(query, campaign_id=campaign_id, limit=limit)

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

    @staticmethod
    def _location_from_row(row: dict) -> Location:
        values = dict(row)
        values["facts"] = json.loads(values.pop("facts_json") or "[]")
        values.pop("created_at", None)
        values.pop("updated_at", None)
        return Location(**values)

    def get_locations(self, campaign_id: int) -> list[Location]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM locations WHERE campaign_id = ? ORDER BY name",
                (campaign_id,),
            ).fetchall()
            return [self._location_from_row(dict(r)) for r in rows]

    def get_location(self, campaign_id: int, location_id: int) -> Location | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM locations WHERE campaign_id = ? AND id = ?",
                (campaign_id, location_id),
            ).fetchone()
            return self._location_from_row(dict(row)) if row else None

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
        world_tick: int | None = None,
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
        new_tick = world_tick if world_tick is not None else state.world_tick
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE solo_state SET phase = ?, round_num = ?,
                    current_location_id = ?, active_combatant_id = ?,
                    turn_order_json = ?, world_tick = ?
                WHERE campaign_id = ?
                """,
                (
                    new_phase,
                    new_round,
                    new_location,
                    new_active,
                    json.dumps(new_order),
                    new_tick,
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
            next_turn_num=state.next_turn_num,
            world_tick=new_tick,
        )

    def set_current_location(self, campaign_id: int, location_id: int) -> SoloState:
        return self.update_solo_state(campaign_id, current_location_id=location_id)

    # ── Breadcrumb graph and campaign event log ──────────────────────────

    @staticmethod
    def _edge_from_row(row: dict) -> LocationEdge:
        values = dict(row)
        values["state"] = json.loads(values.pop("state_json") or "{}")
        values.pop("created_at", None)
        values.pop("updated_at", None)
        return LocationEdge(**values)

    @staticmethod
    def _require_location(conn, campaign_id: int, location_id: int) -> dict:
        row = conn.execute(
            "SELECT id, name FROM locations WHERE campaign_id = ? AND id = ?",
            (campaign_id, location_id),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"no location {location_id} in campaign {campaign_id}"
            )
        return dict(row)

    def _upsert_location_edge_on_conn(
        self,
        conn,
        campaign_id: int,
        from_location_id: int,
        to_location_id: int,
        *,
        kind: str,
        label: str,
        travel_ticks: int,
        description: str | None,
        state: dict,
    ) -> LocationEdge:
        self._require_location(conn, campaign_id, from_location_id)
        self._require_location(conn, campaign_id, to_location_id)
        row = conn.execute(
            """
            INSERT INTO location_edges
                (campaign_id, from_location_id, to_location_id, kind, label,
                 travel_ticks, description, state_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(campaign_id, from_location_id, to_location_id)
            DO UPDATE SET
                kind = excluded.kind,
                label = excluded.label,
                travel_ticks = excluded.travel_ticks,
                description = excluded.description,
                state_json = excluded.state_json,
                updated_at = datetime('now')
            RETURNING *
            """,
            (
                campaign_id,
                from_location_id,
                to_location_id,
                kind,
                label,
                travel_ticks,
                description,
                json.dumps(state),
            ),
        ).fetchone()
        return self._edge_from_row(dict(row))

    def upsert_location_edge(
        self,
        campaign_id: int,
        from_location_id: int,
        to_location_id: int,
        *,
        kind: str = "trail",
        label: str = "",
        travel_ticks: int = 1,
        description: str | None = None,
        state: dict | None = None,
        bidirectional: bool = False,
    ) -> LocationEdge:
        """Create or update one directed edge between two campaign locations.

        ``bidirectional=True`` also writes the reverse edge with the same
        properties. Lazy trail edges use the same upsert, so repeated travel
        never duplicates graph rows.
        """
        if from_location_id == to_location_id:
            raise ValueError("a location edge cannot connect a location to itself")
        if kind not in EDGE_KINDS:
            raise ValueError(
                f"unknown edge kind {kind!r}; expected one of: "
                + ", ".join(EDGE_KINDS)
            )
        if int(travel_ticks) < 1:
            raise ValueError("travel_ticks must be at least 1")
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            edge = self._upsert_location_edge_on_conn(
                conn,
                campaign_id,
                from_location_id,
                to_location_id,
                kind=kind,
                label=label,
                travel_ticks=int(travel_ticks),
                description=description,
                state=state or {},
            )
            if bidirectional:
                self._upsert_location_edge_on_conn(
                    conn,
                    campaign_id,
                    to_location_id,
                    from_location_id,
                    kind=kind,
                    label=label,
                    travel_ticks=int(travel_ticks),
                    description=description,
                    state=state or {},
                )
            return edge

    def get_location_edges(
        self, campaign_id: int, location_id: int | None = None
    ) -> list[LocationEdge]:
        with self._conn() as conn:
            if location_id is None:
                rows = conn.execute(
                    "SELECT * FROM location_edges WHERE campaign_id = ? "
                    "ORDER BY id",
                    (campaign_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM location_edges WHERE campaign_id = ? "
                    "AND (from_location_id = ? OR to_location_id = ?) "
                    "ORDER BY id",
                    (campaign_id, location_id, location_id),
                ).fetchall()
            return [self._edge_from_row(dict(row)) for row in rows]

    @staticmethod
    def _world_tick_on_conn(conn, campaign_id: int) -> int:
        row = conn.execute(
            "SELECT world_tick FROM solo_state WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        return int(row["world_tick"]) if row else 0

    def _append_event_on_conn(
        self,
        conn,
        campaign_id: int,
        kind: str,
        *,
        tick: int,
        summary: str = "",
        location_id: int | None = None,
        encounter_id: int | None = None,
        data: dict | None = None,
    ) -> CampaignEvent:
        if not kind or len(kind) > 80:
            raise ValueError("event kind must be 1-80 characters")
        if tick < 0:
            raise ValueError("event tick cannot be negative")
        if location_id is not None:
            self._require_location(conn, campaign_id, location_id)
        if encounter_id is not None:
            row = conn.execute(
                "SELECT id FROM encounters WHERE campaign_id = ? AND id = ?",
                (campaign_id, encounter_id),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"no encounter {encounter_id} in campaign {campaign_id}"
                )
        row = conn.execute(
            """
            INSERT INTO campaign_events
                (campaign_id, tick, kind, summary, location_id, encounter_id,
                 data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                campaign_id,
                tick,
                kind,
                summary,
                location_id,
                encounter_id,
                json.dumps(data or {}),
            ),
        ).fetchone()
        values = dict(row)
        values["data"] = json.loads(values.pop("data_json") or "{}")
        return CampaignEvent(**values)

    def append_event(
        self,
        campaign_id: int,
        kind: str,
        *,
        tick: int | None = None,
        summary: str = "",
        location_id: int | None = None,
        encounter_id: int | None = None,
        data: dict | None = None,
    ) -> CampaignEvent:
        """Append one immutable event at ``tick`` (default: current world tick)."""
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            if tick is None:
                tick = self._world_tick_on_conn(conn, campaign_id)
            return self._append_event_on_conn(
                conn,
                campaign_id,
                kind,
                tick=int(tick),
                summary=summary,
                location_id=location_id,
                encounter_id=encounter_id,
                data=data,
            )

    def list_events(
        self,
        campaign_id: int,
        *,
        limit: int = 50,
        since_tick: int | None = None,
        location_id: int | None = None,
        encounter_id: int | None = None,
        kind: str | None = None,
    ) -> list[CampaignEvent]:
        """Return the most recent events, ordered oldest-first for replay."""
        limit = max(1, min(int(limit), 200))
        clauses = ["campaign_id = ?"]
        params: list[object] = [campaign_id]
        if since_tick is not None:
            clauses.append("tick >= ?")
            params.append(int(since_tick))
        if location_id is not None:
            clauses.append("location_id = ?")
            params.append(int(location_id))
        if encounter_id is not None:
            clauses.append("encounter_id = ?")
            params.append(int(encounter_id))
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM campaign_events WHERE "
                + " AND ".join(clauses)
                + " ORDER BY tick DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
            events = []
            for row in rows:
                values = dict(row)
                values["data"] = json.loads(values.pop("data_json") or "{}")
                events.append(CampaignEvent(**values))
            events.reverse()
            return events

    def count_events(self, campaign_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM campaign_events WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            return int(row[0])

    def move_to_location(
        self,
        campaign_id: int,
        to_location_id: int,
        *,
        summary: str = "",
        data: dict | None = None,
    ) -> dict:
        """Move the party to a known location, advancing the world clock.

        An existing directed edge supplies ``travel_ticks``. If the party has
        never traveled this route before, a discovered trail edge is recorded
        so the breadcrumb graph accumulates as the campaign does.
        """
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            target = self._require_location(conn, campaign_id, to_location_id)
            conn.execute(
                "INSERT INTO solo_state (campaign_id) VALUES (?) "
                "ON CONFLICT(campaign_id) DO NOTHING",
                (campaign_id,),
            )
            state_row = conn.execute(
                "SELECT current_location_id, world_tick FROM solo_state "
                "WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            from_location_id = state_row["current_location_id"]
            current_tick = int(state_row["world_tick"] or 0)
            if from_location_id == to_location_id:
                raise ValueError(
                    f"party is already at location {to_location_id}"
                )

            edge: LocationEdge | None = None
            if from_location_id is not None:
                row = conn.execute(
                    "SELECT * FROM location_edges WHERE campaign_id = ? "
                    "AND from_location_id = ? AND to_location_id = ?",
                    (campaign_id, from_location_id, to_location_id),
                ).fetchone()
                if row is not None:
                    edge = self._edge_from_row(dict(row))
                else:
                    edge = self._upsert_location_edge_on_conn(
                        conn,
                        campaign_id,
                        from_location_id,
                        to_location_id,
                        kind="trail",
                        label="",
                        travel_ticks=1,
                        description="Discovered by travel.",
                        state={},
                    )
                    # A discovered route is usable in both directions, but
                    # never overwrite an explicit reverse edge (a road may
                    # already describe the way back with different ticks).
                    reverse = conn.execute(
                        "SELECT id FROM location_edges WHERE campaign_id = ? "
                        "AND from_location_id = ? AND to_location_id = ?",
                        (campaign_id, to_location_id, from_location_id),
                    ).fetchone()
                    if reverse is None:
                        self._upsert_location_edge_on_conn(
                            conn,
                            campaign_id,
                            to_location_id,
                            from_location_id,
                            kind="trail",
                            label="",
                            travel_ticks=1,
                            description="Discovered by travel.",
                            state={},
                        )

            travel_ticks = edge.travel_ticks if edge is not None else 1
            new_tick = current_tick + max(1, travel_ticks)
            conn.execute(
                "UPDATE solo_state SET current_location_id = ?, world_tick = ? "
                "WHERE campaign_id = ?",
                (to_location_id, new_tick, campaign_id),
            )
            payload = {
                "from_location_id": from_location_id,
                "to_location_id": to_location_id,
                "edge_id": edge.id if edge is not None else None,
                "travel_ticks": travel_ticks,
            }
            if data:
                payload["detail"] = data
            event = self._append_event_on_conn(
                conn,
                campaign_id,
                "move",
                tick=new_tick,
                summary=summary or f"Traveled to {target['name']}",
                location_id=to_location_id,
                data=payload,
            )
            return {
                "campaign_id": campaign_id,
                "location": target["name"],
                "location_id": to_location_id,
                "from_location_id": from_location_id,
                "tick": new_tick,
                "edge": edge,
                "event": event,
            }

    # ── Encounter lifecycle ─────────────────────────────────────

    @staticmethod
    def _encounter_from_row(row: dict) -> Encounter:
        values = dict(row)
        values["state"] = json.loads(values.pop("state_json") or "{}")
        values.pop("created_at", None)
        values.pop("updated_at", None)
        return Encounter(**values)

    def create_encounter(
        self,
        campaign_id: int,
        kind: str,
        *,
        summary: str = "",
        state: dict | None = None,
        seed: int | None = None,
        status: str = "pending",
        location_id: int | None = None,
    ) -> Encounter:
        """Create an encounter in ``pending`` (or explicitly ``active``) state.

        When ``location_id`` is omitted the encounter attaches to the party's
        current location, so every encounter is a node on the breadcrumb trail.
        Creation appends an ``encounter_created`` event at the current tick.
        """
        validate_kind(kind)
        validate_status(status)
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            if location_id is not None:
                self._require_location(conn, campaign_id, location_id)
            else:
                row = conn.execute(
                    "SELECT current_location_id FROM solo_state "
                    "WHERE campaign_id = ?",
                    (campaign_id,),
                ).fetchone()
                location_id = row["current_location_id"] if row else None
            if status == "active":
                active = conn.execute(
                    "SELECT id FROM encounters "
                    "WHERE campaign_id = ? AND status = 'active'",
                    (campaign_id,),
                ).fetchone()
                if active is not None:
                    raise ValueError(
                        f"campaign {campaign_id} already has an active encounter"
                    )
            try:
                row = conn.execute(
                    """
                    INSERT INTO encounters
                        (campaign_id, location_id, kind, status, summary,
                         state_json, seed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    RETURNING *
                    """,
                    (
                        campaign_id,
                        location_id,
                        kind,
                        status,
                        summary,
                        json.dumps(state or {}),
                        seed,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"campaign {campaign_id} already has an active encounter"
                ) from exc
            encounter = self._encounter_from_row(dict(row))
            self._append_event_on_conn(
                conn,
                campaign_id,
                "encounter_created",
                tick=self._world_tick_on_conn(conn, campaign_id),
                summary=summary or f"{kind.title()} encounter created",
                location_id=location_id,
                encounter_id=encounter.id,
                data={"kind": kind, "status": status},
            )
            return encounter

    def get_encounter(self, campaign_id: int, encounter_id: int) -> Encounter | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM encounters WHERE campaign_id = ? AND id = ?",
                (campaign_id, encounter_id),
            ).fetchone()
            return self._encounter_from_row(dict(row)) if row else None

    def get_active_encounter(self, campaign_id: int) -> Encounter | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM encounters "
                "WHERE campaign_id = ? AND status = 'active'",
                (campaign_id,),
            ).fetchone()
            return self._encounter_from_row(dict(row)) if row else None

    def list_encounters(self, campaign_id: int, limit: int = 50) -> list[Encounter]:
        limit = max(1, min(int(limit), 200))
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM encounters WHERE campaign_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (campaign_id, limit),
            ).fetchall()
            return [self._encounter_from_row(dict(row)) for row in rows]

    def transition_encounter(
        self,
        campaign_id: int,
        encounter_id: int,
        status: str,
        *,
        summary: str | None = None,
        state: dict | None = None,
    ) -> Encounter:
        """Apply one validated lifecycle transition to an existing encounter."""
        validate_status(status)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM encounters WHERE campaign_id = ? AND id = ?",
                (campaign_id, encounter_id),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"no encounter {encounter_id} in campaign {campaign_id}"
                )
            current = self._encounter_from_row(dict(row))
            validate_transition(current.status, status)

            new_summary = summary if summary is not None else current.summary
            new_state = state if state is not None else current.state
            assignments = [
                "status = ?",
                "summary = ?",
                "state_json = ?",
                "updated_at = datetime('now')",
            ]
            params: list[object] = [
                status,
                new_summary,
                json.dumps(new_state),
            ]
            if status in TERMINAL_STATUSES:
                assignments.append("resolved_at = datetime('now')")
            params.extend([campaign_id, encounter_id])
            try:
                conn.execute(
                    f"UPDATE encounters SET {', '.join(assignments)} "
                    "WHERE campaign_id = ? AND id = ?",
                    params,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"campaign {campaign_id} already has an active encounter"
                ) from exc
            row = conn.execute(
                "SELECT * FROM encounters WHERE campaign_id = ? AND id = ?",
                (campaign_id, encounter_id),
            ).fetchone()
            updated = self._encounter_from_row(dict(row))
            self._append_event_on_conn(
                conn,
                campaign_id,
                "encounter_transition",
                tick=self._world_tick_on_conn(conn, campaign_id),
                summary=new_summary or f"{updated.kind.title()} {status}",
                location_id=updated.location_id,
                encounter_id=updated.id,
                data={
                    "kind": updated.kind,
                    "from": current.status,
                    "to": status,
                },
            )
            return updated

    def resolve_active_encounter(
        self,
        campaign_id: int,
        status: str = "resolved",
        *,
        summary: str | None = None,
        state: dict | None = None,
    ) -> Encounter | None:
        """Resolve the campaign's active encounter, if one exists."""
        active = self.get_active_encounter(campaign_id)
        if active is None:
            return None
        return self.transition_encounter(
            campaign_id, active.id, status, summary=summary, state=state
        )

    def abandon_active_encounter(
        self, campaign_id: int, *, summary: str | None = None
    ) -> Encounter | None:
        """Abandon the campaign's active encounter, if one exists."""
        active = self.get_active_encounter(campaign_id)
        if active is None:
            return None
        return self.transition_encounter(
            campaign_id, active.id, "abandoned", summary=summary
        )

    def attach_encounter_map(
        self,
        campaign_id: int,
        encounter_id: int,
        map_state: dict,
    ) -> Encounter:
        """Store the generated battle map on an encounter without changing status.

        The map is part of the encounter's state (not the transient HTTP
        response): the client can reopen the encounter and still find the grid,
        token cells, and encounter/combatant links. Existing state keys are
        preserved so this cannot erase round or roster metadata.
        """
        if not isinstance(map_state, dict):
            raise TypeError("encounter map state must be an object")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM encounters WHERE campaign_id = ? AND id = ?",
                (campaign_id, encounter_id),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"no encounter {encounter_id} in campaign {campaign_id}"
                )
            current = self._encounter_from_row(dict(row))
            state = dict(current.state)
            state["map"] = map_state
            conn.execute(
                "UPDATE encounters SET state_json = ?, "
                "updated_at = datetime('now') "
                "WHERE campaign_id = ? AND id = ?",
                (json.dumps(state), campaign_id, encounter_id),
            )
            row = conn.execute(
                "SELECT * FROM encounters WHERE campaign_id = ? AND id = ?",
                (campaign_id, encounter_id),
            ).fetchone()
            return self._encounter_from_row(dict(row))

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
        """Insert or refresh the single combatant row for (campaign_id, name).

        Heroes are unique by name, so re-adding a hero refreshes its row.
        Monsters must NOT use this: several monsters may share a name, so
        start_combat inserts them with add_combatant instead. (The old
        UNIQUE(campaign_id, name) + ON CONFLICT upsert silently overwrote
        the first monster whenever a duplicate name was added.)
        """
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            existing = conn.execute(
                "SELECT id FROM combatants WHERE campaign_id = ? AND name = ? "
                "ORDER BY id LIMIT 1",
                (campaign_id, name),
            ).fetchone()
            if existing is not None:
                conn.execute(
                    """
                    UPDATE combatants SET kind = ?, hp = ?, max_hp = ?, temp_hp = ?,
                        ac = ?, initiative = ?, conditions_json = ?,
                        is_active = ?, turn_order = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        kind,
                        max(0, hp),
                        max(1, max_hp),
                        max(0, temp_hp),
                        ac,
                        initiative,
                        json.dumps(conditions or []),
                        1 if is_active else 0,
                        turn_order,
                        existing[0],
                    ),
                )
                return existing[0]
            return self._insert_combatant(
                conn,
                campaign_id,
                name,
                kind,
                hp,
                max_hp,
                temp_hp,
                ac,
                initiative,
                conditions,
                turn_order,
                is_active,
            )

    def add_combatant(
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
        """Always insert a new combatant row, even if the name already exists.

        Use for monsters: an encounter may field several creatures with the
        same name, and each one needs its own HP/AC/initiative row.
        """
        with self._conn() as conn:
            self._ensure_campaign(conn, campaign_id)
            return self._insert_combatant(
                conn,
                campaign_id,
                name,
                kind,
                hp,
                max_hp,
                temp_hp,
                ac,
                initiative,
                conditions,
                turn_order,
                is_active,
            )

    @staticmethod
    def _insert_combatant(
        conn,
        campaign_id: int,
        name: str,
        kind: str,
        hp: int,
        max_hp: int,
        temp_hp: int,
        ac: int,
        initiative: int,
        conditions: list[dict] | None,
        turn_order: int,
        is_active: bool,
    ) -> int:
        cur = conn.execute(
            """
            INSERT INTO combatants (campaign_id, name, kind, hp, max_hp, temp_hp,
                                   ac, initiative, conditions_json, is_active, turn_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        return cur.lastrowid

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

    def clear_non_hero_combatants(self, campaign_id: int) -> int:
        """Remove the encounter roster but keep persistent hero rows.

        start_combat used to clear every combatant, including heroes, and then
        recreate them at full HP. That silently erased wounds, Dying/Wounded
        conditions, and rest healing between encounters. Heroes now survive;
        only monsters/NPCs from the previous fight are discarded.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM combatants WHERE campaign_id = ? AND kind != 'hero'",
                (campaign_id,),
            )
            return cur.rowcount

    def deactivate_combatants(self, campaign_id: int) -> int:
        """Mark every combatant in the campaign inactive; returns how many
        changed. Ending combat must do this: flipping solo_state to
        exploration alone left a live combat roster behind, so the next
        exploration turn still saw active foes."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE combatants SET is_active = 0 "
                "WHERE campaign_id = ? AND is_active = 1",
                (campaign_id,),
            )
            return cur.rowcount

    def get_next_turn_num(self, campaign_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_num), 0) FROM campaign_turns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            return (row[0] if row else 0) + 1

    def reserve_turn_num(self, campaign_id: int) -> int:
        """Atomically reserve the next turn number for a campaign.

        The old path computed MAX(turn_num)+1 in one connection and inserted
        the turn in another, so two concurrent turns could reserve the same
        number and the second insert then failed on
        UNIQUE(campaign_id, turn_num). This holds BEGIN IMMEDIATE across the
        read and the counter increment on the solo_state row, so each caller
        gets a distinct number. A reserved number is consumed even if the
        turn later fails — turn numbers may skip, never collide.
        """
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
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
                "SELECT next_turn_num FROM solo_state WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            turn_num = int(row[0]) if row else 1
            # Belt and braces: if the counter is ever stale (a solo_state
            # row created after turns were already recorded), never hand
            # out a number a recorded turn already holds.
            max_row = conn.execute(
                "SELECT COALESCE(MAX(turn_num), 0) FROM campaign_turns "
                "WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            turn_num = max(turn_num, int(max_row[0]) + 1 if max_row else 1)
            conn.execute(
                "UPDATE solo_state SET next_turn_num = ? WHERE campaign_id = ?",
                (turn_num + 1, campaign_id),
            )
            return turn_num

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