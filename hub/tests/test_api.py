# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Critical FastAPI route tests — hermetic: tmp DBs, faked Ollama."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "pfg_test_key_12345"


@pytest.fixture(autouse=True)
def _hermetic_hub(tmp_path: Path, monkeypatch, rules_db_dir: Path):
    import app.config
    from app import main
    from app.api.deps import get_repo
    from app.config import Settings, get_settings
    from app.db.repository import CampaignRepository
    from app.llm.ollama_client import OllamaClient

    test_settings = Settings(
        data_dir=rules_db_dir,
        campaign_state_path=tmp_path / "campaign_state.json"
    )

    monkeypatch.setattr(app.config, "get_settings", lambda: test_settings)

    async def fake_generate(self, **kwargs):
        return "Fake answer from the God."

    async def fake_stream(self, **kwargs):
        yield "Fake "
        yield "answer."

    async def fake_chat(self, *, messages, model=None, tools=None, **kwargs):
        # Needed because a rules-intent turn routes through the ReAct tool loop,
        # which calls OllamaClient.chat. Without this the fixture leaked to the
        # REAL ollama on those turns (the suite took 343s and the assertion saw a
        # live model reply instead of "Fake answer."). Returning tool_calls=[] is
        # the no-tools-needed branch, which is the tool path's own short-circuit.
        return {"role": "assistant", "content": "Fake answer.", "tool_calls": []}

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)
    monkeypatch.setattr(OllamaClient, "stream", fake_stream)
    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    
    main.app.dependency_overrides[get_repo] = lambda: CampaignRepository(
        str(tmp_path / "campaign.db")
    )
    main.app.dependency_overrides[get_settings] = lambda: test_settings
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def client(rules_db_dir: Path):
    from app import main

    return TestClient(main.app)


@pytest.fixture
def authenticated_client(rules_db_dir: Path):
    """Client with a valid API key for authenticated endpoints."""
    from fastapi.testclient import TestClient

    from app import main

    client = TestClient(main.app)
    client.headers["X-API-Key"] = "pfg_test_key_12345"
    return client


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
    r = client.get("/rules/search", params={"q": "flanking", "edition": "2e"})
    assert r.status_code == 200
    assert all(h["system"] == "2E" for h in r.json()["results"])

    r = client.get("/rules/search", params={"q": "flanking", "edition": "1e"})
    assert r.status_code == 200
    assert all(h["system"] == "1E" for h in r.json()["results"])

    r = client.get("/rules/search", params={"q": "flanking", "edition": "both"})
    assert r.status_code == 200
    systems = {h["system"] for h in r.json()["results"]}
    assert "2E" in systems


def test_rules_search_empty_query(client):
    # An empty query is now a 422, not an empty 200: q carries min_length=1, so
    # a blank search is rejected up front instead of being turned into a MATCH
    # expression that could not match. Returning 200 with results=[] was the
    # old behaviour and encoded the missing bound.
    r = client.get("/rules/search", params={"q": "", "edition": "2e"})
    assert r.status_code == 422


def test_generate_invalid_kind_returns_400(client):
    r = client.post("/generate/notakind", json={"prompt": "test"})
    assert r.status_code == 400


def test_ask_local_only_backend(client):
    r = client.post("/ask", json={"query": "test", "edition": "2e"})
    assert r.status_code == 200
    assert r.json()["backend"] in ("ollama", "raw-excerpts")


