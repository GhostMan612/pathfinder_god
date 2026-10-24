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

from app.rag._fts import build_match_query, editions_for
from .fusion import reciprocal_rank_fusion
from .store import Embedder, SemanticStore


class BenchmarkCase(NamedTuple):
    query: str
    edition: str
    expected_rule: str
    is_exact: bool


class GoldenCase(NamedTuple):
    query: str
    edition: str
    expected_rule: str | None
    case_type: str


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

GOLDEN_EVALUATION_QUERIES: list[GoldenCase] = [
    GoldenCase(query="Flanking", edition="2e", expected_rule="Flanking", case_type="exact"),
    GoldenCase(query="Power Attack", edition="2e", expected_rule="Power Attack", case_type="exact"),
    GoldenCase(query="Fireball", edition="1e", expected_rule="Fireball", case_type="exact"),
    GoldenCase(query="Athletics", edition="2e", expected_rule="Athletics", case_type="exact"),
    GoldenCase(query="Take Cover", edition="2e", expected_rule="Take Cover", case_type="exact"),
    GoldenCase(query="Off-Guard", edition="2e", expected_rule="Off-Guard", case_type="exact"),
    GoldenCase(query="How does flanking work for melee attacks?", edition="2e", expected_rule="Flanking", case_type="conversational"),
    GoldenCase(query="Can I use power attack with a greatsword?", edition="2e", expected_rule="Power Attack", case_type="conversational"),
    GoldenCase(query="What is the damage radius of a fireball spell?", edition="1e", expected_rule="Fireball", case_type="conversational"),
    GoldenCase(query="allies on opposite sides melee advantage", edition="2e", expected_rule="Flanking", case_type="paraphrase"),
    GoldenCase(query="bonus weapon damage at cost of attack accuracy", edition="2e", expected_rule="Power Attack", case_type="paraphrase"),
    GoldenCase(query="burst of explosive flames radius", edition="1e", expected_rule="Fireball", case_type="paraphrase"),
    GoldenCase(query="trip shove grapple skill maneuver", edition="2e", expected_rule="Athletics", case_type="paraphrase"),
    GoldenCase(query="penalty to armor class circumstance defense", edition="2e", expected_rule="Off-Guard", case_type="paraphrase"),
    GoldenCase(query="hiding behind wall protection", edition="2e", expected_rule="Take Cover", case_type="paraphrase"),
    GoldenCase(query="Flanking", edition="1e", expected_rule="Flanking", case_type="edition_conflict"),
    GoldenCase(query="Flanking", edition="2e", expected_rule="Flanking", case_type="edition_conflict"),
    GoldenCase(query="Power Attack", edition="1e", expected_rule="Power Attack", case_type="edition_conflict"),
    GoldenCase(query="Power Attack", edition="2e", expected_rule="Power Attack", case_type="edition_conflict"),
    GoldenCase(query="Fireball", edition="1e", expected_rule="Fireball", case_type="edition_conflict"),
    GoldenCase(query="Fireball", edition="2e", expected_rule="Fireball", case_type="edition_conflict"),
    GoldenCase(query="Cybernetic Arm Enhancement", edition="2e", expected_rule=None, case_type="abstention"),
    GoldenCase(query="Laser Rifle Battery", edition="2e", expected_rule=None, case_type="abstention"),
    GoldenCase(query="Starship Hyperdrive Navigation", edition="1e", expected_rule=None, case_type="abstention"),
]


def populate_benchmark_corpus(database_path: Path) -> None:
    with closing(sqlite3.connect(database_path)) as conn:
        conn.execute("DROP TABLE IF EXISTS rules")
        conn.execute("CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)")
        conn.executemany(
            "INSERT INTO rules (system, category, name, source_book, raw_content) VALUES (?,?,?,?,?)",
            SYNTHETIC_BENCHMARK_CORPUS,
        )
        conn.commit()


