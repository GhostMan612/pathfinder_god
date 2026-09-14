# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import json
import os
from typing import Iterator

import requests

HUB_URL = "http://127.0.0.1:8000"


def _ollama_url() -> str:
    raw = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = f"http://{raw}"
    raw = raw.replace("://0.0.0.0", "://127.0.0.1")
    return raw.rstrip("/")


OLLAMA_URL = _ollama_url()
HTTP_TIMEOUT = 10
GENERATE_TIMEOUT = 300


def hub_health() -> dict | None:
    try:
        r = requests.get(f"{HUB_URL}/health", timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def ollama_up() -> bool:
    try:
        return requests.get(OLLAMA_URL, timeout=3).status_code == 200
    except requests.RequestException:
        return False


def installed_models() -> list[dict]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            return r.json().get("models", [])
    except requests.RequestException:
        pass
    return []


def rules_search(query: str, edition: str = "both", limit: int = 10) -> list[dict]:
    r = requests.get(
        f"{HUB_URL}/rules/search",
        params={"q": query, "edition": edition, "limit": limit},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def generate(kind: str, prompt: str, edition: str = "2e") -> dict:
    r = requests.post(
        f"{HUB_URL}/generate/{kind}",
        json={"prompt": prompt, "edition": edition},
        timeout=GENERATE_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def ask(query: str, edition: str = "both", history: list[list[str]] | None = None) -> dict:
    r = requests.post(
        f"{HUB_URL}/ask",
        json={"query": query, "edition": edition, "history": history or []},
        timeout=GENERATE_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def stream_events(query: str, edition: str = "both") -> Iterator[dict]:
    from websockets.sync.client import connect

    ws_url = HUB_URL.replace("http://", "ws://") + "/stream"
    with connect(ws_url, close_timeout=3) as ws:
        ws.send(json.dumps({"query": query, "edition": edition, "history": []}))
        for raw in ws:
            yield json.loads(raw)
