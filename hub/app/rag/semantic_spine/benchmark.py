# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

from .store import Embedder, SemanticStore


class BenchmarkCase(NamedTuple):
    query: str
    edition: str
    expected_rule: str
    is_exact: bool


SYNTHETIC_BENCHMARK_CORPUS: list[tuple[str, str, str, str, str]] = [
    ("2E", "action", "Flanking", "Player Core", "When you and an ally are on opposite sides of a foe, that foe is off-guard to your melee attacks."),
    ("1E", "combat", "Flanking", "Core Rulebook 1E", "When a creature makes a melee attack on an opponent flanked by an ally, it gains a +2 flanking bonus."),
    ("2E", "feat", "Power Attack", "Player Core", "Make a melee Strike dealing an extra die of damage with an accuracy penalty."),
    ("1E", "feat", "Power Attack", "Core Rulebook 1E", "Take a penalty on all melee attack rolls to add a bonus to all melee damage rolls."),
    ("2E", "skill", "Athletics", "Player Core", "Perform athletic physical maneuvers like Grapple, Shove, Trip, and Disarm."),
    ("2E", "spell", "Fireball", "Player Core", "A roaring sphere of fire detonates and deals 6d6 fire damage in a 20-foot burst."),
    ("1E", "spell", "Fireball", "Core Rulebook 1E", "A blast of fire deals 1d6 fire damage per caster level up to 10d6 in a 20-foot radius spread."),
    ("2E", "action", "Aid", "Unknown Source", "Prepare to assist an ally with an upcoming skill check or attack roll."),
    ("2E", "action", "Take Cover", "Player Core", "Press yourself against a wall or obstacle to gain standard or greater cover defenses."),
    ("2E", "condition", "Off-Guard", "Player Core", "A condition making the creature take a -2 circumstance penalty to Armor Class."),
]

SYNTHETIC_BENCHMARK_QUERIES: list[BenchmarkCase] = [
    BenchmarkCase(query="Flanking", edition="2e", expected_rule="Flanking", is_exact=True),
    BenchmarkCase(query="Power Attack", edition="2e", expected_rule="Power Attack", is_exact=True),
    BenchmarkCase(query="Fireball", edition="1e", expected_rule="Fireball", is_exact=True),
    BenchmarkCase(query="Athletics", edition="2e", expected_rule="Athletics", is_exact=True),
    BenchmarkCase(query="Take Cover", edition="2e", expected_rule="Take Cover", is_exact=True),
    BenchmarkCase(query="allies on opposite sides melee advantage", edition="2e", expected_rule="Flanking", is_exact=False),
    BenchmarkCase(query="bonus weapon damage at cost of attack accuracy", edition="2e", expected_rule="Power Attack", is_exact=False),
    BenchmarkCase(query="burst of explosive flames radius", edition="1e", expected_rule="Fireball", is_exact=False),
    BenchmarkCase(query="trip shove grapple skill maneuver", edition="2e", expected_rule="Athletics", is_exact=False),
    BenchmarkCase(query="penalty to armor class circumstance defense", edition="2e", expected_rule="Off-Guard", is_exact=False),
]


def populate_benchmark_corpus(database_path: Path) -> None:
    with closing(sqlite3.connect(database_path)) as conn:
        conn.execute("CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)")
        conn.executemany(
            "INSERT INTO rules (system, category, name, source_book, raw_content) VALUES (?,?,?,?,?)",
            SYNTHETIC_BENCHMARK_CORPUS,
        )
        conn.commit()


def run_synthetic_benchmark(embedder: Embedder, target_dir: Path | None = None) -> dict[str, object]:
    if target_dir is None:
        temp_obj = tempfile.TemporaryDirectory(prefix="pf_semantic_bench_")
        work_dir = Path(temp_obj.name)
    else:
        temp_obj = None
        work_dir = Path(target_dir)

    try:
        source_db = work_dir / "bench_rules.db"
        index_db = work_dir / "bench_semantic.sqlite3"
        populate_benchmark_corpus(source_db)
        store = SemanticStore(index_db, source_db)

        start_build = time.perf_counter()
        build_result = store.build(embedder, batch_size=4)
        build_time_ms = (time.perf_counter() - start_build) * 1000.0

        latencies_ms: list[float] = []
        hits_at_5 = 0
        exact_retention_hits = 0
        exact_query_count = sum(1 for c in SYNTHETIC_BENCHMARK_QUERIES if c.is_exact)

        for case in SYNTHETIC_BENCHMARK_QUERIES:
            t0 = time.perf_counter()
            ranked = store.search(case.query, case.edition, embedder, limit=5)
            elapsed = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(elapsed)

            names = [r.record.name for r in ranked]
            if case.expected_rule in names:
                hits_at_5 += 1
            if case.is_exact and names and names[0].casefold() == case.expected_rule.casefold():
                exact_retention_hits += 1

        latencies_ms.sort()
        n = len(latencies_ms)
        p50 = latencies_ms[int(n * 0.50)] if n else 0.0
        p95 = latencies_ms[min(int(n * 0.95), n - 1)] if n else 0.0

        recall_at_5 = hits_at_5 / len(SYNTHETIC_BENCHMARK_QUERIES) if SYNTHETIC_BENCHMARK_QUERIES else 0.0
        exact_retention = exact_retention_hits / exact_query_count if exact_query_count else 0.0
        index_size_bytes = index_db.stat().st_size if index_db.exists() else 0

        return {
            "state": "benchmark-ok",
            "model_digest": embedder.identity(),
            "dimensions": embedder.dimensions,
            "corpus_stamp": build_result.get("source_stamp", ""),
            "records": int(build_result.get("rows", "0")),
            "build_time_ms": round(build_time_ms, 2),
            "index_disk_bytes": index_size_bytes,
            "query_p50_ms": round(p50, 2),
            "query_p95_ms": round(p95, 2),
            "recall_at_5": round(recall_at_5, 4),
            "exact_retention": round(exact_retention, 4),
        }
    finally:
        if temp_obj is not None:
            temp_obj.cleanup()
