# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
RAG Retriever — Hybrid vector + FTS5 search for rule context.
"""

import logging
import sqlite3
from pathlib import Path

import anyio

from app.config import get_settings
from app.db.repository import CampaignRepository
from app.rag._fts import build_match_query, editions_for
from app.rag.semantic_spine import hybrid_search

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, repo: CampaignRepository):
        self.repo = repo
        self.settings = get_settings()

    def _get_db_path(self, edition: str) -> str:
        """Find the appropriate DB for the edition."""
        for p in self.settings.db_paths:
            if p.exists():
                return str(p)
        # Fallback to first configured
        return str(self.settings.db_paths[0])

    async def retrieve(self, query: str, edition: str = "both", limit: int = 5) -> list[dict]:
        """Unified entrypoint: FTS5 lexical baseline fused with optional semantic sidecar."""
        lexical = await self._fts5_search(query, edition, limit)
        source_path = Path(self._get_db_path(edition))
        return await hybrid_search(query, edition, limit, lexical, source_path=source_path)

    async def query(self, query: str, edition: str = "both", k: int = 5) -> list[dict]:
        """Hybrid search: FTS5 + vector (when enabled)."""
        return await self.retrieve(query, edition, k)

    async def _fts5_search(self, query: str, edition: str, k: int) -> list[dict]:
        # The body below is synchronous sqlite3 work on a 58 MB database,
        # measured at ~294 ms per query, and /ask runs it twice (query() plus
        # get_sources()). Calling it directly from an async def froze the event
        # loop for ~600-900 ms per request, stalling /health, the WebSocket
        # /stream and the metrics middleware. Offload to a worker thread.
        return await anyio.to_thread.run_sync(self._fts5_search_sync, query, edition, k)

    def _fts5_search_sync(self, query: str, edition: str, k: int) -> list[dict]:
        db_path = self._get_db_path(edition)

        escaped = build_match_query(query)
        if not escaped:
            return []

        # Edition order: 2E first, then 1E (for "both") - DB uses uppercase
        editions = editions_for(edition)

        all_results = []
        seen: set[str] = set()
        for ed in editions:
            if len(all_results) >= k:
                break

            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                need = k - len(all_results)

                def take(rows: list) -> None:
                    for row in rows:
                        key = (row["name"] or "").strip().lower()
                        if key and key in seen:
                            continue
                        if key:
                            seen.add(key)
                        all_results.append({
                            "system": row["system"],
                            "category": row["category"],
                            "name": row["name"],
                            "source_book": row["source_book"],
                            "content": row["raw_content"],
                        })

                # Tier 0: exact name match — "Flanking" must return Flanking,
                # not Mirror's Reflection.
                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content"
                    " FROM rules WHERE system = ? AND name = ? COLLATE NOCASE"
                    " LIMIT ?",
                    (ed, query.strip(), need),
                ).fetchall())
                if len(all_results) >= k:
                    conn.close()
                    break
                need = k - len(all_results)

                # Tier 0b: the rule's NAME appears somewhere inside the
                # question. The retriever is handed whole conversational
                # sentences ("How does flanking work for melee attacks?"), so
                # Tier 0's `name = <whole sentence>` never matched and FTS5 then
                # OR-ed common words (how/does/work/for/melee) into unrelated
                # feats - Flanking was returning Quick Reversal and Wolf Stance.
                # Longest names win, so "Persistent Flame" beats "Fire" when
                # both are mentioned.
                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content"
                    " FROM rules WHERE system = ?"
                    "  AND length(name) >= 4"
                    "  AND instr(lower(?), lower(name)) > 0"
                    "  AND source_book != 'Unknown Source'"
                    " ORDER BY length(name) DESC LIMIT ?",
                    (ed, query.strip(), need),
                ).fetchall())
                if len(all_results) >= k:
                    conn.close()
                    break
                need = k - len(all_results)

                # Tier 1: FTS5 rank over known-source rows.
                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content"
                    " FROM rules WHERE system = ? AND rules MATCH ?"
                    " AND source_book != 'Unknown Source'"
                    " ORDER BY rank LIMIT ?",
                    (ed, escaped, need),
                ).fetchall())
                if len(all_results) >= k:
                    conn.close()
                    break
                need = k - len(all_results)

                # Tier 2: FTS5 rank over legacy Unknown Source rows.
                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content"
                    " FROM rules WHERE system = ? AND rules MATCH ?"
                    " AND source_book = 'Unknown Source'"
                    " ORDER BY rank LIMIT ?",
                    (ed, escaped, need),
                ).fetchall())
                conn.close()

            except sqlite3.OperationalError as e:
                logger.warning(f"FTS5 search failed for {ed}: {e}")
                continue

        return all_results[:k]

    async def get_sources(self, query: str, edition: str, k: int = 5) -> list[dict]:
        """Get source citations for a query (for response attribution).

        Prefer `extract_sources_from_context` when the rows have already been
        fetched - see the note there.
        """
        results = await self.retrieve(query, edition, k)
        return self.extract_sources_from_context(results)

    @staticmethod
    def extract_sources_from_context(context: list[dict] | None) -> list[dict]:
        """Project citation fields out of already-retrieved rows. No DB access.

        `query()` and `get_sources()` used to run the *same* FTS5 search twice
        per request - once to build the RAG prompt and again to attach
        citations. retriever.py's own measurement puts a single FTS5 query on
        this corpus at roughly 294 ms, so that duplicate was pure latency.
        Citations are a projection of rows we already hold, so derive them here
        instead of re-querying.
        """
        sources: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for row in context or []:
            name = (row.get("name") or "").strip()
            book = (row.get("source_book") or "").strip()
            key = (book.lower(), name.lower())
            if not name or key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "name": name,
                    "source_book": book,
                    "category": row.get("category", ""),
                }
            )
        return sources

    async def search(self, query: str, edition: str = "both", limit: int = 5) -> list[dict]:
        """Public search method for rules endpoint."""
        return await self.retrieve(query, edition, limit)