def test_ask_returns_answer(authenticated_client):
    r = authenticated_client.post("/ask", json={"query": "explain flanking", "edition": "2e"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert body["backend"] == "ollama"


def test_generate_boss_forces_mode(authenticated_client, monkeypatch):
    # /generate/boss is now the typed monster endpoint; a boss is a monster
    # built with the elite template (+2 AC/saves/attack/damage, HP x1.2).
    import json as _json

    from app.llm.ollama_client import OllamaClient

    monster = {
        "name": "SAMPLE LICH",
        "level": 5,
        "creature_type": "undead",
        "traits": ["undead", "evil"],
        "hp": 60,
        "ac": 21,
        "perception": 10,
        "saves": {"fortitude": 10, "reflex": 8, "will": 11},
        "strikes": [
            {"name": "Claw", "attack_bonus": 12, "damage": "1d8+4", "damage_type": "slashing"}
        ],
        "abilities": ["Paralyzing Touch"],
        "tactics": "It fights from range, then closes in.",
        "loot_table": ["Phylactery"],
    }

    async def fake_monster_json(self, **kwargs):
        return _json.dumps(monster)

    monkeypatch.setattr(OllamaClient, "generate", fake_monster_json)
    r = authenticated_client.post("/generate/boss", json={"prompt": "a lich sorcerer-king", "level": 5})
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body["valid"] is True
    assert body["monster"]["template"] == "elite"
    assert body["monster"]["ac"] == monster["ac"] + 2
    assert body["monster"]["hp"] == int(monster["hp"] * 1.2)


def test_generate_unknown_kind_returns_400_with_valid_kinds(authenticated_client):
    r = authenticated_client.post("/generate/whatever", json={"prompt": "build me a rogue"})
    assert r.status_code == 400
    assert "character" in r.json()["detail"]


def test_generate_all_kinds(authenticated_client):
    # Prose kinds still flow through /generate/{kind}. npc, monster and
    # boss are typed endpoints now (POST /generate/npc, /generate/monster,
    # /generate/boss) and are covered by their dedicated builder tests.
    kinds = ["map", "campaign", "encounter"]
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

        # BP-08 Pillar B: a rules turn is forwarded verbatim from the Rules
        # Lawyer, then the deterministic Sources block is appended from the
        # retrieval rows. The body must still be exactly what the model
        # emitted - no GM re-narration pass - and the citation must be the
        # real matched row rather than anything the model wrote.
        answer = "".join(chunks)
        assert answer.startswith("Fake answer.")
        assert "\n\nSources:\n- [Core Rulebook - Flanking]" in answer


def test_rules_turn_is_not_re_narrated(authenticated_client, monkeypatch):
    """A rules turn must bypass the GM narrative model entirely.

    The bug this pins: a rules question was answered by the Rules Lawyer and then
    handed to a second model pass to re-narrate it, which stripped mechanical
    nuance and rewrote citation tags.

    `OllamaClient.stream` is called by BOTH the lawyer's verbatim forward and the
    GM narration branch, so counting calls is what actually distinguishes them:
    a correct rules turn calls it exactly once (the lawyer). If the short-circuit
    `return` is removed, control falls through to the narration `async for` and
    calls it a second time - which this asserts against. Counting `chat`/
    `generate` alone is not enough: neither narration nor the lawyer uses them.
    """
    from app.llm.ollama_client import OllamaClient

    calls = {"stream": 0, "chat": 0, "generate": 0}

    async def spy_stream(self, **kwargs):
        calls["stream"] += 1
        yield "Fake "
        yield "answer."

    async def spy_chat(self, **kwargs):
        calls["chat"] += 1
        return {"role": "assistant", "content": "RE-NARRATED", "tool_calls": []}

    async def spy_generate(self, *args, **kwargs):
        calls["generate"] += 1
        return "RE-NARRATED"

    monkeypatch.setattr(OllamaClient, "stream", spy_stream)
    monkeypatch.setattr(OllamaClient, "chat", spy_chat)
    monkeypatch.setattr(OllamaClient, "generate", spy_generate)

    with authenticated_client.websocket_connect("/stream") as ws:
        ws.send_text('{"query": "explain flanking", "edition": "2e"}')
        while True:
            msg = ws.receive_json()
            if msg["type"] == "end":
                break

    assert calls["chat"] == 0, "rules turn re-entered the GM/tool model"
    assert calls["generate"] == 0, "rules turn called the buffered generate path"
    assert calls["stream"] == 1, (
        f"rules turn streamed {calls['stream']} times; expected exactly 1 "
        "(the lawyer verbatim forward). More than one means it fell through to "
        "the GM narration branch and the short-circuit return was lost."
    )


def test_stream_adjudication_yields_verbatim_and_citations(rules_db_dir: Path):
    """The lawyer returns a lazy stream plus deterministic citations.

    A concatenated string cannot satisfy the no-re-narration contract, so the
    return type itself is part of what is being tested.
    """
    import inspect

    from app.agents.rules_lawyer import Citation, RulesLawyerAgent
    from app.config import Settings
    from app.db.repository import CampaignRepository

    monkey = pytest.MonkeyPatch()
    try:
        import app.config as _cfg

        monkey.setattr(
            _cfg,
            "get_settings",
            lambda: Settings(
                data_dir=rules_db_dir,
                campaign_state_path=rules_db_dir / "campaign_state.json",
            ),
        )
        agent = RulesLawyerAgent(CampaignRepository(str(rules_db_dir / "campaign.db")))

        async def collect():
            gen, cites = await agent.stream_adjudication(
                query="explain flanking",
                edition="2e",
                context=[
                    {"source_book": "Core Rulebook", "name": "Flanking", "category": "Combat"}
                ],
                abstain=False,
            )
            # Must be an async generator, and citations must be available
            # before the body is consumed.
            assert inspect.isasyncgen(gen)
            assert [c.tag() for c in cites] == ["[Core Rulebook - Flanking]"]
            assert isinstance(cites[0], Citation)
            return [c async for c in gen]

        out = asyncio.run(collect())
        # "Fake answer." from the class-level stream mock, chunk for chunk.
        assert "".join(out) == "Fake answer."
    finally:
        monkey.undo()


def test_ask_with_history(authenticated_client):
    r = authenticated_client.post("/ask", json={
        "query": "follow up question",
        "edition": "2e",
        "history": [["user: first", "assistant: answer"]]
    })
    assert r.status_code == 200
    assert "answer" in r.json()