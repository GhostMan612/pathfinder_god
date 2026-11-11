# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""LLM gateway: priority, cap, cache, and cancellation.

Uses a fake HTTP client so no Ollama process or network is required.
"""
from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.llm.gateway import INTERACTIVE_PRIORITY, LlmGateway


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *, block_prompt: str | None = None):
        self.calls: list[str] = []
        self.active = 0
        self.max_active = 0
        self.block_prompt = block_prompt
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def post(self, url, json=None):
        prompt = (json or {}).get("prompt", "")
        self.calls.append(prompt)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if prompt == self.block_prompt:
            self.started.set()
            await self.release.wait()
        else:
            await asyncio.sleep(0.01)
        self.active -= 1
        return _Response({"response": f"answer:{prompt}"})

    async def get(self, url, timeout=None):
        return _Response({"models": []})

    async def aclose(self):
        return None


def _settings(**overrides) -> Settings:
    values = {
        "llm_gateway_max_inflight": 1,
        "llm_gateway_queue_limit": 10,
        "llm_gateway_cache_ttl_s": 60.0,
        "llm_gateway_cache_max_entries": 16,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_interactive_jumps_queued_background_job():
    client = _FakeClient(block_prompt="bg1")
    gateway = LlmGateway(_settings(), client_factory=lambda: client)
    try:
        bg1 = asyncio.create_task(
            gateway.generate("bg1", task="chat", priority=1)
        )
        await asyncio.wait_for(client.started.wait(), timeout=2)

        bg2 = asyncio.create_task(
            gateway.generate("bg2", task="chat", priority=1)
        )
        await asyncio.sleep(0.02)
        interactive = asyncio.create_task(
            gateway.generate(
                "interactive",
                task="chat",
                priority=INTERACTIVE_PRIORITY,
            )
        )
        await asyncio.sleep(0.02)
        client.release.set()
        await asyncio.wait_for(
            asyncio.gather(bg1, bg2, interactive), timeout=2
        )

        assert client.calls == ["bg1", "interactive", "bg2"]
    finally:
        await gateway.close()


@pytest.mark.asyncio
async def test_semaphore_serializes_generations():
    client = _FakeClient()
    gateway = LlmGateway(_settings(), client_factory=lambda: client)
    try:
        await asyncio.wait_for(
            asyncio.gather(
                gateway.generate("one", task="chat"),
                gateway.generate("two", task="chat"),
                gateway.generate("three", task="chat"),
            ),
            timeout=2,
        )
        assert client.max_active == 1
        assert len(client.calls) == 3
    finally:
        await gateway.close()


@pytest.mark.asyncio
async def test_builder_cache_hit_avoids_second_http_call():
    client = _FakeClient()
    gateway = LlmGateway(_settings(), client_factory=lambda: client)
    try:
        first = await gateway.generate(
            "same prompt",
            task="builder",
            format="json",
        )
        second = await gateway.generate(
            "same prompt",
            task="builder",
            format="json",
        )
        assert first == second == "answer:same prompt"
        assert client.calls == ["same prompt"]
        assert gateway.stats()["cache_hits"] == 1
    finally:
        await gateway.close()


@pytest.mark.asyncio
async def test_cache_key_includes_sampling_settings():
    client = _FakeClient()
    gateway = LlmGateway(_settings(), client_factory=lambda: client)
    try:
        await gateway.generate(
            "same prompt", task="builder", format="json", temperature=0.6
        )
        # Same prompt, different temperature: a fresh generation, not a
        # cache hit from the first call.
        await gateway.generate(
            "same prompt", task="builder", format="json", temperature=0.9
        )
        assert client.calls == ["same prompt", "same prompt"]
        assert gateway.stats()["cache_hits"] == 0
        # Same prompt and same sampling as the first call: a cache hit.
        await gateway.generate(
            "same prompt", task="builder", format="json", temperature=0.6
        )
        assert client.calls == ["same prompt", "same prompt"]
        assert gateway.stats()["cache_hits"] == 1
        # Same prompt and temperature, different num_predict: fresh again.
        await gateway.generate(
            "same prompt",
            task="builder",
            format="json",
            temperature=0.6,
            num_predict=100,
        )
        assert len(client.calls) == 3
        assert gateway.stats()["cache_hits"] == 1
    finally:
        await gateway.close()


@pytest.mark.asyncio
async def test_chat_is_never_cached():
    client = _FakeClient()
    gateway = LlmGateway(_settings(), client_factory=lambda: client)
    try:
        await gateway.generate("narration", task="chat")
        await gateway.generate("narration", task="chat")
        assert client.calls == ["narration", "narration"]
        assert gateway.stats()["cache_hits"] == 0
    finally:
        await gateway.close()


@pytest.mark.asyncio
async def test_cache_expires_after_ttl():
    client = _FakeClient()
    gateway = LlmGateway(
        _settings(llm_gateway_cache_ttl_s=0.01),
        client_factory=lambda: client,
    )
    try:
        await gateway.generate("expiring", task="rules")
        await asyncio.sleep(0.03)
        await gateway.generate("expiring", task="rules")
        assert client.calls == ["expiring", "expiring"]
        assert gateway.stats()["cache_hits"] == 0
    finally:
        await gateway.close()


@pytest.mark.asyncio
async def test_cancel_while_waiting_releases_slot():
    client = _FakeClient(block_prompt="held")
    gateway = LlmGateway(_settings(), client_factory=lambda: client)
    try:
        held = asyncio.create_task(
            gateway.generate("held", task="chat", priority=1)
        )
        await asyncio.wait_for(client.started.wait(), timeout=2)
        queued = asyncio.create_task(
            gateway.generate("queued", task="chat", priority=1)
        )
        await asyncio.sleep(0.02)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        client.release.set()
        await asyncio.wait_for(held, timeout=2)

        # The cancelled ticket must not leak a semaphore permit.
        assert (
            await asyncio.wait_for(
                gateway.generate("after", task="chat"), timeout=2
            )
            == "answer:after"
        )
        assert gateway.stats()["cancelled"] == 1
    finally:
        await gateway.close()
