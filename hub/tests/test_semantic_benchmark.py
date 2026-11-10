# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing

from app.rag.semantic_spine import normalize_vector, run_synthetic_benchmark
from app.rag.semantic_spine.benchmark import populate_benchmark_corpus


class FakeBenchEmbedder:
    dimensions = 128

    def identity(self) -> str:
        return "ollama:embeddinggemma-2:270m@testdigest123456789012345678901234:d128:q'':p''"

    def embed(self, texts: list[str], *, query: bool = False) -> list[tuple[float, ...]]:
        output = []
        for text in texts:
            values = [0.0] * self.dimensions
            for term in text.casefold().split():
                position = int(hashlib.sha256(term.encode("utf-8")).hexdigest()[:8], 16) % self.dimensions
                values[position] += 1.0
            output.append(normalize_vector(values, self.dimensions))
        return output


def test_run_synthetic_benchmark_metrics(tmp_path):
    report = run_synthetic_benchmark(FakeBenchEmbedder(), target_dir=tmp_path)
    assert report["state"] == "benchmark-ok"
    assert report["model_digest"].startswith("ollama:embeddinggemma-2:270m@")
    assert report["dimensions"] == 128
    assert report["records"] == 10
    assert report["index_disk_bytes"] > 0
    assert report["build_time_ms"] >= 0.0
    assert report["query_p50_ms"] >= 0.0
    assert report["query_p95_ms"] >= 0.0
    assert report["recall_at_5"] > 0.0
    assert report["exact_retention"] == 1.0


def test_populate_benchmark_corpus_creates_fts5_table(tmp_path):
    db_path = tmp_path / "test_corpus.db"
    populate_benchmark_corpus(db_path)
    assert db_path.is_file()
    with closing(sqlite3.connect(db_path)) as conn:
        count = conn.execute("SELECT count(*) FROM rules").fetchone()[0]
        assert count == 10
