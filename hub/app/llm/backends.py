# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""LLM backends with a local-only 2-tier fallback.

Order of preference:

1. **Local Ollama** — the laptop's CPU-friendly model (``phi4-mini`` by default).
2. **Raw rule excerpts** — no LLM at all; hand back the retrieved rules so the
   user *always* gets a useful answer, even fully offline with Ollama stopped.

Everything is async (``httpx``) so the FastAPI hub can stream tokens to the
phone without blocking, and so a slow/hung backend can't wedge the server.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from ..config import Settings
from ..rag.search import RuleHit


@dataclass
class LLMResult:
    """The outcome of a generation, tagged with which backend produced it."""

    text: str
    backend: str


def _raw_excerpts(hits: list[RuleHit]) -> str:
    """Format retrieved rules as a readable, LLM-free answer (tier 2)."""
    if not hits:
        return (
            "No local rules matched and no LLM is available. Try rephrasing, or "
            "start Ollama on the hub."
        )
    lines = ["(No LLM available — here are the most relevant rule excerpts.)", ""]
    for i, h in enumerate(hits, 1):
        lines.append(f"--- Result {i} ---")
        if h.system:
            lines.append(f"System: {h.system.upper()}")
        if h.category:
            lines.append(f"Category: {h.category}")
        lines.append(f"Name: {h.name}")
        if h.source_book:
            lines.append(f"Source: {h.source_book}")
        lines.append(f"Content:\n{h.content}\n")
    return "\n".join(lines)


class LLMRouter:
    """Routes a prompt through the local-only fallback, streaming or buffered."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings


    async def complete(
        self,
        prompt: str,
        *,
        system: str = "You are a precise Pathfinder GM with local 1e and 2e knowledge.",
        hits: list[RuleHit] | None = None,
    ) -> LLMResult:
        """Return a full answer, walking the fallback chain until one works."""
        text = await self._ollama(prompt, system)
        if text is not None:
            return LLMResult(text=text, backend="ollama")

        return LLMResult(text=_raw_excerpts(hits or []), backend="raw-excerpts")


    async def stream(
        self,
        prompt: str,
        *,
        system: str = "You are a precise Pathfinder GM with local 1e and 2e knowledge.",
        hits: list[RuleHit] | None = None,
    ) -> AsyncIterator[tuple[str, str]]:
        """Yield ``(backend, chunk)`` tuples as text arrives.

        The first tuple's ``backend`` tells the client which tier answered.
        """
        got_any = False
        async for chunk in self._ollama_stream(prompt, system):
            got_any = True
            yield ("ollama", chunk)
        if got_any:
            return

        yield ("raw-excerpts", _raw_excerpts(hits or []))


    def _ollama_options(self) -> dict:
        return {
            "temperature": self._s.ollama_temperature,
            "num_predict": self._s.ollama_num_predict,
        }

    async def _ollama(self, prompt: str, system: str) -> str | None:
        url = f"{self._s.ollama_host}/api/generate"
        payload = {
            "model": self._s.ollama_model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": self._ollama_options(),
        }
        try:
            async with httpx.AsyncClient(timeout=self._s.ollama_timeout_s, trust_env=False) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json().get("response", "")
            print(f"[Ollama] HTTP {resp.status_code}")
        except Exception as exc:
            print(f"[Ollama] error: {exc}")
        return None

    async def _ollama_stream(self, prompt: str, system: str) -> AsyncIterator[str]:
        import json
        import traceback

        url = f"{self._s.ollama_host}/api/generate"
        payload = {
            "model": self._s.ollama_model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "options": self._ollama_options(),
        }
        try:
            async with httpx.AsyncClient(timeout=self._s.ollama_timeout_s, trust_env=False) as client, client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    err = await resp.aread()
                    print(f"[Ollama] stream HTTP {resp.status_code}: {err.decode('utf-8', errors='ignore')}")
                    return
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = obj.get("response")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break
        except Exception as exc:
            print("\n--- OLLAMA CRASH LOG ---")
            print(f"Target URL: {url}")
            print(f"Error Details: {exc}")
            traceback.print_exc()
            print("------------------------\n")