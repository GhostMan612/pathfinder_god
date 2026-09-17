# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for ContinuityAgent session summarization."""

import pytest

from app.agents.continuity import ContinuityAgent


CANNED_SUMMARY = (
    "The mist parted over the ruined tavern as the party closed in. "
    "Steel rang against chitin while the pit trap claimed its due.\n\n"
    "When silence fell, the heroes counted their wounds and their spoils, "
    "unaware of the eyes watching from the cellar dark."
)


class _FakeLlm:
    def __init__(self, payload: str = CANNED_SUMMARY, fail: bool = False):
        self._payload = payload
        self._fail = fail
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail:
            raise ConnectionError("ollama unreachable")
        return self._payload


EVENTS = [
    "Defeated 3 goblin warriors in the tavern common room",
    "Valeros dropped to 8 HP from a pit trap",
    "Found a hidden cache behind the cellar trapdoor",
]


class TestSummarizeSession:
    @pytest.mark.asyncio
    async def test_summary_generation_with_mocked_llm(self):
        agent = ContinuityAgent(_FakeLlm())
        journal = await agent.summarize_session(EVENTS, "Abomination Vaults")
        assert journal.summary == CANNED_SUMMARY
        assert journal.event_count == 3
        assert journal.campaign_name == "Abomination Vaults"

    @pytest.mark.asyncio
    async def test_prompt_contains_chronicler_brief_and_events(self):
        llm = _FakeLlm()
        agent = ContinuityAgent(llm)
        await agent.summarize_session(EVENTS, "Abomination Vaults")
        prompt = llm.calls[0]["prompt"]
        assert "chronicler" in prompt.lower()
        assert "2-paragraph" in prompt
        assert "goblin warriors" in prompt
        assert "Abomination Vaults" in prompt

    @pytest.mark.asyncio
    async def test_empty_events_returns_empty_journal(self):
        agent = ContinuityAgent(_FakeLlm())
        journal = await agent.summarize_session(["  ", ""], "Abomination Vaults")
        assert journal.summary == ""
        assert journal.event_count == 0

    @pytest.mark.asyncio
    async def test_llm_failure_degrades_gracefully(self):
        agent = ContinuityAgent(_FakeLlm(fail=True))
        journal = await agent.summarize_session(EVENTS, "Abomination Vaults")
        assert journal.summary == ""
        assert journal.event_count == 3
