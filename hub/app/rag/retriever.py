# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
RAG Retriever — Hybrid vector + FTS5 search for rule context.
"""

import logging
import sqlite3
from typing import Any

from app.config import get_settings
from app.db.repository import CampaignRepository

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

    async def query(self, query: str, edition: str = "both", k: int = 5) -> list[dict]:
        """Hybrid search: FTS5 + vector (if available)."""
        # For now, FTS5 only — vector search can be added with Chroma
        return await self._fts5_search(query, edition, k)

    async def _fts5_search(self, query: str, edition: str, k: int) -> list[dict]:
        db_path = self._get_db_path(edition)

        escaped = query.replace('"', '""')
        for ch in ['*', '-', '+', '(', ')', ':', '|', '@', '{', '}', '[', ']', '^', '~']:
            escaped = escaped.replace(ch, f' {ch} ')
        escaped = escaped.replace('?', '')
        escaped = ' '.join(escaped.split())
        tokens = [t for t in escaped.split() if len(t) > 2]
        if len(tokens) > 1:
            escaped = ' OR '.join(tokens)
        elif tokens:
            escaped = tokens[0]

        # Edition order: 2E first, then 1E (for "both") - DB uses uppercase
        edition_map = {"2e": "2E", "1e": "1E"}
        editions = [edition_map.get("2e", "2E"), edition_map.get("1e", "1E")] if edition == "both" else [edition_map.get(edition, edition.upper())]

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
        """Get source citations for a query (for response attribution)."""
        results = await self._fts5_search(query, edition, k)
        return [
            {
                "name": r["name"],
                "source_book": r.get("source_book", ""),
                "category": r.get("category", ""),
            }
            for r in results
        ]

    async def search(self, query: str, edition: str = "both", limit: int = 5) -> list[dict]:
        """Public search method for rules endpoint."""
        return await self._fts5_search(query, edition, limit)