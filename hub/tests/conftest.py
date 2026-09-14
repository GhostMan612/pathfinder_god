# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Shared test fixtures — a tiny FTS5 rules DB standing in for the 500MB real one."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.service import GodService
from app.state.campaign import CampaignStore
import app.main as main


# Sample rules across both editions, matching the primary `rules` FTS5 schema.
_SAMPLE_ROWS = [
    ("2e", "action", "Flanking",
     "Core Rulebook",
     "When you and an ally are on opposite sides of a foe, that foe is off-guard to melee attacks."),
    ("1e", "combat", "Flanking",
     "Core Rulebook 1e",
     "A creature threatened by two foes on opposite sides is flanked, granting +2 to attack."),
    ("2e", "monster", "Goblin Warrior",
     "Bestiary",
     "A small, quick goblin that fights with a dogslicer and shortbow; skittish but vicious in numbers."),
    ("1e", "spell", "Fireball",
     "Core Rulebook 1e",
     "A blast of fire deals 1d6 fire damage per caster level to all creatures in a 20-ft radius."),
    ("2e", "feat", "Power Attack",
     "Core Rulebook",
     "Make a melee Strike with a penalty to accuracy for extra damage on a hit."),
]


def _build_rules_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE VIRTUAL TABLE rules USING fts5(system, category, name, source_book, raw_content)"
    )
    conn.executemany(
        "INSERT INTO rules (system, category, name, source_book, raw_content) VALUES (?,?,?,?,?)",
        _SAMPLE_ROWS,
    )
    conn.commit()
    conn.close()


def _create_test_client(rules_db_dir: Path) -> TestClient:
    """Create a test client with a fake LLM that bypasses auth.

    Gemini §15.10: FakeLLM overrides orchestrator._agentic_chat + generate to avoid
    waiting for real Ollama (phi4-mini/qwen2.5 5-11 tok/s). Tests hit G1-9 gates in ms.
    """
    test_settings = Settings(
        data_dir=rules_db_dir,
        campaign_state_path=rules_db_dir / "campaign_state.json",
    )
    svc = GodService(test_settings)

    class FakeLLM:
        async def complete(self, prompt: str, *, system: str = "", hits=None):
            from app.llm.backends import LLMResult
            return LLMResult(text="FAKE ANSWER for: " + prompt[:40], backend="ollama")

        async def stream(self, prompt: str, *, system: str = "", hits=None):
            for word in ["The ", "God ", "speaks."]:
                yield ("ollama", word)

    # Also fake the orchestrator's ReAct tool loop (qwen2.5 path) —
    # prevents tests from hitting real /api/chat which needs Ollama.
    from unittest.mock import AsyncMock

    async def fake_agentic_chat(prompt, system, original_prompt, edition, tools):
        # Simulate tool_calls for validate_action / lookup_rule then final narrative
        return "FAKE AGENTIC ANSWER with tool loop (level dc cited)"

    svc._orchestrator = getattr(svc, "_orchestrator", None) or getattr(svc, "orchestrator", None)
    # GodService uses self.orchestrator or self._llm; patch both
    try:
        from app.llm.orchestrator import LLMOrchestrator
        # If service exposes orchestrator, mock its _agentic_chat
        if hasattr(svc, "orchestrator"):
            svc.orchestrator._agentic_chat = fake_agentic_chat
        if hasattr(svc, "_orchestrator") and svc._orchestrator is not None:
            svc._orchestrator._agentic_chat = fake_agentic_chat
    except Exception:
        pass

    # Patch ollama_client.chat too for direct /generate tests
    try:
        from app.llm.ollama_client import OllamaClient
        svc._llm = FakeLLM()
        # Monkey-patch OllamaClient.chat globally for this process
        OllamaClient.chat = AsyncMock(return_value={"role": "assistant", "content": "FAKE CHAT", "tool_calls": []})
    except Exception:
        pass

    if not hasattr(svc, "_llm") or svc._llm is None:
        svc._llm = FakeLLM()
    else:
        # Ensure existing LLM stays fake
        svc._llm = FakeLLM()

    # Swap the module globals the route handlers close over.
    main.settings = test_settings
    main.service = svc
    main.campaign = CampaignStore(test_settings.campaign_state_path)

    return TestClient(main.app)


@pytest.fixture
def rules_db_dir(tmp_path: Path) -> Path:
    """A temp data dir containing a `pathfinder_rag.db` with sample rules."""
    _build_rules_db(tmp_path / "pathfinder_rag.db")
    return tmp_path


@pytest.fixture
def settings(rules_db_dir: Path):
    from app.config import Settings

    return Settings(data_dir=rules_db_dir, campaign_state_path=rules_db_dir / "campaign_state.json")


@pytest.fixture
def client(rules_db_dir: Path):
    return _create_test_client(rules_db_dir)


@pytest.fixture
def authenticated_client(rules_db_dir: Path) -> TestClient:
    """Client with a valid API key for authenticated endpoints."""
    client = _create_test_client(rules_db_dir)
    # Add a valid API key to the client's headers
    client.headers["X-API-Key"] = "pfg_test_key_12345"
    return client