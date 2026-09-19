# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Full-text retrieval over the Pathfinder rules databases.

This consolidates the search logic that was scattered across the original
scripts:

* ``hub_agent.query_db`` — auto-detecting the table shape of each DB
  (``rules`` FTS5, the ``rules_fts`` + ``rules`` pair, ``chunks``, or ``items``).
* ``gm_local.search`` / ``gm_termux_combined.search`` — the edition-filtered
  FTS5 query (``WHERE system=? AND rules MATCH ?``) with the **2e-first,
  then 1e** fallback.

The databases are 500MB+ and live only on the laptop (git-ignored). This module
never writes to them — read-only, with defensive guards so a missing or oddly
shaped DB degrades gracefully instead of crashing the hub.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

# --- Edition handling ------------------------------------------------------

_1E_ALIASES = {"1e", "pf1", "pf1e", "pathfinder 1e", "pathfinder1", "pathfinder first edition"}
_2E_ALIASES = {"2e", "pf2", "pf2e", "pathfinder 2e", "pathfinder2", "pathfinder second edition"}
_BOTH_ALIASES = {"both", "all", "any", "default", ""}


def normalize_edition(raw_edition: str | None) -> str:
    """Map many spellings of an edition down to ``"1e"``, ``"2e"``, or ``"both"``."""
    if raw_edition is None:
        return "both"
    cleaned = str(raw_edition).strip().lower()
    if cleaned in _1E_ALIASES:
        return "1e"
    if cleaned in _2E_ALIASES:
        return "2e"
    if cleaned in _BOTH_ALIASES:
        return "both"
    return cleaned


# Which DB files are relevant for a given edition (used when a DB has no
# per-row `system` column and edition is encoded in the filename instead).
_EDITION_DB_HINTS = {
    "1e": {"pathfinder_god.db", "pathfinder_rag.db", "pathfinder_1e_rag.db"},
    "2e": {"pathfinder_god.db", "pathfinder_rag.db", "pathfinder_2e_rag.db"},
}


@dataclass(frozen=True)
class RuleHit:
    """One retrieved rule snippet."""

    name: str
    content: str
    system: str = ""       # "1e" / "2e" when the DB tracks it
    category: str = ""
    source_book: str = ""

    def as_context_block(self, max_chars: int = 1200) -> str:
        header = self.name or "Rule"
        if self.system:
            header = f"{self.system.upper()} | {header}"
        body = self.content[:max_chars]
        return f"[{header}]\n{body}"


def _build_match_query(search_term: str) -> str:
    """Turn a natural-language question into a forgiving FTS5 MATCH expression.

    Keeps words longer than three characters and OR-joins them so a phrasing
    mismatch still retrieves something (mirrors the original hub_agent logic).
    """
    clean = re.sub(r"[^\w\s]", " ", search_term)
    words = [w for w in clean.split() if len(w) > 3]
    return " OR ".join(words) if words else (clean.strip() or search_term)


