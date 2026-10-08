# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""The ReAct tool loop executes real tool results end to end (WP-A).

These tests exist because the loop was previously unexecuted: every fake in
the suite returned tool_calls=[], so a TypeError in the tool-result
serialization and AttributeErrors in the NPC tool dispatch shipped unnoticed.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from app.db.repository import CampaignRepository
from app.llm.orchestrator import LLMOrchestrator


def _make_orchestrator(db_path: Path) -> LLMOrchestrator:
    repo = CampaignRepository(str(db_path))
    return LLMOrchestrator(repo)


async def test_agentic_chat_serializes_dataclass_tool_results(rules_db_dir, tmp_path: Path) -> None:
    orch = _make_orchestrator(tmp_path / "campaign.db")
    msg1 = {
        "content": "",
        "tool_calls": [
            {"function": {"name": "lookup_rule", "arguments": json.dumps({"query": "fireball"})}}
        ],
    }
    msg3 = {"content": "Fireball deals 1d6 fire damage per caster level."}
    orch.ollama.chat = AsyncMock(side_effect=[msg1, msg3])
    answer = await orch._agentic_chat(
        "what does fireball do?", "system", "what does fireball do?", "2e", []
    )
    assert answer == "Fireball deals 1d6 fire damage per caster level."


async def test_save_npc_tool_persists_with_campaign_id(rules_db_dir, tmp_path: Path) -> None:
    orch = _make_orchestrator(tmp_path / "campaign.db")
    result = await orch.handle_tool_call(
        "save_npc_to_db",
        {
            "npc_json": {
                "name": "SAMPLE NPC B",
                "level": 3,
                "ancestry": "Human",
                "class_": "Fighter",
                "personality": "stoic",
                "hooks": ["owes the party"],
            }
        },
        campaign_id=7,
    )
    assert result.get("saved") is True
    npc = orch.repo.get_npc(7, "SAMPLE NPC B")
    assert npc is not None and npc.level == 3
    assert orch.repo.get_npc(1, "SAMPLE NPC B") is None


async def test_level_up_tool_raises_level_and_returns_new_level(rules_db_dir, tmp_path: Path) -> None:
    orch = _make_orchestrator(tmp_path / "campaign.db")
    await orch.handle_tool_call(
        "save_npc_to_db",
        {"npc_json": {"name": "SAMPLE NPC C", "level": 2}},
        campaign_id=3,
    )
    npc = orch.repo.get_npc(3, "SAMPLE NPC C")
    assert npc is not None
    result = await orch.handle_tool_call("level_up", {"character_id": npc.id}, campaign_id=3)
    assert result.get("leveled_up") is True
    assert result.get("new_level") == 3
    assert orch.repo.get_npc(3, "SAMPLE NPC C").level == 3


async def test_level_up_missing_npc_returns_error(rules_db_dir, tmp_path: Path) -> None:
    orch = _make_orchestrator(tmp_path / "campaign.db")
    result = await orch.handle_tool_call("level_up", {"character_id": 999}, campaign_id=1)
    assert "error" in result


async def test_tool_failure_returns_error_dict(rules_db_dir, tmp_path: Path) -> None:
    orch = _make_orchestrator(tmp_path / "campaign.db")
    result = await orch.handle_tool_call(
        "calculate_dc", {"level": "not-a-number"}, campaign_id=1
    )
    assert "error" in result
