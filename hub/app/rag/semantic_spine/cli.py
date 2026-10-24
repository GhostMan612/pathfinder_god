# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import get_settings
from .benchmark import run_comparative_benchmark, run_synthetic_benchmark
from .model import SemanticSpineError
from .ollama import OllamaEmbedder
from .store import SemanticStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Pathfinder God optional, local semantic sidecar")
    parser.add_argument("action", choices=("status", "preflight", "build", "search", "benchmark", "evaluate"))
    parser.add_argument("--model", default="embeddinggemma-2:270m")
    parser.add_argument("--dimensions", type=int, choices=(128, 256, 512, 768), default=256)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--ollama-url", default=None)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--edition", choices=("1e", "2e", "both"), default="both")
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    settings = get_settings()
    source = args.source or next((p for p in settings.db_paths if p.exists()), settings.db_paths[0])
    index = args.index or settings.data_dir / "semantic_rules.sqlite3"
    store = SemanticStore(index, source)
    try:
        if args.action == "status":
            print(json.dumps(store.status(), indent=2))
            return 0
        embedder = OllamaEmbedder(
            endpoint=args.ollama_url or settings.ollama_host,
            model=args.model,
            dimensions=args.dimensions,
        )
        if args.action == "preflight":
            identity = embedder.identity()
            vectors = embedder.embed(["How does flanking work?"], query=True)
            print(json.dumps({"model_identity": identity, "dimensions": len(vectors[0]), "state": "preflight-ok"}, indent=2))
            return 0
        if args.action == "build":
            print(json.dumps(store.build(embedder, args.batch_size), indent=2))
            return 0
        if args.action == "benchmark":
            report = run_synthetic_benchmark(embedder)
            print(json.dumps(report, indent=2))
            return 0
        if args.action == "evaluate":
            report = run_comparative_benchmark(embedder)
            print(json.dumps(report, indent=2))
            return 0
        if not args.query.strip():
            raise SemanticSpineError("A query is required for search")
        hits = store.search(args.query, args.edition, embedder, args.limit)
        print(
            json.dumps(
                [
                    {
                        "name": hit.record.name,
                        "system": hit.record.system,
                        "source_book": hit.record.source_book,
                        "score": round(hit.score, 5),
                    }
                    for hit in hits
                ],
                indent=2,
            )
        )
        return 0
    except (SemanticSpineError, OSError) as error:
        print(json.dumps({"state": "blocked", "reason": str(error)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
