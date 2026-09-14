# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for retrieval, edition fallback, and shape detection."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.rag.search import Retriever, normalize_edition


def _retriever(data_dir: Path) -> Retriever:
    return Retriever([data_dir / "pathfinder_rag.db"], rag_limit=4)


def test_normalize_edition_aliases():
    assert normalize_edition("PF2E") == "2e"
    assert normalize_edition("pathfinder first edition") == "1e"
    assert normalize_edition(None) == "both"
    assert normalize_edition("both") == "both"


def test_search_finds_matching_rule(rules_db_dir: Path):
    hits = _retriever(rules_db_dir).search("fireball", edition="1e")
    assert hits, "expected a hit for fireball"
    assert any("fire" in h.content.lower() for h in hits)


def test_edition_filter_isolates_2e(rules_db_dir: Path):
    hits = _retriever(rules_db_dir).search("power attack feat", edition="2e")
    assert hits
    assert all(h.system == "2e" for h in hits)


def test_edition_fallback_2e_to_1e(rules_db_dir: Path):
    # Fireball only exists as a 1e row here; asking 2e-first must fall back to 1e.
    hits = _retriever(rules_db_dir).search("fireball", edition="2e")
    assert hits
    assert hits[0].system == "1e"


def test_both_prefers_2e_when_present(rules_db_dir: Path):
    # Flanking exists in both editions; "both" should surface 2e first.
    hits = _retriever(rules_db_dir).search("flanking", edition="both")
    assert hits
    assert hits[0].system == "2e"


def test_build_context_has_no_hit_message(rules_db_dir: Path):
    ctx = _retriever(rules_db_dir).build_context("xyzzy nonexistent thing", edition="2e")
    assert "No local Pathfinder rule hit" in ctx


def test_missing_db_degrades_gracefully(tmp_path: Path):
    # Point at a non-existent DB — should return [] rather than raise.
    r = Retriever([tmp_path / "nope.db"])
    assert r.search("anything") == []


def test_generic_chunks_shape(tmp_path: Path):
    # A DB using the alternate `chunks(source, content)` FTS shape.
    db = tmp_path / "pathfinder_god.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE VIRTUAL TABLE chunks USING fts5(source, content)")
    conn.execute("INSERT INTO chunks VALUES ('Bestiary', 'The dragon breathes acid across the cavern.')")
    conn.commit()
    conn.close()

    hits = Retriever([db]).search("dragon acid", edition="both")
    assert hits
    assert "dragon" in hits[0].content.lower()
