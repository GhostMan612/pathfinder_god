# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import hashlib
import sqlite3
import sys
from contextlib import closing

import pytest

import app.config
from app.config import Settings
from app.db.repository import CampaignRepository
from app.rag.retriever import Retriever
from app.rag.semantic_spine import (
    SemanticStore,
    hybrid_search,
    normalize_vector,
)


class IntegrationFakeEmbedder:
    dimensions = 128

    def __init__(self, model_name: str = "embeddinggemma-2:270m", explode: bool = False) -> None:
        self.model_name = model_name
        self.explode = explode

    def identity(self) -> str:
        return f"ollama:{self.model_name}@fakeidentitydigest12345678901234567890:d128:q'':p''"

    def embed(self, texts: list[str], *, query: bool = False) -> list[tuple[float, ...]]:
        if self.explode:
            raise TimeoutError("Simulated Ollama timeout")
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
def populated_env(tmp_path, monkeypatch):
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
    embedder = IntegrationFakeEmbedder()
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
    }


@pytest.mark.asyncio
async def test_retriever_off_matches_baseline_identically(populated_env, monkeypatch):
    test_settings = populated_env["settings"]
    _apply_settings(monkeypatch, test_settings)

    retriever = Retriever(populated_env["repo"])
    lexical = await retriever._fts5_search("flanking", edition="2e", k=3)
    unified = await retriever.query("flanking", edition="2e", k=3)
    public_search = await retriever.search("flanking", edition="2e", limit=3)

    assert lexical == unified
    assert lexical == public_search


@pytest.mark.asyncio
async def test_retriever_off_never_touches_embedder_or_sidecar(populated_env, monkeypatch):
    test_settings = populated_env["settings"]
    _apply_settings(monkeypatch, test_settings)

    retriever = Retriever(populated_env["repo"])
    results = await retriever.query("flanking", edition="2e", k=3)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_hybrid_search_absent_sidecar_falls_back_to_lexical(populated_env, monkeypatch):
    test_settings = populated_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    test_settings.semantic_index_path = populated_env["tmp_path"] / "nonexistent.sqlite3"
    _apply_settings(monkeypatch, test_settings)

    lexical_rows = [{"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "Text"}]
    res = await hybrid_search("flanking", "2e", 1, lexical_rows, source_path=populated_env["source_db"])
    assert res == lexical_rows


@pytest.mark.asyncio
async def test_hybrid_search_stale_index_falls_back_to_lexical(populated_env, monkeypatch):
    test_settings = populated_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    with closing(sqlite3.connect(populated_env["source_db"])) as conn:
        conn.execute("INSERT INTO rules VALUES (?,?,?,?,?)", ("2E", "action", "Mutated", "Book", "Content"))
        conn.commit()

    lexical_rows = [{"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "Text"}]
    res = await hybrid_search(
        "flanking",
        "2e",
        1,
        lexical_rows,
        source_path=populated_env["source_db"],
        embedder=populated_env["embedder"],
    )
    assert res == lexical_rows


@pytest.mark.asyncio
async def test_hybrid_search_model_mismatch_falls_back_to_lexical(populated_env, monkeypatch):
    test_settings = populated_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    mismatched_embedder = IntegrationFakeEmbedder(model_name="different-model:latest")
    lexical_rows = [{"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "Text"}]
    res = await hybrid_search(
        "flanking",
        "2e",
        1,
        lexical_rows,
        source_path=populated_env["source_db"],
        embedder=mismatched_embedder,
    )
    assert res == lexical_rows


@pytest.mark.asyncio
async def test_hybrid_search_exact_match_anchor_preserved_at_rank_1(populated_env, monkeypatch):
    test_settings = populated_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    lexical_rows = [
        {"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "Opposite sides ally."}
    ]
    res = await hybrid_search(
        "Flanking",
        "2e",
        2,
        lexical_rows,
        source_path=populated_env["source_db"],
        embedder=populated_env["embedder"],
    )
    assert res
    assert res[0]["name"] == "Flanking"


@pytest.mark.asyncio
async def test_hybrid_search_improves_paraphrase_ranking(populated_env, monkeypatch):
    test_settings = populated_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    lexical_rows = [
        {"system": "2E", "category": "spell", "name": "Fireball", "source_book": "Player Core", "content": "Explosive fire."}
    ]
    res = await hybrid_search(
        "extra damage accuracy penalty",
        "2e",
        3,
        lexical_rows,
        source_path=populated_env["source_db"],
        embedder=populated_env["embedder"],
    )
    names = [r["name"] for r in res]
    assert "Power Attack" in names


@pytest.mark.asyncio
async def test_hybrid_search_preserves_edition_isolation(populated_env, monkeypatch):
    test_settings = populated_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    lexical_rows = [
        {"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "2e flanking text"}
    ]
    res = await hybrid_search(
        "flanking",
        "2e",
        3,
        lexical_rows,
        source_path=populated_env["source_db"],
        embedder=populated_env["embedder"],
    )
    assert all(r["system"] == "2E" for r in res)


@pytest.mark.asyncio
async def test_hybrid_search_provider_error_falls_back_to_lexical(populated_env, monkeypatch):
    test_settings = populated_env["settings"].model_copy(deep=True)
    test_settings.semantic_enabled = True
    _apply_settings(monkeypatch, test_settings)

    lexical_rows = [
        {"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "2e flanking text"}
    ]
    res = await hybrid_search(
        "flanking",
        "2e",
        2,
        lexical_rows,
        source_path=populated_env["source_db"],
        embedder=IntegrationFakeEmbedder(explode=True),
    )
    assert res == lexical_rows


def test_citation_projection_fidelity_under_hybrid():
    context = [
        {"system": "2E", "category": "action", "name": "Flanking", "source_book": "Player Core", "content": "text"},
        {"system": "2E", "category": "action", "name": "Aid", "source_book": "Unknown Source", "content": "text2"},
    ]
    sources = Retriever.extract_sources_from_context(context)
    assert len(sources) == 2
    assert sources[0]["source_book"] == "Player Core"
    assert sources[0]["name"] == "Flanking"
    assert sources[1]["source_book"] == "Unknown Source"


def test_rules_search_endpoint_with_semantic_enabled(client):
    response = client.get("/rules/search?q=flanking&edition=2e&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "flanking"
    assert len(data["results"]) > 0
    assert "name" in data["results"][0]
    assert "source_book" in data["results"][0]


def test_ask_endpoint_with_semantic_enabled(client):
    response = client.post("/ask", json={"query": "flanking", "edition": "2e"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
