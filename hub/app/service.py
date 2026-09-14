# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""The God service — orchestrates retrieval + agent prompt + LLM routing.

This is the single seam the HTTP layer (and the CLI) call into. It mirrors the
old ``run_agent`` flow but split so answers can be either buffered or streamed,
and so the retrieved rule hits are available for the tier-3 raw-excerpt fallback.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .agent.gm import build_prompt, detect_mode
from .config import Settings
from .llm.backends import LLMResult, LLMRouter
from .rag.search import Retriever, RuleHit, normalize_edition

_SYSTEM_PROMPT = (
    "You are the Pathfinder God: an all-knowing, fair Game Master with local Pathfinder "
    "1e and 2e knowledge. You build characters, NPCs, monsters, bosses, maps, and "
    "campaigns with full biographies and backstories, and you run the game."
)


@dataclass
class Prepared:
    """Everything needed to run one generation."""

    mode: str
    edition: str
    prompt: str
    hits: list[RuleHit]


class GodService:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._retriever = Retriever(settings.db_paths, rag_limit=settings.rag_limit)
        self._llm = LLMRouter(settings)

    # -- shared prep -------------------------------------------------------

    def prepare(
        self,
        user_query: str,
        *,
        edition: str | None = None,
        mode: str | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> Prepared:
        norm_edition = normalize_edition(edition)
        resolved_mode = mode or detect_mode(user_query)
        hits = self._retriever.search(user_query, edition=norm_edition)
        context = (
            "\n\n".join(h.as_context_block() for h in hits)
            if hits
            else "No local rule matched; rely on general Pathfinder principles and state assumptions."
        )
        prompt = build_prompt(user_query, resolved_mode, norm_edition, context, history=history)
        return Prepared(mode=resolved_mode, edition=norm_edition, prompt=prompt, hits=hits)

    # -- buffered ----------------------------------------------------------

    async def ask(
        self,
        user_query: str,
        *,
        edition: str | None = None,
        mode: str | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> tuple[LLMResult, Prepared]:
        prepared = self.prepare(user_query, edition=edition, mode=mode, history=history)
        result = await self._llm.complete(prepared.prompt, system=_SYSTEM_PROMPT, hits=prepared.hits)
        return result, prepared

    # -- streaming ---------------------------------------------------------

    async def stream(
        self,
        user_query: str,
        *,
        edition: str | None = None,
        mode: str | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> AsyncIterator[tuple[str, str]]:
        """Yield ``(backend, chunk)`` tuples for a live 'God is typing' feed."""
        prepared = self.prepare(user_query, edition=edition, mode=mode, history=history)
        async for backend, chunk in self._llm.stream(prepared.prompt, system=_SYSTEM_PROMPT, hits=prepared.hits):
            yield backend, chunk

    # -- read-only retrieval (for the bestiary / rules browser) ------------

    def search_rules(self, query: str, edition: str | None = None, limit: int | None = None) -> list[RuleHit]:
        return self._retriever.search(query, edition=normalize_edition(edition), limit=limit)