class Retriever:
    """Read-only retriever across one or more Pathfinder rules databases."""

    def __init__(self, db_paths: list[Path], rag_limit: int = 4) -> None:
        self._db_paths = list(db_paths)
        self._rag_limit = rag_limit

    # -- public API --------------------------------------------------------

    def search(self, query: str, edition: str = "both", limit: int | None = None) -> list[RuleHit]:
        """Retrieve rule snippets for ``query``.

        For an edition-specific request we try that edition first and, if it
        yields nothing, fall back to the other edition — 2e-first when the
        caller asks for "both", matching the original scripts' behaviour.
        """
        limit = limit or self._rag_limit
        edition = normalize_edition(edition)

        if edition == "2e":
            return self._search_editions(query, ["2e", "1e"], limit)
        if edition == "1e":
            return self._search_editions(query, ["1e", "2e"], limit)
        # "both": prefer 2e, then 1e, then anything.
        return self._search_editions(query, ["2e", "1e", "both"], limit)

    def build_context(self, query: str, edition: str = "both", limit: int | None = None) -> str:
        """Assemble retrieved snippets into a prompt-ready context block."""
        hits = self.search(query, edition=edition, limit=limit)
        if hits:
            return "\n\n".join(h.as_context_block() for h in hits)
        return (
            "No local Pathfinder rule hit was found in the databases. Answer as a "
            "knowledgeable GM using broad Pathfinder principles and clearly state any "
            "assumptions."
        )

    # -- internals ---------------------------------------------------------

    def _search_editions(self, query: str, order: list[str], limit: int) -> list[RuleHit]:
        for edition in order:
            hits = self._search_one_edition(query, edition, limit)
            if hits:
                return hits
        return []

    def _candidate_dbs(self, edition: str) -> list[Path]:
        out: list[Path] = []
        seen: set[Path] = set()
        hint = _EDITION_DB_HINTS.get(edition)
        for path in self._db_paths:
            if path in seen or not path.exists():
                continue
            if hint is None or path.name in hint:
                out.append(path)
            seen.add(path)
        return out

    def _search_one_edition(self, query: str, edition: str, limit: int) -> list[RuleHit]:
        match_query = _build_match_query(query)
        results: list[RuleHit] = []
        for db_path in self._candidate_dbs(edition):
            conn = self._connect(db_path)
            if conn is None:
                continue
            try:
                results.extend(self._query_conn(conn, query, match_query, edition, limit))
            except sqlite3.Error as exc:  # pragma: no cover - runtime guard
                print(f"[RAG] query failed for {db_path.name}: {exc}")
            finally:
                conn.close()
            if len(results) >= limit:
                break
        return results[:limit]

    @staticmethod
    def _connect(db_path: Path) -> sqlite3.Connection | None:
        try:
            # Read-only URI connection: never mutate the user's 500MB DBs.
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10.0)
            conn.execute("PRAGMA busy_timeout = 10000")
            return conn
        except sqlite3.Error as exc:  # pragma: no cover - runtime guard
            print(f"[RAG] unable to open {db_path.name}: {exc}")
            return None

    @staticmethod
    def _tables(conn: sqlite3.Connection) -> set[str]:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
        return {row[0] for row in cur.fetchall()}

    @staticmethod
    def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in cur.fetchall())

    def _query_conn(
        self,
        conn: sqlite3.Connection,
        raw_query: str,
        match_query: str,
        edition: str,
        limit: int,
    ) -> list[RuleHit]:
        tables = self._tables(conn)

        # Shape A: a `rules` FTS5 table with a per-row `system` column
        # (the primary/unified schema used by gm_local & the termux scripts).
        if "rules" in tables and self._has_column(conn, "rules", "raw_content"):
            has_system = self._has_column(conn, "rules", "system")
            try:
                if has_system and edition in ("1e", "2e"):
                    cur = conn.execute(
                        "SELECT system, category, name, source_book, raw_content "
                        "FROM rules WHERE system=? AND rules MATCH ? LIMIT ?",
                        (edition, match_query, limit),
                    )
                else:
                    cur = conn.execute(
                        "SELECT system, category, name, source_book, raw_content "
                        "FROM rules WHERE rules MATCH ? LIMIT ?",
                        (match_query, limit),
                    )
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                # `rules` isn't actually an FTS table here — fall back to LIKE.
                like = f"%{raw_query}%"
                cols = "system, category, name, source_book, raw_content" if has_system else \
                       "'' , '', name, '', raw_content"
                cur = conn.execute(
                    f"SELECT {cols} FROM rules WHERE name LIKE ? OR raw_content LIKE ? LIMIT ?",
                    (like, like, limit),
                )
                rows = cur.fetchall()
            return [
                RuleHit(
                    system=str(r[0] or ""), category=str(r[1] or ""), name=str(r[2] or ""),
                    source_book=str(r[3] or ""), content=str(r[4] or ""),
                )
                for r in rows if r and r[4]
            ]

        # Shape B: separate `rules_fts` index joined to a `rules` content table.
        if "rules_fts" in tables and "rules" in tables:
            cur = conn.execute(
                "SELECT rules.name, rules.raw_content FROM rules_fts "
                "JOIN rules ON rules_fts.rowid = rules.id "
                "WHERE rules_fts MATCH ? ORDER BY rank LIMIT ?",
                (match_query, limit),
            )
            return [RuleHit(name=str(r[0] or ""), content=str(r[1] or "")) for r in cur.fetchall() if r and r[1]]

        # Shape C: a generic `chunks` FTS table (source, content).
        if "chunks" in tables:
            cur = conn.execute("SELECT source, content FROM chunks WHERE chunks MATCH ? LIMIT ?", (match_query, limit))
            return [RuleHit(name=str(r[0] or ""), content=str(r[1] or "")) for r in cur.fetchall() if r and r[1]]

        # Shape D: a generic `items` FTS table (name, content).
        if "items" in tables:
            cur = conn.execute("SELECT name, content FROM items WHERE items MATCH ? LIMIT ?", (match_query, limit))
            return [RuleHit(name=str(r[0] or ""), content=str(r[1] or "")) for r in cur.fetchall() if r and r[1]]

        return []
