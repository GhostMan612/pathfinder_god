# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""GM encounter trigger tools.

Door, NPC, and loot triggers call the campaign repository directly — the same
service layer behind the generic REST routes — instead of adding a route per
kind. Synthetic data only; no model is contacted.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from app.db.repository import CampaignRepository
from app.llm.orchestrator import (
    ENCOUNTER_TRIGGER_TOOLS,
    SOLO_LOOP_TOOLS,
    LLMOrchestrator,
)


def _setup(tmp_path: Path):
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town = repo.upsert_location(
        campaign.id, "SAMPLE TOWN", type_="settlement"
    )
    repo.set_current_location(campaign.id, town)
    return repo, campaign, town, LLMOrchestrator(repo)


def test_encounter_tools_are_registered() -> None:
    names = {tool["function"]["name"] for tool in SOLO_LOOP_TOOLS}
    assert {
        "trigger_door",
        "trigger_npc",
        "trigger_loot",
        "transition_encounter",
    } <= names
    assert ENCOUNTER_TRIGGER_TOOLS == {
        "trigger_door": "door",
        "trigger_npc": "npc",
        "trigger_loot": "loot",
    }


@pytest.mark.parametrize(
    ("tool_name", "kind"),
    [
        ("trigger_door", "door"),
        ("trigger_npc", "npc"),
        ("trigger_loot", "loot"),
    ],
)
async def test_trigger_tools_create_and_activate(
    tmp_path: Path, tool_name: str, kind: str
) -> None:
    repo, campaign, town, orchestrator = _setup(tmp_path)

    result = await orchestrator.handle_tool_call(
        tool_name,
        {"summary": f"SAMPLE {kind.upper()}", "state": {"sample": True}},
        campaign_id=campaign.id,
    )

    assert result["activated"] is True
    encounter = result["encounter"]
    assert encounter["kind"] == kind
    assert encounter["status"] == "active"
    assert encounter["location_id"] == town
    assert repo.get_active_encounter(campaign.id).id == encounter["id"]
    assert [event.kind for event in repo.list_events(
        campaign.id, encounter_id=encounter["id"]
    )] == ["encounter_created", "encounter_transition"]


async def test_trigger_leaves_pending_when_another_encounter_is_active(
    tmp_path: Path,
) -> None:
    repo, campaign, _town, orchestrator = _setup(tmp_path)
    battle = repo.create_encounter(
        campaign.id, "battle", status="active", summary="SAMPLE BATTLE"
    )

    result = await orchestrator.handle_tool_call(
        "trigger_door",
        {"summary": "SAMPLE IRON DOOR"},
        campaign_id=campaign.id,
    )

    assert result["activated"] is False
    assert result["encounter"]["status"] == "pending"
    assert "already has an active encounter" in result["note"]
    assert repo.get_active_encounter(campaign.id).id == battle.id


async def test_transition_tool_resolves_a_triggered_loot_encounter(
    tmp_path: Path,
) -> None:
    repo, campaign, _town, orchestrator = _setup(tmp_path)
    created = await orchestrator.handle_tool_call(
        "trigger_loot",
        {"summary": "SAMPLE CACHE"},
        campaign_id=campaign.id,
    )
    encounter_id = created["encounter"]["id"]

    resolved = await orchestrator.handle_tool_call(
        "transition_encounter",
        {
            "encounter_id": encounter_id,
            "status": "resolved",
            "summary": "SAMPLE CACHE CLAIMED",
        },
        campaign_id=campaign.id,
    )

    assert resolved["encounter"]["status"] == "resolved"
    stored = repo.get_encounter(campaign.id, encounter_id)
    assert stored is not None
    assert stored.resolved_at is not None


async def test_transition_tool_forwards_the_trap_carve_out(
    tmp_path: Path,
) -> None:
    repo, campaign, _town, orchestrator = _setup(tmp_path)
    trap = repo.create_encounter(campaign.id, "trap", summary="SAMPLE TRAP")

    result = await orchestrator.handle_tool_call(
        "transition_encounter",
        {"encounter_id": trap.id, "status": "resolved", "instant": True},
        campaign_id=campaign.id,
    )

    assert result["encounter"]["status"] == "resolved"
    assert [
        event.kind
        for event in repo.list_events(campaign.id, encounter_id=trap.id)
    ] == ["encounter_created", "hazard_resolved"]


async def test_transition_tool_returns_a_validation_error(
    tmp_path: Path,
) -> None:
    _repo, campaign, _town, orchestrator = _setup(tmp_path)

    result = await orchestrator.handle_tool_call(
        "transition_encounter",
        {"encounter_id": 99999, "status": "resolved"},
        campaign_id=campaign.id,
    )

    assert "no encounter 99999" in result["error"]


class SlowEmbedder:
    """A stand-in OllamaEmbedder whose embed() blocks synchronously.

    Each call sleeps 0.3s the way a real urllib round trip does, so a
    recall that runs on the event loop would freeze it for the whole
    call. The vectors are unit vectors; ranking falls back to the
    lexical RRF boost, which is enough for this test.
    """

    dimensions = 256

    def __init__(self, *args, **kwargs) -> None:
        self.dimensions = int(kwargs.get("dimensions", 256))

    def embed(self, texts: list[str], *, query: bool = False):
        time.sleep(0.3)
        return [(1.0,) + (0.0,) * (self.dimensions - 1) for _ in texts]


async def test_search_sessions_tool_does_not_block_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, campaign, _town, orchestrator = _setup(tmp_path)
    repo.save_session(
        campaign_id=campaign.id,
        session_num=1,
        summary="The party arrived in Falcon's Hollow and took the lumber camp contract.",
        facts=[{"fact": "Contract signed", "category": "quest", "confidence": 1.0}],
        raw_log="Arrived at town gates.",
    )
    repo.save_session(
        campaign_id=campaign.id,
        session_num=2,
        summary="Deep in the Darkmoon Wood, the heroes defeated a pack of rabid timber wolves.",
        facts=[{"fact": "Defeated timber wolves", "category": "mechanic", "confidence": 1.0}],
        raw_log="Tracks led into deep trees.",
    )
    monkeypatch.setattr(
        "app.rag.semantic_spine.ollama.OllamaEmbedder", SlowEmbedder
    )

    ticks = 0
    done = asyncio.Event()

    async def ticker() -> None:
        nonlocal ticks
        while not done.is_set():
            await asyncio.sleep(0.05)
            ticks += 1

    ticker_task = asyncio.create_task(ticker())
    try:
        result = await orchestrator.handle_tool_call(
            "search_sessions",
            {"query": "timber wolves", "campaign_id": campaign.id, "limit": 3},
            campaign_id=campaign.id,
        )
    finally:
        done.set()
        await ticker_task

    # The recall ran (the lexical match finds session 2) and the event
    # loop stayed live while the slow synchronous embedder worked: two
    # embed calls at 0.3s each leave room for ~11 ticks at 0.05s. A
    # recall that blocked the loop would leave at most 1 tick.
    assert result
    assert 2 in [hit["session_num"] for hit in result]
    assert ticks >= 5
