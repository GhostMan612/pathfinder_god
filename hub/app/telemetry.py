# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Routing feedback telemetry: why the Rules Lawyer could not answer.

Two failure modes are worth knowing about at the table rather than discovering
weeks later:

  * ``abstain`` - the calibrated gate decided the corpus cannot answer, so the
    GM refused. That is correct behaviour, but a rising count means the rules
    DB is missing material the group actually asks about.
  * ``bad_inline_citation`` - the model wrote a bracketed ``[Book - Rule]`` tag
    naming a rule it was never shown. The deterministic Sources block is
    trustworthy; the prose is not, so these tags are stripped. Every occurrence
    is a retrieval or prompt defect worth fixing upstream.

Design constraints, in priority order:

  1. **Never break a request.** Every I/O error is swallowed. A read-only
     checkout, a full disk, or a missing ``data/`` directory must not turn a
     rules ruling into a 500.
  2. **Never block the request path.** Writes happen on a daemon thread.
  3. **Never write to the real log during tests.** ``PFGOD_MISS_LOG`` redirects
     the path, and ``flush_pending()`` lets a test join the writers before it
     asserts.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

#: Environment override, primarily so hermetic tests can redirect the sink.
MISS_LOG_ENV = "PFGOD_MISS_LOG"

#: Query text is truncated: this is a diagnostic breadcrumb, not a transcript.
_MAX_QUERY_CHARS = 300
_MAX_DETAIL_CHARS = 400
_MAX_STRIPPED = 10

#: Writers are tracked so tests can join them. Daemon threads only, so a hung
#: write can never hold up interpreter shutdown.
_pending: list[threading.Thread] = []
_pending_lock = threading.Lock()


def _repo_root() -> Path:
    """<repo>/hub/app/telemetry.py -> parents[2] is the repo root."""
    return Path(__file__).resolve().parents[2]


def miss_log_path() -> Path:
    """Where misses are appended. Redirectable via ``PFGOD_MISS_LOG``."""
    override = os.environ.get(MISS_LOG_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "data" / "misses.jsonl"


def _append(payload: dict, path: Path) -> None:
    """Write one line, swallowing everything."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        # Deliberately empty: telemetry must never break a request. A full
        # disk, a read-only mount or a permissions error is not the player's
        # problem to hear about at the table.
        pass


def log_miss(
    event: str,
    query: str,
    *,
    route_score: float | None = None,
    details: dict | None = None,
) -> None:
    """Queue one diagnostic record. Returns immediately.

    ``event`` is ``"abstain"`` or ``"bad_inline_citation"``.
    """
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "query": (query or "")[:_MAX_QUERY_CHARS],
    }
    if route_score is not None:
        payload["route_score"] = route_score
    if details:
        payload["details"] = {
            k: (str(v)[:_MAX_DETAIL_CHARS] if not isinstance(v, (int, float, bool)) else v)
            for k, v in list(details.items())[:_MAX_STRIPPED]
        }

    path = miss_log_path()

    def _run() -> None:
        _append(payload, path)

    thread = threading.Thread(target=_run, daemon=True)
    with _pending_lock:
        # Drop finished threads so the list cannot grow without bound.
        _pending[:] = [t for t in _pending if t.is_alive()]
        _pending.append(thread)
    try:
        thread.start()
    except Exception:
        pass


def flush_pending(timeout: float = 5.0) -> None:
    """Join outstanding writers. For tests; no-op in production."""
    with _pending_lock:
        threads = list(_pending)
    for t in threads:
        t.join(timeout=timeout)


def read_misses(path: Path | None = None) -> list[dict]:
    """Parse the log. Returns [] on any problem - diagnostics only."""
    target = path or miss_log_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except Exception:
        return []
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def count_since(path: Path | None = None) -> dict:
    """{event: count} over the whole log. Cheap enough for a status bar."""
    counts: dict[str, int] = {}
    for row in read_misses(path):
        event = str(row.get("event", "unknown"))
        counts[event] = counts.get(event, 0) + 1
    return counts


# Re-exported so callers do not need a second import for time.
__all__ = [
    "MISS_LOG_ENV",
    "count_since",
    "flush_pending",
    "log_miss",
    "miss_log_path",
    "read_misses",
    "time",
]