def _fts5_baseline_search(db_path: Path, query: str, edition: str, k: int = 5) -> list[dict]:
    escaped = build_match_query(query)
    editions = editions_for(edition)
    all_results: list[dict] = []
    seen: set[str] = set()

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for ed in editions:
            if len(all_results) >= k:
                break
            need = k - len(all_results)

            def take(rows: list) -> None:
                for row in rows:
                    key = (row["name"] or "").strip().lower()
                    if key and key in seen:
                        continue
                    if key:
                        seen.add(key)
                    all_results.append({
                        "system": row["system"],
                        "category": row["category"],
                        "name": row["name"],
                        "source_book": row["source_book"],
                        "content": row["raw_content"],
                    })

            take(conn.execute(
                "SELECT system, category, name, source_book, raw_content "
                "FROM rules WHERE system = ? AND name = ? COLLATE NOCASE LIMIT ?",
                (ed, query.strip(), need),
            ).fetchall())
            if len(all_results) >= k:
                break
            need = k - len(all_results)

            take(conn.execute(
                "SELECT system, category, name, source_book, raw_content "
                "FROM rules WHERE system = ? AND length(name) >= 4 "
                "AND instr(lower(?), lower(name)) > 0 "
                "AND source_book != 'Unknown Source' ORDER BY length(name) DESC LIMIT ?",
                (ed, query.strip(), need),
            ).fetchall())
            if len(all_results) >= k:
                break
            need = k - len(all_results)

            if escaped:
                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content "
                    "FROM rules WHERE system = ? AND rules MATCH ? "
                    "AND source_book != 'Unknown Source' ORDER BY rank LIMIT ?",
                    (ed, escaped, need),
                ).fetchall())
                if len(all_results) >= k:
                    break
                need = k - len(all_results)

                take(conn.execute(
                    "SELECT system, category, name, source_book, raw_content "
                    "FROM rules WHERE system = ? AND rules MATCH ? "
                    "AND source_book = 'Unknown Source' ORDER BY rank LIMIT ?",
                    (ed, escaped, need),
                ).fetchall())

    return all_results[:k]


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


