# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Critical FastAPI route tests — 6 essential tests only."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.backends import LLMResult
from app.service import GodService
from app.state.campaign import CampaignStore


class FakeLLM:
    async def complete(self, prompt: str, *, system: str = "", hits=None) -> "LLMResult":
        return LLMResult(text="FAKE ANSWER for: " + prompt[:40], backend="ollama")

    async def stream(self, prompt: str, *, system: str = "", hits=None) -> AsyncIterator[tuple[str, str]]:
        for word in ["The ", "God ", "speaks."]:
            yield ("ollama", word)


# API key for authenticated endpoints
TEST_API_KEY = "pfg_test_key_12345"


@pytest.fixture
def client(rules_db_dir: Path):
    import app.main as main

    test_settings = Settings(
        data_dir=rules_db_dir,
        campaign_state_path=rules_db_dir / "campaign_state.json",
    )
    svc = GodService(test_settings)
    svc._llm = FakeLLM()  # type: ignore[assignment]
    main.settings = test_settings
    main.service = svc
    main.campaign = CampaignStore(test_settings.campaign_state_path)
    return TestClient(main.app)


@pytest.fixture
def authenticated_client(rules_db_dir: Path):
    """Client with a valid API key for authenticated endpoints."""
    import app.main as main
    from app.config import Settings
    from app.service import GodService
    from app.state.campaign import CampaignStore
    from fastapi.testclient import TestClient

    test_settings = Settings(
        data_dir=rules_db_dir,
        campaign_state_path=rules_db_dir / "campaign_state.json",
    )
    svc = GodService(test_settings)
    svc._llm = FakeLLM()
    main.settings = test_settings
    main.service = svc
    main.campaign = CampaignStore(test_settings.campaign_state_path)
    client = TestClient(main.app)
    client.headers["X-API-Key"] = "pfg_test_key_12345"
    return client


# --- Public endpoints (no auth required) ---

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "pathfinder_rag.db" in body["databases_found"]


def test_rules_search(client):
    r = client.get("/rules/search", params={"q": "flanking", "edition": "2e"})
    assert r.status_code == 200
    body = r.json()
    assert body["results"]
    assert body["results"][0]["system"] == "2E"


def test_rules_search_edition_filter(client):
    # 2e only
    r = client.get("/rules/search", params={"q": "flanking", "edition": "2e"})
    assert r.status_code == 200
    assert all(h["system"] == "2E" for h in r.json()["results"])

    # 1e only
    r = client.get("/rules/search", params={"q": "flanking", "edition": "1e"})
    assert r.status_code == 200
    assert all(h["system"] == "1E" for h in r.json()["results"])

    # both - returns 2E results (test DB behavior)
    r = client.get("/rules/search", params={"q": "flanking", "edition": "both"})
    assert r.status_code == 200
    systems = {h["system"] for h in r.json()["results"]}
    assert "2E" in systems


def test_rules_search_empty_query(client):
    r = client.get("/rules/search", params={"q": "", "edition": "2e"})
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_generate_invalid_kind_returns_400(client):
    r = client.post("/generate/notakind", json={"prompt": "test"})
    assert r.status_code == 400


def test_ask_local_only_backend(client):
    r = client.post("/ask", json={"query": "test", "edition": "2e"})
    assert r.status_code == 200
    assert r.json()["backend"] in ("ollama", "raw-excerpts")


# --- Authenticated endpoints (require API key) ---

def test_ask_returns_answer(authenticated_client):
    r = authenticated_client.post("/ask", json={"query": "explain flanking", "edition": "2e"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert body["backend"] == "ollama"


def test_generate_boss_forces_mode(authenticated_client):
    r = authenticated_client.post("/generate/boss", json={"prompt": "a lich sorcerer-king", "edition": "both"})
    assert r.status_code == 200
    assert r.json()["mode"] == "boss"


def test_generate_unknown_kind_autodetects(authenticated_client):
    r = authenticated_client.post("/generate/whatever", json={"prompt": "build me a rogue"})
    assert r.status_code == 200
    assert r.json()["mode"] == "character"


def test_generate_all_kinds(authenticated_client):
    kinds = ["character", "npc", "monster", "boss", "map", "campaign", "encounter"]
    for kind in kinds:
        r = authenticated_client.post(f"/generate/{kind}", json={"prompt": "test", "edition": "2e"})
        assert r.status_code == 200, f"kind={kind} failed"
        assert r.json()["mode"] == kind


def test_campaign_note_roundtrip(authenticated_client):
    authenticated_client.post("/campaign/reset")
    r = authenticated_client.post("/campaign/note", json={"prompt": "met an NPC", "response": "the innkeeper"})
    assert r.status_code == 200
    state = authenticated_client.get("/campaign").json()
    assert "party" in state and "notes" in state


def test_stream_websocket(authenticated_client):
    with authenticated_client.websocket_connect("/stream") as ws:
        ws.send_text('{"query": "explain flanking", "edition": "2e"}')
        first = ws.receive_json()
        assert first["type"] == "start"
        assert first["backend"] == "ollama"

        chunks = []
        while True:
            msg = ws.receive_json()
            if msg["type"] == "chunk":
                chunks.append(msg["text"])
            elif msg["type"] == "end":
                break
        assert "".join(chunks) == "The God speaks."


def test_ask_with_history(authenticated_client):
    r = authenticated_client.post("/ask", json={
        "query": "follow up question",
        "edition": "2e",
        "history": [["user: first", "assistant: answer"]]
    })
    assert r.status_code == 200
    assert "answer" in r.json()


def test_ask_local_only_backend(authenticated_client):
    r = authenticated_client.post("/ask", json={"query": "test", "edition": "2e"})
    assert r.status_code == 200
    assert r.json()["backend"] in ("ollama", "raw-excerpts")


def test_generate_invalid_kind_returns_400(authenticated_client):
    r = authenticated_client.post("/generate/notakind", json={"prompt": "test"})
    assert r.status_code == 400


def test_rules_search_empty_query(authenticated_client):
    r = authenticated_client.get("/rules/search", params={"q": "", "edition": "2e"})
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_generate_invalid_kind_returns_400(client):
    r = client.post("/generate/notakind", json={"prompt": "test"})
    assert r.status_code == 400


def test_rules_search_empty_query(client):
    r = client.get("/rules/search", params={"q": "", "edition": "2e"})
    assert r.status_code == 200
    assert r.json()["results"] == []