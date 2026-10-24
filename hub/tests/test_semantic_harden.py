# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

import app.config
from app.config import Settings
from app.db.repository import CampaignRepository
from app.rag.retriever import Retriever
from app.rag.semantic_spine import (
    SemanticStore,
    hybrid_search,
    normalize_vector,
    run_comparative_benchmark,
)


class HardenFakeEmbedder:
    dimensions = 128

    def __init__(self, model_name: str = "embeddinggemma-2:270m", explode: bool = False) -> None:
        self.model_name = model_name
        self.explode = explode

    def identity(self) -> str:
        return f"ollama:{self.model_name}@fakehardenidentity12345678901234567890:d128:q'':p''"

    def embed(self, texts: list[str], *, query: bool = False) -> list[tuple[float, ...]]:
        if self.explode:
            raise TimeoutError("Simulated Ollama timeout in test")
        output = []
        for text in texts:
            values = [0.0] * self.dimensions
            for term in text.casefold().split():
                pos = int(hashlib.sha256(term.encode("utf-8")).hexdigest()[:8], 16) % self.dimensions
                values[pos] += 1.0
            output.append(normalize_vector(values, self.dimensions))
        return output


def _apply_settings(monkeypatch, custom_settings: Settings) -> None:
    monkeypatch.setattr(app.config, "get_settings", lambda: custom_settings)
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("app.") and getattr(mod, "get_settings", None) is not None:
            monkeypatch.setattr(mod, "get_settings", lambda: custom_settings)


@pytest.fixture
def harden_env(tmp_path):
    source_db = tmp_path / "pathfinder_rag.db"
    index_db = tmp_path / "semantic_rules.sqlite3"
    with closing(sqlite3.connect(source_db)) as conn:
        conn.execute("DROP TABLE IF EXISTS rules")
        conn.execute("CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)")
        conn.executemany(
            "INSERT INTO rules (system, category, name, source_book, raw_content) VALUES (?,?,?,?,?)",
            [
                ("2E", "action", "Flanking", "Player Core", "Opposite sides ally melee off-guard."),
                ("1E", "combat", "Flanking", "Core Rulebook 1E", "Flanking attack bonus."),
                ("2E", "feat", "Power Attack", "Player Core", "Extra damage with accuracy penalty."),
                ("2E", "spell", "Fireball", "Player Core", "Explosive fire burst."),
                ("2E", "action", "Aid", "Unknown Source", "Assist ally check."),
            ],
        )
        conn.commit()

    store = SemanticStore(index_db, source_db)
    embedder = HardenFakeEmbedder()
    store.build(embedder)

    custom_settings = Settings(
        data_dir=tmp_path,
        semantic_enabled=False,
        semantic_model="embeddinggemma-2:270m",
        semantic_dimensions=128,
        semantic_index_path=index_db,
    )
    repo = CampaignRepository(tmp_path / "campaign.db")
    return {
        "tmp_path": tmp_path,
        "source_db": source_db,
        "index_db": index_db,
        "settings": custom_settings,
        "repo": repo,
        "embedder": embedder,
        "store": store,
    }


def test_corrupt_index_detected_as_corrupt_or_unreadable(harden_env):
    index_db = harden_env["index_db"]
    index_db.write_bytes(b"NOT A REAL SQLITE FILE RANDOM BYTES HERE")
    store = SemanticStore(index_db, harden_env["source_db"])
    status = store.status()
    assert status["state"] in ("corrupt", "unreadable")


