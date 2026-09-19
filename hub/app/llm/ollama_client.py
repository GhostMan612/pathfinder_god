# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Ollama Client — Async HTTP client for local LLM inference.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, host: str = "http://127.0.0.1:11450"):
        self.host = host.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            timeout = get_settings().ollama_timeout_s
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        prompt: str,
        system: str = "",
        model: str = "phi4-mini",
        temperature: float = 0.6,
        num_predict: int = 700,
    ) -> str:
        """Single completion call."""
        client = await self._get_client()
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        try:
            resp = await client.post(f"{self.host}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except httpx.HTTPError as e:
            logger.error(f"Ollama generate failed: {e}")
            raise OllamaError(f"Ollama request failed: {e}") from e

    async def stream(
        self,
        prompt: str,
        system: str = "",
        model: str = "phi4-mini",
    ) -> AsyncGenerator[str, None]:
        """Streaming completion."""
        client = await self._get_client()
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": True,
        }
        try:
            async with client.stream("POST", f"{self.host}/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPError as e:
            logger.error(f"Ollama stream failed: {e}")
            raise OllamaError(f"Ollama stream failed: {e}") from e

    async def embeddings(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """Get embeddings for text."""
        client = await self._get_client()
        payload = {"model": model, "prompt": text}
        try:
            resp = await client.post(f"{self.host}/api/embeddings", json=payload)
            resp.raise_for_status()
            return resp.json().get("embedding", [])
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
    ) -> dict[str, Any]:
        """Chat with tool-calling support (Ollama /api/chat).

        Returns the raw message dict: {role, content, tool_calls?}.
        Tools format: [{"type":"function","function":{"name":..., "description":..., "parameters":{...}}}]
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        if tools:
            payload["tools"] = tools
        try:
            resp = await client.post(f"{self.host}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Ollama /api/chat wraps: {message:{role,content,tool_calls}, done: true, ...}
            return data.get("message", data)
        except httpx.HTTPError as e:
            logger.error(f"Ollama chat failed: {e}")
            raise OllamaError(f"Ollama chat failed: {e}") from e

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        model: str = "qwen2.5:3b",
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Streaming chat with tool calls (yields message chunks)."""
        client = await self._get_client()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        try:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "message" in data:
                            yield data["message"]
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPError as e:
            logger.error(f"Ollama chat stream failed: {e}")
            raise OllamaError(f"Ollama chat stream failed: {e}") from e