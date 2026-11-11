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

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..config import Settings
from ..rag.search import RuleHit
from .gateway import get_gateway

logger = logging.getLogger(__name__)


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

    def __init__(self, settings: Settings, gateway=None) -> None:
        self._s = settings
        self._gateway = gateway or get_gateway()


    async def complete(
        self,
        prompt: str,
        *,
        system: str = "You are a precise Pathfinder GM with local 1e and 2e knowledge.",
        hits: list[RuleHit] | None = None,
        task: str = "chat",
        priority: int = 0,
    ) -> LLMResult:
        """Return a full answer, walking the fallback chain until one works."""
        text = await self._ollama(
            prompt, system, task=task, priority=priority
        )
        # Guard on content, not just None. _ollama returns
        # resp.json().get("response", ""), which is "" when Ollama answers 200
        # with an empty body, and "" is not None - so complete() returned an
        # empty answer as a successful Ollama result and never reached the
        # fallback. The documented "you always get a useful answer, even fully
        # offline" contract broke exactly when Ollama was half-alive.
        if text and text.strip():
            return LLMResult(text=text, backend="ollama")
        if text is not None:
            logger.debug("Ollama returned an empty completion; using raw excerpts")

        return LLMResult(text=_raw_excerpts(hits or []), backend="raw-excerpts")


    async def stream(
        self,
        prompt: str,
        *,
        system: str = "You are a precise Pathfinder GM with local 1e and 2e knowledge.",
        hits: list[RuleHit] | None = None,
        task: str = "chat",
        priority: int = 0,
    ) -> AsyncIterator[tuple[str, str]]:
        """Yield ``(backend, chunk)`` tuples as text arrives.

        The first tuple's ``backend`` tells the client which tier answered.
        """
        got_any = False
        async for chunk in self._ollama_stream(
            prompt, system, task=task, priority=priority
        ):
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

    async def _ollama(
        self,
        prompt: str,
        system: str,
        *,
        task: str,
        priority: int,
    ) -> str | None:
        try:
            text = await self._gateway.generate(
                prompt,
                system=system,
                model=self._s.ollama_model,
                temperature=self._s.ollama_temperature,
                num_predict=self._s.ollama_num_predict,
                task=task,
                priority=priority,
            )
            return text if text and text.strip() else None
        except Exception as exc:
            print(f"[Ollama] error: {exc}")
            return None

    async def _ollama_stream(
        self, prompt: str, system: str, *, task: str, priority: int
    ) -> AsyncIterator[str]:
        try:
            async for chunk in self._gateway.stream(
                prompt,
                system=system,
                model=self._s.ollama_model,
                temperature=self._s.ollama_temperature,
                num_predict=self._s.ollama_num_predict,
                task=task,
                priority=priority,
            ):
                yield chunk
        except Exception as exc:
            print(f"[Ollama] stream error: {exc}")