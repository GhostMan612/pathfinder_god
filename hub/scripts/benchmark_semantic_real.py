# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Real-corpus held-out benchmark: production FTS5 vs FTS5 + semantic RRF.

The hermetic ``cli evaluate`` command builds a 10-record synthetic corpus. That
is necessary but not sufficient for the semantic enable gate: P05 requires a
held-out real-corpus comparison. This script samples rule records from the
production database, derives queries that do not contain the rule name, and
scores the production lexical path against the production hybrid path.

    python scripts/benchmark_semantic_real.py --sample 20 --paraphrases

Paraphrases are generated once with a local Ollama model and cached under
``data/`` so reruns stay comparable and cheap. The script never writes the
rules database or the semantic sidecar.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sqlite3
import sys
import time
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "hub") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "hub"))

import app.config
from app.rag.retriever import Retriever
from app.rag.semantic_spine.adapter import hybrid_search
from app.rag.semantic_spine.ollama import OllamaEmbedder

ABSTENTION_QUERIES = [
    ("starship hyperdrive navigation", "2e"),
    ("laser rifle battery recharge", "2e"),
    ("cybernetic arm enhancement", "1e"),
]

PARAPHRASE_PROMPT = """Rewrite the Pathfinder rule below as a natural question a player would ask at the table.
Rules:
- At most 14 words.
- Do not use the rule name or any proper noun from it.
- Preserve the mechanical intent.
- Output only the question.

Rule name: {name}
Rule text: {content}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-corpus semantic enable-gate benchmark")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "data" / "pathfinder_rag.db")
    parser.add_argument("--index", type=Path, default=REPO_ROOT / "data" / "semantic_rules.sqlite3")
    parser.add_argument("--sample", type=int, default=20, help="rules sampled per edition")
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="embeddinggemma-2:270m")
    parser.add_argument("--dimensions", type=int, default=256)
    parser.add_argument("--paraphrase-model", default="phi4-mini")
    parser.add_argument("--paraphrases", action="store_true", help="generate held-out paraphrases with Ollama")
    parser.add_argument("--cache", type=Path, default=REPO_ROOT / "data" / "semantic_eval_paraphrases.json")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


def sample_rules(db: Path, edition: str, count: int, seed: int) -> list[sqlite3.Row]:
    with closing(sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True, timeout=10.0)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT rowid, system, category, name, source_book, raw_content "
            "FROM rules WHERE system = ? AND source_book != 'Unknown Source' "
            "AND length(name) BETWEEN 8 AND 60 AND length(raw_content) BETWEEN 400 AND 4000",
            (edition,),
        ).fetchall()
    unique: dict[str, sqlite3.Row] = {}
    for row in rows:
        unique.setdefault(str(row["name"]).strip().casefold(), row)
    pool = list(unique.values())
    rng = random.Random(f"{seed}:{edition}")
    return rng.sample(pool, min(count, len(pool)))


def ollama_generate(url: str, model: str, prompt: str, timeout: float = 180.0) -> str:
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 48},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return str(payload.get("response", "")).strip()


def paraphrase(url: str, model: str, rule: sqlite3.Row) -> str | None:
    prompt = PARAPHRASE_PROMPT.format(
        name=rule["name"],
        content=str(rule["raw_content"])[:1200],
    )
    try:
        text = ollama_generate(url, model, prompt)
    except Exception:
        return None
    text = text.strip().strip('"').splitlines()[0].strip()
    if not text.endswith("?"):
        text += "?"
    if len(text) > 160:
        return None
    name = str(rule["name"]).casefold()
    if name in text.casefold():
        return None
    return text


def load_cache(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def rank_of(names: list[str], expected: str) -> int | None:
    target = expected.casefold()
    for position, name in enumerate(names, start=1):
        if (name or "").casefold() == target:
            return position
    return None


def score_queries(
    label: str,
    cases: list[dict],
    retriever: Retriever,
    embedder: OllamaEmbedder,
    db: Path,
) -> dict[str, object]:
    latencies: list[float] = []
    per_type: dict[str, dict[str, float]] = {}
    hits = 0
    rr_sum = 0.0
    ranked_cases = 0
    abstention_total = 0
    abstention_safe = 0
    details: list[dict] = []

    for case in cases:
        query = case["query"]
        started = time.perf_counter()
        lexical = retriever._fts5_search_sync(query, case["edition"], 5)
        epoch = time.perf_counter() - started
        if label == "hybrid":
            rows = asyncio.run(
                hybrid_search(
                    query,
                    case["edition"],
                    5,
                    lexical,
                    source_path=db,
                    embedder=embedder,
                )
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
        else:
            rows = lexical
            elapsed_ms = epoch * 1000.0
        latencies.append(elapsed_ms)

        names = [str(row.get("name") or "") for row in rows]
        bucket = per_type.setdefault(case["type"], {"cases": 0, "hits": 0, "rr": 0.0, "abstention_safe": 0})
        bucket["cases"] += 1

        if case["type"] == "abstention":
            abstention_total += 1
            safe = not any(name.casefold() in query.casefold() for name in names if name)
            if safe:
                abstention_safe += 1
                bucket["abstention_safe"] += 1
            details.append({"query": query, "type": case["type"], "top": names[:3], "safe": safe})
            continue

        ranked_cases += 1
        rank = rank_of(names, case["expected"])
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank
            bucket["hits"] += 1
            bucket["rr"] += 1.0 / rank
        details.append({"query": query, "type": case["type"], "expected": case["expected"], "rank": rank, "top": names[:3]})

    latencies.sort()
    n = len(latencies)
    summary: dict[str, object] = {
        "cases": len(cases),
        "recall_at_5": round(hits / ranked_cases, 4) if ranked_cases else 0.0,
        "mrr_at_5": round(rr_sum / ranked_cases, 4) if ranked_cases else 0.0,
        "abstention_safety": round(abstention_safe / abstention_total, 4) if abstention_total else 1.0,
        "p50_ms": round(latencies[int(n * 0.50)] if n else 0.0, 2),
        "p95_ms": round(latencies[min(int(n * 0.95), n - 1)] if n else 0.0, 2),
        "by_type": {},
    }
    for name, bucket in per_type.items():
        if name == "abstention":
            count = bucket["cases"] or 1
            summary["by_type"][name] = {
                "cases": bucket["cases"],
                "abstention_safety": round(bucket["abstention_safe"] / count, 4),
            }
        else:
            count = bucket["cases"] or 1
            summary["by_type"][name] = {
                "cases": bucket["cases"],
                "recall_at_5": round(bucket["hits"] / count, 4),
                "mrr_at_5": round(bucket["rr"] / count, 4),
            }
    return {"summary": summary, "details": details}


def main() -> int:
    args = parse_args()
    for path, label in ((args.db, "rules database"), (args.index, "semantic sidecar")):
        if not path.is_file():
            print(f"Missing {label}: {path}", file=sys.stderr)
            return 2

    settings = app.config.Settings(
        semantic_enabled=True,
        semantic_index_path=args.index,
        ollama_host=args.ollama_url,
        semantic_timeout_s=120.0,
    )
    app.config.get_settings = lambda: settings
    retriever = Retriever(None)  # repository is unused by the lexical path
    retriever.settings = settings
    embedder = OllamaEmbedder(
        endpoint=args.ollama_url,
        model=args.model,
        dimensions=args.dimensions,
        timeout_s=120.0,
    )

    cache = load_cache(args.cache)
    cases: list[dict] = []
    sampled = 0
    for edition in ("2E", "1E"):
        for rule in sample_rules(args.db, edition, args.sample, args.seed):
            sampled += 1
            key = f"{edition}:{rule['rowid']}"
            cases.append(
                {
                    "query": str(rule["name"]),
                    "edition": edition.lower(),
                    "expected": str(rule["name"]),
                    "type": "exact",
                }
            )
            if not args.paraphrases:
                continue
            question = cache.get(key)
            if question is None:
                question = paraphrase(args.ollama_url, args.paraphrase_model, rule)
                if question:
                    cache[key] = question
                print(f"[paraphrase] {rule['name']} -> {question}", file=sys.stderr)
            if question:
                cases.append(
                    {
                        "query": question,
                        "edition": edition.lower(),
                        "expected": str(rule["name"]),
                        "type": "paraphrase",
                    }
                )

    for query, edition in ABSTENTION_QUERIES:
        cases.append({"query": query, "edition": edition, "expected": None, "type": "abstention"})

    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

    baseline = score_queries("baseline", cases, retriever, embedder, args.db)
    hybrid = score_queries("hybrid", cases, retriever, embedder, args.db)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db": str(args.db),
        "index": str(args.index),
        "model": args.model,
        "dimensions": args.dimensions,
        "sampled_rules": sampled,
        "query_count": len(cases),
        "baseline_fts5": baseline["summary"],
        "hybrid_retriever": hybrid["summary"],
        "delta": {
            "recall_gain": round(hybrid["summary"]["recall_at_5"] - baseline["summary"]["recall_at_5"], 4),
            "mrr_gain": round(hybrid["summary"]["mrr_at_5"] - baseline["summary"]["mrr_at_5"], 4),
            "abstention_gain": round(
                hybrid["summary"]["abstention_safety"] - baseline["summary"]["abstention_safety"], 4
            ),
        },
        "queries": {"baseline": baseline["details"], "hybrid": hybrid["details"]},
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
