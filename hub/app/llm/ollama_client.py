# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Ollama Client — async facade over the single LLM gateway.

All HTTP to Ollama goes through :class:`app.llm.gateway.LlmGateway`, which owns
the priority queue, in-flight cap, and result cache. This class keeps the
existing agent-facing method names so callers do not need to change.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.llm.gateway import get_gateway

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, host: str = "http://127.0.0.1:11450"):
        # Kept for callers/tests that pass a host. The process-wide gateway
        # owns the actual endpoint (settings.ollama_host).
        self.host = host.rstrip("/")
        self._gateway = get_gateway()

    async def close(self) -> None:
        """No-op: the shared gateway owns its client connection pool."""

    async def generate(
        self,
        prompt: str,
        system: str = "",
        model: str = "phi4-mini",
        temperature: float = 0.6,
        num_predict: int = 700,
        format: str | None = None,
        *,
        task: str | None = None,
        priority: int = 0,
    ) -> str:
        """Single completion call.

        `format="json"` asks Ollama for grammar-constrained JSON, which is how
        small models like qwen2.5:3b are made to emit parseable output. JSON
        generations are cached as ``builder`` work; free text is not cached.
        """
        try:
            return await self._gateway.generate(
                prompt,
                system=system,
                model=model,
                temperature=temperature,
                num_predict=num_predict,
                format=format,
                task=task or ("builder" if format == "json" else "chat"),
                priority=priority,
            )
        except httpx.HTTPError as e:
            logger.error(f"Ollama generate failed: {e}")
            raise OllamaError(f"Ollama request failed: {e}") from e

    async def stream(
        self,
        prompt: str,
        system: str = "",
        model: str = "phi4-mini",
        *,
        task: str = "chat",
        priority: int = 0,
    ) -> AsyncGenerator[str, None]:
        """Streaming completion."""
        try:
            async for chunk in self._gateway.stream(
                prompt,
                system=system,
                model=model,
                task=task,
                priority=priority,
            ):
                yield chunk
        except httpx.HTTPError as e:
            logger.error(f"Ollama stream failed: {e}")
            raise OllamaError(f"Ollama stream failed: {e}") from e

    async def embeddings(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """Get embeddings for text."""
        try:
            return await self._gateway.embeddings(text, model=model)
        except httpx.HTTPError as e:
            logger.error(f"Ollama embeddings failed: {e}")
            raise OllamaError(f"Ollama embeddings failed: {e}") from e

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str = "qwen2.5:3b",
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.6,
        num_predict: int = 700,
        *,
        task: str = "chat",
        priority: int = 0,
    ) -> dict[str, Any]:
        """Chat with tool-calling support (Ollama /api/chat).

        Returns the raw message dict: {role, content, tool_calls?}.
        Tools format: [{"type":"function","function":{"name":..., "description":..., "parameters":{...}}}]
        """
        try:
            return await self._gateway.chat(
                messages,
                model=model,
                tools=tools,
                temperature=temperature,
                num_predict=num_predict,
                task=task,
                priority=priority,
            )
        except httpx.HTTPError as e:
            logger.error(f"Ollama chat failed: {e}")
            raise OllamaError(f"Ollama chat failed: {e}") from e

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        model: str = "qwen2.5:3b",
        tools: list[dict[str, Any]] | None = None,
        *,
        task: str = "chat",
        priority: int = 0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Streaming chat with tool calls (yields message chunks)."""
        try:
            async for message in self._gateway.chat_stream(
                messages,
                model=model,
                tools=tools,
                task=task,
                priority=priority,
            ):
                yield message
        except httpx.HTTPError as e:
            logger.error(f"Ollama chat stream failed: {e}")
            raise OllamaError(f"Ollama chat stream failed: {e}") from e
