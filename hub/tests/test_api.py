# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Critical FastAPI route tests — hermetic: tmp DBs, faked Ollama."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# API key for authenticated endpoints
TEST_API_KEY = "pfg_test_key_12345"


@pytest.fixture(autouse=True)
def _hermetic_hub(tmp_path: Path, monkeypatch):
    import app.main as main
    from app.api.deps import get_repo
    from app.db.repository import CampaignRepository
    from app.llm.ollama_client import OllamaClient

    async def fake_generate(self, **kwargs):
        return "Fake answer from the God."

    async def fake_stream(self, **kwargs):
        yield "Fake "
        yield "answer."

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)
    monkeypatch.setattr(OllamaClient, "stream", fake_stream)
    main.app.dependency_overrides[get_repo] = lambda: CampaignRepository(
        str(tmp_path / "campaign.db")
    )
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def client(rules_db_dir: Path):
    import app.main as main

    return TestClient(main.app)


@pytest.fixture
def authenticated_client(rules_db_dir: Path):
    """Client with a valid API key for authenticated endpoints."""
    import app.main as main
    from fastapi.testclient import TestClient

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


def test_generate_unknown_kind_returns_400_with_valid_kinds(authenticated_client):
    r = authenticated_client.post("/generate/whatever", json={"prompt": "build me a rogue"})
    assert r.status_code == 400
    assert "character" in r.json()["detail"]


def test_generate_all_kinds(authenticated_client):
    kinds = ["npc", "monster", "boss", "map", "campaign", "encounter"]
    for kind in kinds:
        r = authenticated_client.post(f"/generate/{kind}", json={"prompt": "test", "edition": "2e"})
        assert r.status_code == 200, f"kind={kind} failed"
        assert r.json()["mode"] == kind


def test_generate_character_dedicated_route(authenticated_client, monkeypatch):
    import json as _json

    from app.llm.ollama_client import OllamaClient

    character = {
        "name": "Valeros",
        "ancestry": "Human",
        "heritage": "",
        "background": "Guard",
        "character_class": "Fighter",
        "level": 1,
        "abilities": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 12, "cha": 10},
        "proficiencies": {
            "skills": {"athletics": 1, "stealth": 1, "arcana": 1},
            "defenses": {"martialWeapons": 1},
            "classProfs": {},
        },
    }

    async def fake_character_json(self, **kwargs):
        return _json.dumps(character)

    monkeypatch.setattr(OllamaClient, "generate", fake_character_json)
    r = authenticated_client.post("/generate/character", json={"prompt": "human fighter"})
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body["valid"] is True
    assert body["character"]["name"] == "Valeros"


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
        assert "".join(chunks) == "Fake answer."


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