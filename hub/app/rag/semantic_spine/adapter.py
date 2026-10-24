# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import logging
from pathlib import Path

import anyio

import app.config
from .fusion import reciprocal_rank_fusion
from .ollama import OllamaEmbedder
from .store import Embedder, RankedRule, SemanticStore

logger = logging.getLogger(__name__)


def _sync_search(
    query: str,
    edition: str,
    limit: int,
    store: SemanticStore,
    embedder: Embedder,
) -> list[RankedRule]:
    return store.search(query, edition, embedder, limit=limit)


async def hybrid_search(
    query: str,
    edition: str,
    k: int,
    lexical_rows: list[dict],
    source_path: Path | None = None,
    embedder: Embedder | None = None,
) -> list[dict]:
    settings = app.config.get_settings()
    if not settings.semantic_enabled:
        return lexical_rows

    if not query.strip() or k <= 0:
        return lexical_rows

    bounded_query = query.strip()[:200]
    candidate_limit = min(max(k * 2, settings.semantic_candidates), 100)
    index_path = settings.semantic_index_path
    if not index_path.is_file():
        logger.warning("Semantic sidecar index is absent, using lexical fallback")
        return lexical_rows

    resolved_source = source_path or next((p for p in settings.db_paths if p.exists()), settings.db_paths[0])
    if not resolved_source.is_file():
        logger.warning("Rules database source is unavailable, using lexical fallback")
        return lexical_rows

    try:
        store = SemanticStore(index_path, resolved_source)
        status = store.status()
        if status.get("state") != "ready":
            logger.warning("Semantic sidecar not ready (%s), using lexical fallback", status.get("state"))
            return lexical_rows

        active_embedder = embedder or OllamaEmbedder(
            endpoint=settings.ollama_host,
            model=settings.semantic_model,
            dimensions=settings.semantic_dimensions,
            timeout_s=getattr(settings, "semantic_timeout_s", 15.0),
        )

        semantic_hits = await anyio.to_thread.run_sync(
            _sync_search,
            bounded_query,
            edition,
            candidate_limit,
            store,
            active_embedder,
        )
        fused = reciprocal_rank_fusion(bounded_query, lexical_rows, semantic_hits, limit=k)
        norm_ed = edition.strip().upper()
        if norm_ed in ("1E", "PF1"):
            fused = [r for r in fused if r.get("system") == "1E"]
        elif norm_ed in ("2E", "PF2"):
            fused = [r for r in fused if r.get("system") == "2E"]
        return fused[:k]
    except Exception as exc:
        logger.warning("Semantic hybrid search failed (%s), using lexical fallback", type(exc).__name__)
        return lexical_rows
