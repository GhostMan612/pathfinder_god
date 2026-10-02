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
from collections import deque
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
        # Read only the tail. misses.jsonl is append-only with no size cap and is
        # reachable via POST /rules/missed, so limit=1000 used to load the whole
        # file into memory just to slice the last 1000 lines.
        with miss_path().open("r", encoding="utf-8") as fh:
            lines = list(deque(fh, maxlen=max(limit, 1)))
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
