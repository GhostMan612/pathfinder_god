# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Raw FTS5 Fallback — Direct rule excerpt retrieval (no LLM).
Tier 2 of the fallback chain — always works.
"""

import logging
import sqlite3
from typing import Any

from app.config import get_settings
from app.db.repository import CampaignRepository

logger = logging.getLogger(__name__)


async def search_rules(
    query: str,
    edition: str = "both",
    limit: int = 5,
    repo: CampaignRepository | None = None,
) -> list[dict[str, Any]]:
    """
    Direct FTS5 search — returns raw rule excerpts.
    Used when Ollama is unavailable or as final fallback.
    """
    settings = get_settings()

    # Find available DB
    db_path = None
    for p in settings.db_paths:
        if p.exists():
            db_path = str(p)
            break

    if not db_path:
        logger.error("No rules database found")
        return []

    escaped = query.replace('"', '""')
    # Escape FTS5 special characters
    for ch in ['*', '-', '+', '(', ')', ':', '|', '@', '{', '}', '[', ']', '^', '~']:
        escaped = escaped.replace(ch, f' {ch} ')
    # Remove ? entirely (FTS5 wildcard)
    escaped = escaped.replace('?', '')
    # Collapse multiple spaces
    escaped = ' '.join(escaped.split())
    # Edition order: 2E first, then 1E (for "both") - DB uses uppercase
    edition_map = {"2e": "2E", "1e": "1E"}
    editions = [edition_map.get("2e", "2E"), edition_map.get("1e", "1E")] if edition == "both" else [edition_map.get(edition, edition.upper())]

    all_results = []
    seen: set[str] = set()
    for ed in editions:
        if len(all_results) >= limit:
            break

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

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

            need = limit - len(all_results)
            take(conn.execute(
                "SELECT system, category, name, source_book, raw_content"
                " FROM rules WHERE system = ? AND name = ? COLLATE NOCASE"
                " LIMIT ?",
                (ed, query.strip(), need),
            ).fetchall())
            if len(all_results) < limit:
                need = limit - len(all_results)
                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content"
                    " FROM rules WHERE system = ? AND rules MATCH ?"
                    " AND source_book != 'Unknown Source'"
                    " ORDER BY rank LIMIT ?",
                    (ed, escaped, need),
                ).fetchall())
            if len(all_results) < limit:
                need = limit - len(all_results)
                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content"
                    " FROM rules WHERE system = ? AND rules MATCH ?"
                    " AND source_book = 'Unknown Source'"
                    " ORDER BY rank LIMIT ?",
                    (ed, escaped, need),
                ).fetchall())
            conn.close()

        except sqlite3.OperationalError as e:
            logger.warning(f"FTS5 fallback search failed for {ed}: {e}")
            continue

    return all_results[:limit]


async def format_raw_excerpts(hits: list[dict], query: str) -> str:
    """Format raw hits into a readable response."""
    if not hits:
        return f"No rules found for '{query}'. Try a different search term."

    lines = [f"Rule excerpts for '{query}':\n"]
    for i, hit in enumerate(hits, 1):
        lines.append(
            f"{i}. **{hit['name']}** ({hit.get('system', '?')}) — {hit.get('source_book', 'Unknown')}\n"
            f"   {hit['content'][:300]}..."
        )
    return "\n".join(lines)