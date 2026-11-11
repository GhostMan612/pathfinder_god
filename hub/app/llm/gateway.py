# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""The single HTTP gateway to Ollama.

The laptop runs one resident model, so every generation is serialized through a
priority queue and a semaphore. Interactive turns enqueue at priority 0; builder
and other background jobs enqueue at priority 1. Queue overflow blocks the
producer instead of dropping work. Builder/JSON/rules results are cached; chat,
GM, and narration results are never cached because the same prompt must be able
to produce a different scene.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import itertools
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

INTERACTIVE_PRIORITY = 0
BACKGROUND_PRIORITY = 1
CACHEABLE_TASKS = frozenset(
    {"builder", "builders", "json", "rules", "reasoning"}
)


@dataclass(order=True)
class _Ticket:
    priority: int
    sequence: int
    future: asyncio.Future[None] = field(compare=False, repr=False)


class LlmGateway:
    """Priority queue + semaphore + cache in front of Ollama's HTTP API."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._s = settings or get_settings()
        self._queue: asyncio.PriorityQueue[_Ticket] = asyncio.PriorityQueue(
            maxsize=max(1, int(self._s.llm_gateway_queue_limit))
        )
        self._semaphore = asyncio.Semaphore(
            max(1, int(self._s.llm_gateway_max_inflight))
        )
        self._sequence = itertools.count()
        self._dispatcher: asyncio.Task[None] | None = None
        self._client_factory = client_factory
        self._client: Any | None = None
        self._cache: dict[str, tuple[float, str]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._waiting = 0
        self._cancelled = 0
        self._started = 0

    # ── admission control ────────────────────────────────────────────────

    def _ensure_dispatcher(self) -> None:
        if self._dispatcher is None or self._dispatcher.done():
            self._dispatcher = asyncio.create_task(
                self._dispatch_loop(), name="llm-gateway-dispatcher"
            )

    async def _dispatch_loop(self) -> None:
        while True:
            await self._semaphore.acquire()
            ticket = await self._queue.get()
            if ticket.future.done():
                self._semaphore.release()
                continue
            try:
                ticket.future.set_result(None)
            except asyncio.InvalidStateError:
                # Defensive: the waiter was cancelled between the done()
                # check and set_result. Release the permit we acquired for
                # it and keep dispatching instead of dying here and
                # deadlocking the queue.
                self._semaphore.release()
                continue

    @asynccontextmanager
    async def _slot(self, priority: int):
        self._ensure_dispatcher()
        future: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )
        ticket = _Ticket(
            priority=max(0, int(priority)),
            sequence=next(self._sequence),
            future=future,
        )
        await self._queue.put(ticket)
        self._waiting += 1
        try:
            await future
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            if future.done() and not future.cancelled():
                # The dispatcher already handed us a slot: it acquired the
                # semaphore and set this future's result, but the
                # cancellation landed before we resumed, so we never reach
                # the yield whose finally releases the permit. Release it
                # here or the gateway deadlocks once max_inflight is
                # exhausted.
                self._semaphore.release()
            self._waiting = max(0, self._waiting - 1)
            self._cancelled += 1
            logger.info(
                "LLM gateway ticket cancelled priority=%s waiting=%s",
                ticket.priority,
                self._waiting,
            )
            raise
        self._waiting = max(0, self._waiting - 1)
        self._started += 1
        try:
            yield
        finally:
            self._semaphore.release()

    # ── cache ────────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(
        model: str,
        prompt: str,
        system: str,
        task: str,
        fmt: str | None,
    ) -> str:
        raw = "\x00".join((model, prompt, system, task, fmt or ""))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> str | None:
        item = self._cache.get(key)
        now = time.monotonic()
        if item is None:
            self._cache_misses += 1
            return None
        expires_at, value = item
        if expires_at <= now:
            self._cache.pop(key, None)
            self._cache_misses += 1
            return None
        self._cache_hits += 1
        return value

    def _cache_put(self, key: str, value: str) -> None:
        if not value:
            return
        limit = max(1, int(self._s.llm_gateway_cache_max_entries))
        if len(self._cache) >= limit:
            oldest = next(iter(self._cache), None)
            if oldest is not None:
                self._cache.pop(oldest, None)
        expires_at = time.monotonic() + max(
            0.0, float(self._s.llm_gateway_cache_ttl_s)
        )
        self._cache[key] = (expires_at, value)

    # ── HTTP client ──────────────────────────────────────────────────────

    async def _get_client(self) -> Any:
        if self._client is None:
            if self._client_factory is not None:
                client = self._client_factory()
                if inspect.isawaitable(client):
                    client = await client
                self._client = client
            else:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self._s.ollama_timeout_s),
                    trust_env=False,
                )
        return self._client

    async def _post_generate(self, payload: dict[str, Any]) -> str:
        client = await self._get_client()
        resp = await client.post(
            f"{self._s.ollama_host}/api/generate", json=payload
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    # ── public API ───────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.6,
        num_predict: int = 700,
        format: str | None = None,
        task: str = "chat",
        priority: int = INTERACTIVE_PRIORITY,
    ) -> str:
        model = model or self._s.ollama_model
        cache_key = None
        if task in CACHEABLE_TASKS:
            cache_key = self._cache_key(model, prompt, system, task, format)
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        if format:
            payload["format"] = format
        async with self._slot(priority):
            text = await self._post_generate(payload)
        if cache_key is not None:
            self._cache_put(cache_key, text)
        return text

    async def stream(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.6,
        num_predict: int = 700,
        task: str = "chat",
        priority: int = INTERACTIVE_PRIORITY,
    ) -> AsyncGenerator[str, None]:
        model = model or self._s.ollama_model
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        async with self._slot(priority):
            client = await self._get_client()
            async with client.stream(
                "POST", f"{self._s.ollama_host}/api/generate", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    chunk = obj.get("response")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.6,
        num_predict: int = 700,
        task: str = "chat",
        priority: int = INTERACTIVE_PRIORITY,
    ) -> dict[str, Any]:
        model = model or self._s.ollama_model
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
        async with self._slot(priority):
            client = await self._get_client()
            resp = await client.post(
                f"{self._s.ollama_host}/api/chat", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", data)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        task: str = "chat",
        priority: int = INTERACTIVE_PRIORITY,
    ) -> AsyncGenerator[dict[str, Any], None]:
        model = model or self._s.ollama_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        async with self._slot(priority):
            client = await self._get_client()
            async with client.stream(
                "POST", f"{self._s.ollama_host}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except ValueError:
                        continue
                    if "message" in data:
                        yield data["message"]
                    if data.get("done"):
                        break

    async def embeddings(
        self,
        text: str,
        *,
        model: str = "nomic-embed-text",
        task: str = "embeddings",
        priority: int = BACKGROUND_PRIORITY,
    ) -> list[float]:
        payload = {"model": model, "prompt": text}
        async with self._slot(priority):
            client = await self._get_client()
            resp = await client.post(
                f"{self._s.ollama_host}/api/embeddings", json=payload
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])

    async def tags(self) -> dict[str, Any]:
        """Readiness probe; bypasses the generation queue on purpose."""
        client = await self._get_client()
        resp = await client.get(
            f"{self._s.ollama_host}/api/tags", timeout=3.0
        )
        resp.raise_for_status()
        return resp.json()

    def stats(self) -> dict[str, int]:
        return {
            "waiting": self._waiting,
            "started": self._started,
            "cancelled": self._cancelled,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_entries": len(self._cache),
        }

    async def close(self) -> None:
        if self._dispatcher is not None:
            self._dispatcher.cancel()
            try:
                await self._dispatcher
            except asyncio.CancelledError:
                pass
            self._dispatcher = None
        client = self._client
        self._client = None
        if client is not None:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                result = aclose()
                if inspect.isawaitable(result):
                    await result


@lru_cache(maxsize=1)
def get_gateway() -> LlmGateway:
    """Process-wide gateway so every caller shares one queue and cache."""
    return LlmGateway(get_settings())
