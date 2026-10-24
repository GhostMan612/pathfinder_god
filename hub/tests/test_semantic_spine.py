# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest

from app.rag.semantic_spine import (
    OllamaEmbedder,
    RankedRule,
    RuleRecord,
    SemanticSpineError,
    SemanticStore,
    normalize_vector,
    reciprocal_rank_fusion,
)


class FakeEmbedder:
    dimensions = 128

    def __init__(self, version: str = "mock-v1", fail_after: int = -1) -> None:
        self.version = version
        self.fail_after = fail_after
        self.calls = 0

    def identity(self) -> str:
        return self.version

    def embed(self, texts: list[str], *, query: bool = False) -> list[tuple[float, ...]]:
        self.calls += 1
        if self.fail_after > 0 and self.calls >= self.fail_after:
            raise SemanticSpineError("Synthetic provider failure")
        output = []
        for text in texts:
            values = [0.0] * self.dimensions
            for term in text.casefold().split():
                position = int(hashlib.sha256(term.encode("utf-8")).hexdigest()[:8], 16) % self.dimensions
                values[position] += 1.0
            output.append(normalize_vector(values, self.dimensions))
        return output


@pytest.fixture
def standalone_store(tmp_path):
    db = tmp_path / "rules.db"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)")
        conn.executemany(
            "INSERT INTO rules(system,category,name,source_book,raw_content) VALUES(?,?,?,?,?)",
            [
                ("2E", "action", "Flanking", "Player Core", "Off guard melee ally opposite side."),
                ("1E", "combat", "Flanking", "Core Rulebook 1E", "Flanking improves attack bonus."),
                ("2E", "skill", "Athletics", "Player Core", "Grapple trip disarm athletics."),
                ("2E", "action", "Aid", "Unknown Source", "Assist another skill check."),
            ],
        )
        conn.commit()
    return SemanticStore(tmp_path / "semantic.sqlite3", db)


def test_complete_spine_index_does_not_mutate_primary_rules(standalone_store):
    source_bytes = standalone_store.source_path.read_bytes()
    result = standalone_store.build(FakeEmbedder(), batch_size=2)
    assert result["state"] == "ready"
    assert result["rows"] == "4"
    assert standalone_store.status()["state"] == "ready"
    assert standalone_store.source_path.read_bytes() == source_bytes
    assert standalone_store.index_path.is_file()


def test_search_preserves_edition_and_source(standalone_store):
    embedder = FakeEmbedder()
    standalone_store.build(embedder)
    hits = standalone_store.search("flanking", "2e", embedder, limit=3)
    assert hits
    assert hits[0].record.system == "2E"
    assert all(hit.record.source_book for hit in hits)
    assert all(len(hit.record.public_hit()) == 5 for hit in hits)


def test_other_edition_only_fills_remaining_slots(standalone_store):
    embedder = FakeEmbedder()
    standalone_store.build(embedder)
    hits = standalone_store.search("attack", "1e", embedder, limit=3)
    assert hits[0].record.system == "1E"
    assert len(hits) == 3


def test_source_change_invalidates_index(standalone_store):
    embedder = FakeEmbedder()
    standalone_store.build(embedder)
    with closing(sqlite3.connect(standalone_store.source_path)) as conn:
        conn.execute("INSERT INTO rules VALUES(?,?,?,?,?)", ("2E", "action", "Grab", "Player Core", "New record"))
        conn.commit()
    assert standalone_store.status()["state"] == "stale"
    with pytest.raises(SemanticSpineError, match="not ready"):
        standalone_store.search("grab", "2e", embedder)


def test_model_change_fails_closed(standalone_store):
    standalone_store.build(FakeEmbedder())
    with pytest.raises(SemanticSpineError, match="model or dimensions changed"):
        standalone_store.search("grapple", "both", FakeEmbedder("mock-v2"))


def test_atomic_failure_does_not_replace_previous_complete_index(standalone_store):
    standalone_store.build(FakeEmbedder())
    before = standalone_store.index_path.read_bytes()
    with pytest.raises(SemanticSpineError, match="Synthetic provider failure"):
        standalone_store.build(FakeEmbedder(fail_after=2), batch_size=1)
    assert standalone_store.index_path.read_bytes() == before
    assert standalone_store.status()["state"] == "ready"


def test_unavailable_index_is_not_silent_success(standalone_store):
    assert standalone_store.status()["state"] == "absent"
    with pytest.raises(SemanticSpineError, match="not ready"):
        standalone_store.search("flanking", "both", FakeEmbedder())


