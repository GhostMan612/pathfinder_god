# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Miss log — queries nobody could answer, queued for chunked backfill.

When /rules/fetch can't find or scrape a term (or the Spoke was offline),
the miss lands here as one JSON line in data/misses.jsonl. Bulk runs read
this file to prioritize what the fleet scrapes next, so every miss makes
the database permanently more complete.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


def miss_path() -> Path:
    return get_settings().data_dir / "misses.jsonl"


def log_miss(query: str, edition: str = "both", source: str = "spoke") -> None:
    query = (query or "").strip()
    if not query:
        return
    try:
        path = miss_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "query": query[:200],
                "edition": edition,
                "source": source,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_misses(limit: int = 500) -> list[dict[str, Any]]:
    try:
        lines = miss_path().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