@pytest.mark.asyncio
async def test_adapter_fallback_on_corrupt_index(harden_env, monkeypatch):
    test_settings = harden_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    index_db = harden_env["index_db"]
    index_db.write_bytes(b"CORRUPT DATA")

    lexical_rows = [{"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "Text"}]
    res = await hybrid_search(
        "flanking",
        "2e",
        2,
        lexical_rows,
        source_path=harden_env["source_db"],
        embedder=harden_env["embedder"],
    )
    assert res == lexical_rows


@pytest.mark.asyncio
async def test_adapter_provider_timeout_fallback(harden_env, monkeypatch):
    test_settings = harden_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    exploding_embedder = HardenFakeEmbedder(explode=True)
    lexical_rows = [{"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "Text"}]
    res = await hybrid_search(
        "flanking",
        "2e",
        2,
        lexical_rows,
        source_path=harden_env["source_db"],
        embedder=exploding_embedder,
    )
    assert res == lexical_rows


def test_source_db_immutability_during_build(tmp_path):
    source_db = tmp_path / "immut_source.db"
    index_db = tmp_path / "immut_index.sqlite3"
    with closing(sqlite3.connect(source_db)) as conn:
        conn.execute("CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)")
        conn.execute("INSERT INTO rules VALUES ('2E','action','Test','Book','Content')")
        conn.commit()

    source_hash_before = hashlib.sha256(source_db.read_bytes()).hexdigest()
    store = SemanticStore(index_db, source_db)
    store.build(HardenFakeEmbedder())
    source_hash_after = hashlib.sha256(source_db.read_bytes()).hexdigest()

    assert source_hash_before == source_hash_after


def test_concurrent_search_thread_safety(harden_env):
    store = harden_env["store"]
    embedder = harden_env["embedder"]

    def do_search(q: str):
        return store.search(q, "2e", embedder, limit=3)

    queries = ["Flanking", "Power Attack", "Fireball", "Aid", "Opposite sides ally"] * 6
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(do_search, queries))

    assert len(results) == len(queries)
    assert all(isinstance(r, list) for r in results)


def test_comparative_benchmark_golden_execution(tmp_path):
    report = run_comparative_benchmark(HardenFakeEmbedder(), target_dir=tmp_path)
    assert report["state"] == "evaluation-ok"
    assert report["records"] == 10
    assert report["cases_count"] >= 20
    assert report["hybrid_retriever"]["exact_retention"] == 1.0
    assert report["hybrid_retriever"]["edition_isolation"] == 1.0
    assert report["hybrid_retriever"]["abstention_safety"] == 1.0
    assert report["delta"]["exact_retention_preserved"] is True
    assert report["delta"]["edition_isolation_preserved"] is True
    assert report["delta"]["abstention_safety_preserved"] is True


@pytest.mark.asyncio
async def test_no_sensitive_query_data_in_warnings(harden_env, monkeypatch, caplog):
    test_settings = harden_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    exploding_embedder = HardenFakeEmbedder(explode=True)
    secret_query = "OPERATOR_SECRET_PHRASE_NEVER_LOG"
    lexical = [{"system": "2E", "category": "action", "name": "Rule", "source_book": "Book", "content": "Text"}]

    with caplog.at_level(logging.WARNING):
        res = await hybrid_search(
            secret_query,
            "2e",
            2,
            lexical,
            source_path=harden_env["source_db"],
            embedder=exploding_embedder,
        )

    assert res == lexical
    for record in caplog.records:
        assert secret_query not in record.message


@pytest.mark.asyncio
async def test_clean_reversibility_when_switch_off(harden_env, monkeypatch):
    test_settings = harden_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = False
    _apply_settings(monkeypatch, test_settings)

    retriever = Retriever(harden_env["repo"])
    lexical = await retriever._fts5_search("flanking", edition="2e", k=2)
    hybrid = await retriever.query("flanking", edition="2e", k=2)

    assert lexical == hybrid


def test_index_build_preserves_backup_on_replacement(tmp_path):
    source_db = tmp_path / "source_backup.db"
    index_db = tmp_path / "index_backup.sqlite3"
    with closing(sqlite3.connect(source_db)) as conn:
        conn.execute("CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)")
        conn.execute("INSERT INTO rules VALUES ('2E','action','Rule1','Book','Text 1')")
        conn.commit()

    store = SemanticStore(index_db, source_db)
    embedder = HardenFakeEmbedder()
    res1 = store.build(embedder)
    assert res1["state"] == "ready"
    assert index_db.is_file()

    with closing(sqlite3.connect(source_db)) as conn:
        conn.execute("INSERT INTO rules VALUES ('2E','action','Rule2','Book','Text 2')")
        conn.commit()

    res2 = store.build(embedder)
    assert res2["state"] == "ready"
    backup_path = Path(str(index_db) + ".bak")
    assert backup_path.is_file()