def test_invalid_vectors_are_rejected():
    with pytest.raises(SemanticSpineError, match="zero magnitude"):
        normalize_vector([0] * 128, 128)
    with pytest.raises(SemanticSpineError, match="shorter"):
        normalize_vector([1] * 100, 128)
    with pytest.raises(SemanticSpineError, match="non-finite"):
        normalize_vector([float("nan")] + [0] * 127, 128)


def test_rank_fusion_protects_exact_rule_name():
    exact = {"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "Rule text"}
    other = RuleRecord("2E", "feat", "Related Feat", "Player Core", "Similar text")
    results = reciprocal_rank_fusion("flanking", [exact], [RankedRule(other, 1.0)], 2)
    assert [hit["name"] for hit in results] == ["Flanking", "Related Feat"]
    assert len(results[0]) == 5


def test_rank_fusion_preserves_distinct_editions():
    a = {"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "A"}
    b = RuleRecord("1E", "combat", "Flanking", "Core Rulebook 1E", "B")
    results = reciprocal_rank_fusion("flanking", [a], [RankedRule(b, 0.9)], 3)
    assert len(results) == 2
    assert {hit["system"] for hit in results} == {"1E", "2E"}


def test_ollama_embedder_rejects_non_loopback_endpoint():
    with pytest.raises(SemanticSpineError, match="loopback"):
        OllamaEmbedder("http://example.com:11434")
    with pytest.raises(SemanticSpineError, match="dimensions"):
        OllamaEmbedder(dimensions=99)


def test_ollama_embedder_absent_model_raises(monkeypatch):
    embedder = OllamaEmbedder(model="embeddinggemma-2:270m")
    monkeypatch.setattr(embedder, "_request", lambda path, data=None: {"models": [{"name": "qwen2.5:3b", "digest": "a" * 64}]})
    with pytest.raises(SemanticSpineError, match="not installed locally"):
        embedder.identity()


def test_ollama_embedder_malformed_tags_raises(monkeypatch):
    embedder = OllamaEmbedder(model="embeddinggemma-2:270m")
    monkeypatch.setattr(embedder, "_request", lambda path, data=None: {"models": "invalid"})
    with pytest.raises(SemanticSpineError, match="Malformed"):
        embedder.identity()


def test_ollama_embedder_malformed_embed_raises(monkeypatch):
    embedder = OllamaEmbedder(model="embeddinggemma-2:270m")
    monkeypatch.setattr(embedder, "_request", lambda path, data=None: {"embeddings": "invalid"})
    with pytest.raises(SemanticSpineError, match="unexpected"):
        embedder.embed(["hello world"])


def test_ollama_embedder_batch_count_mismatch_raises(monkeypatch):
    embedder = OllamaEmbedder(model="embeddinggemma-2:270m", dimensions=256)
    monkeypatch.setattr(embedder, "_request", lambda path, data=None: {"embeddings": [[1.0] * 256]})
    with pytest.raises(SemanticSpineError, match="unexpected"):
        embedder.embed(["first", "second"])


def test_ollama_embedder_dimension_mismatch_raises(monkeypatch):
    embedder = OllamaEmbedder(model="embeddinggemma-2:270m", dimensions=256)
    monkeypatch.setattr(embedder, "_request", lambda path, data=None: {"embeddings": [[1.0] * 64]})
    with pytest.raises(SemanticSpineError, match="shorter"):
        embedder.embed(["test query"])


def test_over_context_budget_record_fails_publication(tmp_path):
    source_db = tmp_path / "large_rules.db"
    with closing(sqlite3.connect(source_db)) as conn:
        conn.execute("CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)")
        conn.execute(
            "INSERT INTO rules (system, category, name, source_book, raw_content) VALUES (?,?,?,?,?)",
            ("2E", "action", "HugeRule", "Player Core", "word " * 3000),
        )
        conn.commit()
    store = SemanticStore(tmp_path / "large_semantic.sqlite3", source_db)
    with pytest.raises(SemanticSpineError, match="context budget"):
        store.build(FakeEmbedder())


def test_repeated_build_creates_backup_and_succeeds(standalone_store):
    embedder = FakeEmbedder()
    first = standalone_store.build(embedder)
    assert first["state"] == "ready"
    assert standalone_store.index_path.is_file()

    second = standalone_store.build(embedder)
    assert second["state"] == "ready"
    backup = Path(str(standalone_store.index_path) + ".bak")
    assert backup.is_file()


def test_concurrent_thread_boundary_search(standalone_store):
    embedder = FakeEmbedder()
    standalone_store.build(embedder)

    def do_search(q: str):
        return standalone_store.search(q, "both", embedder, limit=2)

    queries = ["flanking", "athletics", "aid", "attack", "flanking"] * 3
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(do_search, queries))

    assert len(results) == len(queries)
    for res in results:
        assert isinstance(res, list)
        assert len(res) > 0
