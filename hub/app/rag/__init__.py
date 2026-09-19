# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Retrieval-augmented generation over the local Pathfinder rules databases."""

from .search import Retriever, RuleHit, normalize_edition

__all__ = ["Retriever", "RuleHit", "normalize_edition"]
