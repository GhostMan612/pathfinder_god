# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Rate-limit probe — find each domain's safe crawl speed BEFORE scraping.

Ramps request rate in phases and STOPS at the first sign of throttling
(HTTP 429/403, repeated 5xx/timeouts, or latency collapse). Writes
probe_results.json, which fleet.py picks up automatically.

Polite by design: starts at 1 req / 2s, never exceeds 4 rps, ~30 requests
per domain max, rotating User-Agents, honors Retry-After. Run:

    C:\\venv-hub\\venv\\Scripts\\python.exe hub/scripts/probe_limits.py
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import aiohttp

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from fleet import (  # noqa: E402
    PROBE_FILE,
    USER_AGENTS,
    PROJECT_TAG,
    robots_snapshot,
)

import random

TARGETS = {
    "2e.aonprd.com": [
        "https://2e.aonprd.com/",
        "https://2e.aonprd.com/Conditions.aspx",
    ],
    "www.aonprd.com": [
        "https://www.aonprd.com/",
        "https://www.aonprd.com/Conditions.aspx",
    ],
    "www.d20pfsrd.com": [
        "https://www.d20pfsrd.com/",
        "https://www.d20pfsrd.com/conditions",
    ],
}

PHASES = [(2.0, 4), (1.0, 6), (0.5, 8), (0.25, 8)]


async def one(session: aiohttp.ClientSession, url: str) -> tuple[int | None, float]:
    start = time.monotonic()
    try:
        async with session.get(
            url,
            headers={"User-Agent": f"{random.choice(USER_AGENTS)} {PROJECT_TAG}"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            await resp.read()
            retry_after = resp.headers.get("Retry-After")
            if resp.status == 429 and retry_after:
                try:
                    await asyncio.sleep(min(float(retry_after), 30.0))
                except ValueError:
                    pass
            return resp.status, time.monotonic() - start
    except Exception:
        return None, time.monotonic() - start


async def probe_domain(session: aiohttp.ClientSession, domain: str, urls: list[str]) -> dict:
    print(f"== probing {domain}", flush=True)
    last_clean = PHASES[0][0]
    reason = "completed all phases"
    latencies: list[float] = []
    i = 0
    for interval, count in PHASES:
        phase_status: list[int | None] = []
        phase_lat: list[float] = []
        for _ in range(count):
            url = urls[i % len(urls)]
            i += 1
            status, dt = await one(session, url)
            phase_status.append(status)
            phase_lat.append(dt)
            print(f"   {interval:>4}s interval -> {status} in {dt:.2f}s {url}", flush=True)
            await asyncio.sleep(interval)
        bad = sum(1 for s in phase_status if s in (429, 403) or s is None or (s is not None and s >= 500))
        p50 = statistics.median(phase_lat) if phase_lat else 0.0
        latencies.extend(phase_lat)
        if any(s in (429, 403) for s in phase_status):
            reason = f"throttled at {interval}s interval (429/403)"
            break
        if bad >= 2:
            reason = f"errors at {interval}s interval ({bad}/{len(phase_status)})"
            break
        if p50 > 6.0:
            reason = f"latency collapse at {interval}s interval (p50 {p50:.1f}s)"
            break
        last_clean = interval
    safe = round(min(last_clean * 2.0, 5.0), 2)
    result = {
        "safe_interval": safe,
        "max_ok_rps": round(1.0 / last_clean, 2),
        "stopped": reason,
        "p50_latency": round(statistics.median(latencies), 2) if latencies else None,
    }
    print(f"   => {domain}: safe_interval={safe}s ({reason})", flush=True)
    return result


async def main() -> int:
    out: dict = {"domains": {}, "robots": {}}
    async with aiohttp.ClientSession() as session:
        for domain in TARGETS:
            out["robots"][domain] = await robots_snapshot(session, domain)
        for domain, urls in TARGETS.items():
            out["domains"][domain] = await probe_domain(session, domain, urls)
            await asyncio.sleep(2.0)
    PROBE_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {PROBE_FILE}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
