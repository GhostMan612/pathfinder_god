# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from .adapter import hybrid_search
from .benchmark import run_comparative_benchmark, run_synthetic_benchmark
from .chunker import chunk_rule
from .fusion import reciprocal_rank_fusion
from .model import (
    ChunkRecord,
    RankedRule,
    RuleRecord,
    SemanticSpineError,
    cosine,
    normalize_vector,
)
from .ollama import OllamaEmbedder
from .store import SemanticStore

__all__ = [
    "ChunkRecord",
    "OllamaEmbedder",
    "RankedRule",
    "RuleRecord",
    "SemanticSpineError",
    "SemanticStore",
    "chunk_rule",
    "cosine",
    "hybrid_search",
    "normalize_vector",
    "reciprocal_rank_fusion",
    "run_comparative_benchmark",
    "run_synthetic_benchmark",
]
