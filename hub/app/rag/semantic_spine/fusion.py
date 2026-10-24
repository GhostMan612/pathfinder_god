# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

from .model import RankedRule, RuleRecord


def _key(hit: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        str(hit.get("system", "")).upper(),
        str(hit.get("category", "")).casefold(),
        str(hit.get("name", "")).casefold(),
        str(hit.get("source_book", "")).casefold(),
    )


def reciprocal_rank_fusion(
    query: str,
    lexical: list[dict[str, str]],
    semantic: list[RankedRule],
    limit: int,
    *,
    lexical_weight: float = 1.0,
    semantic_weight: float = 0.8,
    rrf_k: int = 60,
) -> list[dict[str, str]]:
    if limit < 1:
        return []
    anchors = []
    scores: dict[tuple[str, str, str, str], float] = {}
    hits: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for rank, hit in enumerate(lexical, 1):
        key = _key(hit)
        hits.setdefault(key, hit)
        scores[key] = scores.get(key, 0.0) + lexical_weight / (rrf_k + rank)
        if hit.get("name", "").strip().casefold() == query.strip().casefold() and key not in anchors:
            anchors.append(key)
    for rank, item in enumerate(semantic, 1):
        hit = item.record.public_hit()
        key = _key(hit)
        hits.setdefault(key, hit)
        scores[key] = scores.get(key, 0.0) + semantic_weight / (rrf_k + rank)
    ordered_anchors = sorted(anchors, key=lambda key: (-scores[key], key))
    remainder = [key for key in hits if key not in anchors]
    remainder.sort(key=lambda key: (-scores[key], str(hits[key].get("source_book", "")).casefold() == "unknown source", key))
    return [hits[key] for key in (ordered_anchors + remainder)[:limit]]
