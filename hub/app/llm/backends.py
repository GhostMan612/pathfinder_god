# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""LLM backends with the same 3-tier fallback the original scripts used.

Order of preference (from ``gm_termux_combined.py``):

1. **DeepSeek API** — only when ``PFGOD_DEEPSEEK_API_KEY`` is set. Best for the
   long biographies/backstories the tiny local model struggles with.
2. **Local Ollama** — the laptop's CPU-friendly model (``phi4-mini`` by default).
3. **Raw rule excerpts** — no LLM at all; hand back the retrieved rules so the
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
    backend: str  # "deepseek" | "ollama" | "raw-excerpts"


def _raw_excerpts(hits: list[RuleHit]) -> str:
    """Format retrieved rules as a readable, LLM-free answer (tier 3)."""
    if not hits:
        return (
            "No local rules matched and no LLM is available. Try rephrasing, or "
            "start Ollama / set a DeepSeek API key on the hub."
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
    """Routes a prompt through the 3-tier fallback, streaming or buffered."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    # -- buffered (whole answer at once) -----------------------------------

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "You are a precise Pathfinder GM with local 1e and 2e knowledge.",
        hits: list[RuleHit] | None = None,
    ) -> LLMResult:
        """Return a full answer, walking the fallback chain until one works."""
        if self._s.deepseek_api_key:
            text = await self._deepseek(prompt, system)
            if text is not None:
                return LLMResult(text=text, backend="deepseek")

        text = await self._ollama(prompt, system)
        if text is not None:
            return LLMResult(text=text, backend="ollama")

        return LLMResult(text=_raw_excerpts(hits or []), backend="raw-excerpts")

    # -- streaming (token by token, for WS /stream) ------------------------

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
        if self._s.deepseek_api_key:
            got_any = False
            async for chunk in self._deepseek_stream(prompt, system):
                got_any = True
                yield ("deepseek", chunk)
            if got_any:
                return

        got_any = False
        async for chunk in self._ollama_stream(prompt, system):
            got_any = True
            yield ("ollama", chunk)
        if got_any:
            return

        yield ("raw-excerpts", _raw_excerpts(hits or []))

    # -- DeepSeek ----------------------------------------------------------

    def _deepseek_payload(self, prompt: str, system: str, stream: bool) -> dict:
        return {
            "model": self._s.deepseek_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": self._s.ollama_temperature,
            "max_tokens": self._s.ollama_num_predict,
            "stream": stream,
        }

    async def _deepseek(self, prompt: str, system: str) -> str | None:
        url = f"{self._s.deepseek_base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._s.deepseek_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._s.deepseek_timeout_s) as client:
                resp = await client.post(url, headers=headers, json=self._deepseek_payload(prompt, system, False))
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            print(f"[DeepSeek] HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as exc:  # noqa: BLE001 - degrade to next tier
            print(f"[DeepSeek] error: {exc}")
        return None

    async def _deepseek_stream(self, prompt: str, system: str) -> AsyncIterator[str]:
        import json

        url = f"{self._s.deepseek_base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._s.deepseek_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._s.deepseek_timeout_s) as client:
                async with client.stream("POST", url, headers=headers, json=self._deepseek_payload(prompt, system, True)) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        print(f"[DeepSeek] stream HTTP {resp.status_code}")
                        return
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = json.loads(data)["choices"][0]["delta"].get("content")
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                        if delta:
                            yield delta
        except Exception as exc:  # noqa: BLE001
            print(f"[DeepSeek] stream error: {exc}")

    # -- Ollama ------------------------------------------------------------

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
        except Exception as exc:  # noqa: BLE001
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
            # trust_env=False forces Python to ignore Windows proxy settings
            async with httpx.AsyncClient(timeout=self._s.ollama_timeout_s, trust_env=False) as client:
                async with client.stream("POST", url, json=payload) as resp:
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
            print(f"\n--- OLLAMA CRASH LOG ---")
            print(f"Target URL: {url}")
            print(f"Error Details: {exc}")
            traceback.print_exc()
            print(f"------------------------\n")