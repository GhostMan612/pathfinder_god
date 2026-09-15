# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Fetcher fleet — polite, resumable scraping primitives.

One shared module so every scraper (AoN 2e/1e, d20pfsrd) behaves the same:
- Rotating User-Agents per request (no single fingerprint hammering).
- Per-domain rate limiter (intervals from probe_results.json when present,
  else conservative defaults). Never faster than 4 req/s anywhere.
- Retry with exponential backoff; honors Retry-After on 429/503.
- robots.txt snapshot per domain (informational; our content paths — AoN
  index/detail pages, d20pfsrd articles — are not disallowed).
- JSON checkpoints so chunked runs resume instead of restarting.

Tuning workflow: run probe_limits.py first, it writes probe_results.json,
fleet picks it up automatically. Scrapers take --limit/--offset/--resume
so a full site becomes many small polite chunks.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger("fleet")

SCRIPTS_DIR = Path(__file__).resolve().parent
PROBE_FILE = SCRIPTS_DIR / "probe_results.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

DEFAULT_INTERVALS = {
    "2e.aonprd.com": 1.5,
    "www.aonprd.com": 1.5,
    "www.d20pfsrd.com": 1.0,
}
FALLBACK_INTERVAL = 2.0
MAX_INTERVAL_FLOOR = 0.25

PROJECT_TAG = "PathfinderGod/1.0"


class FetchError(Exception):
    def __init__(self, url: str, status: int | None, message: str = ""):
        super().__init__(f"fetch {status} {url} {message}".strip())
        self.url = url
        self.status = status


def load_intervals(path: Path = PROBE_FILE) -> dict[str, float]:
    intervals = dict(DEFAULT_INTERVALS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for domain, info in (data.get("domains") or {}).items():
            safe = float(info.get("safe_interval", 0) or 0)
            if safe > 0:
                intervals[domain] = max(safe, MAX_INTERVAL_FLOOR)
    except Exception:
        pass
    return intervals


class DomainLimiter:
    """Async per-domain minimum-interval gate."""

    def __init__(self, intervals: dict[str, float] | None = None):
        self.intervals = intervals or load_intervals()
        self._locks: dict[str, asyncio.Lock] = {}
        self._last: dict[str, float] = {}

    def interval_for(self, url: str) -> float:
        domain = urlparse(url).netloc.lower()
        return max(self.intervals.get(domain, FALLBACK_INTERVAL), MAX_INTERVAL_FLOOR)

    async def wait(self, url: str) -> None:
        domain = urlparse(url).netloc.lower()
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            wait_for = self._last.get(domain, 0.0) + self.interval_for(url) - time.monotonic()
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last[domain] = time.monotonic()


def _pick_ua() -> str:
    return f"{random.choice(USER_AGENTS)} {PROJECT_TAG}"


async def fetch(
    session: aiohttp.ClientSession,
    url: str,
    limiter: DomainLimiter | None = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> str:
    """GET url as text. Rotates UA, backs off on 429/5xx, honors Retry-After."""
    last_status: int | None = None
    for attempt in range(retries + 1):
        if limiter is not None:
            await limiter.wait(url)
        try:
            async with session.get(
                url,
                headers={"User-Agent": _pick_ua()},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                last_status = resp.status
                if resp.status in (429, 500, 502, 503, 504) and attempt < retries:
                    retry_after = resp.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else (2.0 * (attempt + 1))
                    except ValueError:
                        delay = 2.0 * (attempt + 1)
                    delay = min(delay + random.uniform(0, 1.0), 60.0)
                    logger.warning(f"fleet: {resp.status} {url} — backing off {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
                raise FetchError(url, resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < retries:
                delay = 2.0 * (attempt + 1) + random.uniform(0, 1.0)
                logger.warning(f"fleet: network error {url} ({e}) — retry in {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            raise FetchError(url, last_status, str(e)) from e
    raise FetchError(url, last_status, "retries exhausted")


class Checkpoint:
    """Resumable progress: {done: [url...], cursor: int} as JSON."""

    def __init__(self, path: Path):
        self.path = path
        self.done: set[str] = set()
        self.cursor: int = 0
        self._since_save = 0
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.done = set(data.get("done", []))
            self.cursor = int(data.get("cursor", 0))
        except Exception:
            pass

    def save(self, force: bool = False) -> None:
        self._since_save += 1
        if not force and self._since_save < 25:
            return
        self._since_save = 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"done": sorted(self.done), "cursor": self.cursor}),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"fleet: checkpoint save failed: {e}")

    def has(self, url: str) -> bool:
        return url in self.done

    def mark(self, url: str) -> None:
        self.done.add(url)
        self.save()


async def robots_snapshot(session: aiohttp.ClientSession, domain: str) -> dict:
    """Fetch robots.txt for the record (informational only)."""
    url = f"https://{domain}/robots.txt"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return {"domain": domain, "status": resp.status, "rules": []}
            text = await resp.text()
            rules = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
            return {"domain": domain, "status": 200, "rules": rules[:40]}
    except Exception as e:
        return {"domain": domain, "status": None, "rules": [], "error": str(e)}