def run_comparative_benchmark(embedder: Embedder, target_dir: Path | None = None) -> dict[str, object]:
    if target_dir is None:
        temp_obj = tempfile.TemporaryDirectory(prefix="pf_comparative_bench_")
        work_dir = Path(temp_obj.name)
    else:
        temp_obj = None
        work_dir = Path(target_dir)

    try:
        source_db = work_dir / "comparative_rules.db"
        index_db = work_dir / "comparative_semantic.sqlite3"
        populate_benchmark_corpus(source_db)
        store = SemanticStore(index_db, source_db)

        start_build = time.perf_counter()
        build_result = store.build(embedder, batch_size=4)
        build_time_ms = (time.perf_counter() - start_build) * 1000.0

        target_cases = [c for c in GOLDEN_EVALUATION_QUERIES if c.expected_rule is not None]
        exact_cases = [c for c in GOLDEN_EVALUATION_QUERIES if c.case_type in ("exact", "edition_conflict")]
        abstention_cases = [c for c in GOLDEN_EVALUATION_QUERIES if c.case_type == "abstention"]

        base_latencies: list[float] = []
        hybrid_latencies: list[float] = []

        base_hits = 0
        hybrid_hits = 0
        base_rr_sum = 0.0
        hybrid_rr_sum = 0.0

        base_exact_hits = 0
        hybrid_exact_hits = 0

        base_edition_safe = 0
        hybrid_edition_safe = 0

        base_abstention_safe = 0
        hybrid_abstention_safe = 0

        for case in GOLDEN_EVALUATION_QUERIES:
            t0 = time.perf_counter()
            base_results = _fts5_baseline_search(source_db, case.query, case.edition, k=5)
            base_elapsed = (time.perf_counter() - t0) * 1000.0
            base_latencies.append(base_elapsed)

            t1 = time.perf_counter()
            semantic_hits = store.search(case.query, case.edition, embedder, limit=10)
            hybrid_results = reciprocal_rank_fusion(case.query, base_results, semantic_hits, limit=5)
            norm_ed = case.edition.strip().upper()
            if norm_ed in ("1E", "PF1"):
                hybrid_results = [r for r in hybrid_results if r.get("system") == "1E"]
            elif norm_ed in ("2E", "PF2"):
                hybrid_results = [r for r in hybrid_results if r.get("system") == "2E"]
            hybrid_results = hybrid_results[:5]
            hybrid_elapsed = (time.perf_counter() - t1) * 1000.0
            hybrid_latencies.append(hybrid_elapsed)

            base_names = [r["name"] for r in base_results]
            hybrid_names = [r["name"] for r in hybrid_results]

            target_edition = case.edition.upper()
            if target_edition in ("1E", "PF1"):
                expected_system = "1E"
            elif target_edition in ("2E", "PF2"):
                expected_system = "2E"
            else:
                expected_system = None

            if expected_system:
                if base_results and base_results[0]["system"] == expected_system:
                    base_edition_safe += 1
                elif not base_results:
                    base_edition_safe += 1

                if hybrid_results and hybrid_results[0]["system"] == expected_system:
                    hybrid_edition_safe += 1
                elif not hybrid_results:
                    hybrid_edition_safe += 1
            else:
                base_edition_safe += 1
                hybrid_edition_safe += 1

            if case.expected_rule is not None:
                if case.expected_rule in base_names:
                    base_hits += 1
                    rank = base_names.index(case.expected_rule) + 1
                    base_rr_sum += 1.0 / rank
                if case.expected_rule in hybrid_names:
                    hybrid_hits += 1
                    rank = hybrid_names.index(case.expected_rule) + 1
                    hybrid_rr_sum += 1.0 / rank

                if case in exact_cases:
                    if base_names and base_names[0].casefold() == case.expected_rule.casefold():
                        base_exact_hits += 1
                    if hybrid_names and hybrid_names[0].casefold() == case.expected_rule.casefold():
                        hybrid_exact_hits += 1

            if case in abstention_cases:
                if not base_results or not any((r["name"] or "").casefold() in case.query.casefold() for r in base_results):
                    base_abstention_safe += 1
                if not hybrid_results or not any((r["name"] or "").casefold() in case.query.casefold() for r in hybrid_results):
                    hybrid_abstention_safe += 1

        base_latencies.sort()
        hybrid_latencies.sort()
        nb = len(base_latencies)
        nh = len(hybrid_latencies)

        total_target = len(target_cases)
        total_exact = len(exact_cases)
        total_queries = len(GOLDEN_EVALUATION_QUERIES)
        total_abstention = len(abstention_cases)

        base_recall = base_hits / total_target if total_target else 0.0
        hybrid_recall = hybrid_hits / total_target if total_target else 0.0

        base_mrr = base_rr_sum / total_target if total_target else 0.0
        hybrid_mrr = hybrid_rr_sum / total_target if total_target else 0.0

        base_exact = base_exact_hits / total_exact if total_exact else 0.0
        hybrid_exact = hybrid_exact_hits / total_exact if total_exact else 0.0

        base_edition = base_edition_safe / total_queries if total_queries else 0.0
        hybrid_edition = hybrid_edition_safe / total_queries if total_queries else 0.0

        base_abstention = base_abstention_safe / total_abstention if total_abstention else 0.0
        hybrid_abstention = hybrid_abstention_safe / total_abstention if total_abstention else 0.0

        index_size_bytes = index_db.stat().st_size if index_db.exists() else 0

        return {
            "state": "evaluation-ok",
            "model_digest": embedder.identity(),
            "dimensions": embedder.dimensions,
            "records": int(build_result.get("rows", "0")),
            "cases_count": total_queries,
            "build_time_ms": round(build_time_ms, 2),
            "index_disk_bytes": index_size_bytes,
            "baseline_fts5": {
                "recall_at_5": round(base_recall, 4),
                "mrr_at_5": round(base_mrr, 4),
                "exact_retention": round(base_exact, 4),
                "edition_isolation": round(base_edition, 4),
                "abstention_safety": round(base_abstention, 4),
                "p50_ms": round(base_latencies[int(nb * 0.50)] if nb else 0.0, 2),
                "p95_ms": round(base_latencies[min(int(nb * 0.95), nb - 1)] if nb else 0.0, 2),
            },
            "hybrid_retriever": {
                "recall_at_5": round(hybrid_recall, 4),
                "mrr_at_5": round(hybrid_mrr, 4),
                "exact_retention": round(hybrid_exact, 4),
                "edition_isolation": round(hybrid_edition, 4),
                "abstention_safety": round(hybrid_abstention, 4),
                "p50_ms": round(hybrid_latencies[int(nh * 0.50)] if nh else 0.0, 2),
                "p95_ms": round(hybrid_latencies[min(int(nh * 0.95), nh - 1)] if nh else 0.0, 2),
            },
            "delta": {
                "recall_gain": round(hybrid_recall - base_recall, 4),
                "mrr_gain": round(hybrid_mrr - base_mrr, 4),
                "exact_retention_preserved": hybrid_exact >= base_exact,
                "edition_isolation_preserved": hybrid_edition >= base_edition,
                "abstention_safety_preserved": hybrid_abstention >= base_abstention,
            },
        }
    finally:
        if temp_obj is not None:
            temp_obj.cleanup()
