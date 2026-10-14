# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""BP-08 Pillar A: abstention must be deterministic, not model-dependent.

The point of these tests is the CALL COUNT. A prompt that merely *asks* a 3B
model to refuse is not a guarantee - it is the exact failure that produced the
invented "DC of 20" and the fabricated Waffle Iron DC. When abstain=True the
lawyer must answer without contacting Ollama at all.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.rules_lawyer import ABSTENTION_TEXT, RulesLawyerAgent


class _ExplodingLLM:
    """Every entry point raises. If the abstention path touches one, the test fails."""

    def __init__(self) -> None:
        self.generate_calls = 0
        self.stream_calls = 0
        self.chat_calls = 0

    async def generate(self, *a, **k):
        self.generate_calls += 1
        raise AssertionError("OllamaClient.generate must not be called when abstaining")

    async def chat(self, *a, **k):
        self.chat_calls += 1
        raise AssertionError("OllamaClient.chat must not be called when abstaining")

    async def stream(self, *a, **k):
        self.stream_calls += 1
        raise AssertionError("OllamaClient.stream must not be called when abstaining")
        yield ""  # pragma: no cover - makes this an async generator


def _agent(llm) -> RulesLawyerAgent:
    agent = RulesLawyerAgent.__new__(RulesLawyerAgent)  # skip __init__ (no httpx)
    agent.ollama = llm
    agent.settings = type("S", (), {"model_for": staticmethod(lambda _k: "stub")})()
    return agent


# ── streaming path ───────────────────────────────────────────────


def test_stream_abstention_makes_zero_llm_calls():
    llm = _ExplodingLLM()
    agent = _agent(llm)

    async def run():
        gen, cites = await agent.stream_adjudication(
            query="What is the DC to bake a cake with the Celestial Waffle Iron?",
            edition="2e",
            context=[],
            abstain=True,
        )
        return [c async for c in gen], cites

    chunks, citations = asyncio.run(run())

    assert chunks == [ABSTENTION_TEXT]
    assert citations == []
    assert llm.stream_calls == 0, "abstention still called stream()"
    assert llm.generate_calls == 0
    assert llm.chat_calls == 0


def test_stream_abstention_ignores_cited_context():
    """abstain=True wins even if rows were passed: no grounding was possible."""
    llm = _ExplodingLLM()
    agent = _agent(llm)

    async def run():
        gen, cites = await agent.stream_adjudication(
            query="Unanswerable?",
            context=[{"source_book": "Core Rulebook", "name": "Tack", "category": "Combat"}],
            abstain=True,
        )
        return [c async for c in gen], cites

    chunks, citations = asyncio.run(run())
    assert chunks == [ABSTENTION_TEXT]
    assert citations == [], "abstention must emit zero citations"
    assert llm.stream_calls == 0


# ── buffered path ────────────────────────────────────────────────


def test_adjudicate_abstention_makes_zero_llm_calls():
    llm = _ExplodingLLM()
    agent = _agent(llm)

    answer, citations = asyncio.run(
        agent.adjudicate(
            query="What is the DC to swim across a fast river?",
            edition="2e",
            context=[],
            abstain=True,
        )
    )

    assert answer == ABSTENTION_TEXT
    assert citations == []
    assert llm.stream_calls == 0
    assert llm.generate_calls == 0
    assert llm.chat_calls == 0


def test_adjudicate_delegates_to_stream_adjudication():
    llm = _ExplodingLLM()
    agent = _agent(llm)
    answer, cites = asyncio.run(
        agent.adjudicate("q", abstain=True)
    )
    assert answer == ABSTENTION_TEXT
    assert cites == []


# ── negative control: the model IS used when we do have grounding ─


def test_non_abstaining_turn_still_reaches_the_model():
    """Guard against over-correcting: a grounded turn must still call the LLM."""

    class _CountingLLM(_ExplodingLLM):
        async def stream(self, *a, **k):
            self.stream_calls += 1
            yield "You may take an Attack action. "

    llm = _CountingLLM()
    agent = _agent(llm)

    async def run():
        gen, cites = await agent.stream_adjudication(
            query="Can I attack?",
            edition="2e",
            context=[{"source_book": "Core Rulebook", "name": "Attack", "category": "Combat"}],
            abstain=False,
        )
        return [c async for c in gen], cites

    chunks, cites = asyncio.run(run())
    assert llm.stream_calls == 1
    assert chunks == ["You may take an Attack action. "]
    assert [c.tag() for c in cites] == ["[Core Rulebook - Attack]"]


def test_refusal_wording_is_the_single_source_of_truth():
    """Both lanes must refuse with the exact same sentence.

    Previously the orchestrator injected an instruction *clause* asking the model
    to say this, while the lawyer emitted it directly. That is the split that let
    the two drift, so the clause is gone; both paths now share ABSTENTION_TEXT.
    """
    from app.agents.rules_lawyer import ABSTENTION_TEXT

    assert "I don't have that rule in my books" in ABSTENTION_TEXT
    assert ABSTENTION_TEXT.strip() == "I don't have that rule in my books."


@pytest.mark.parametrize("prompt", ["", "   "])
def test_abstain_flag_short_circuits_regardless_of_query(prompt):
    llm = _ExplodingLLM()
    agent = _agent(llm)
    answer, cites = asyncio.run(agent.adjudicate(prompt, abstain=True))
    assert answer == ABSTENTION_TEXT
    assert cites == []
    assert llm.stream_calls == 0

def test_orchestrator_ask_path_short_circuits_before_agentic_chat(monkeypatch):
    """BP-08: /ask must not reach Ollama when the gate says abstain.

    Regression guard. This path used to append an instruction clause and then
    call _agentic_chat anyway, so the model was consulted for precisely the
    turns where we had already decided the corpus cannot answer.
    """
    from app.llm.orchestrator import LLMOrchestrator

    class _Settings:
        # rag_enabled=False keeps the retriever out of the picture; the gate is
        # stubbed, so `context` is irrelevant to this test.
        rag_enabled = False
        rag_limit = 5
        ollama_temperature = 0.0
        ollama_num_predict = 256

        @staticmethod
        def model_for(_kind):
            return "stub"

    orch = LLMOrchestrator.__new__(LLMOrchestrator)
    orch.settings = _Settings()
    orch.repo = None

    calls = {"agentic": 0}

    async def _explode_agentic(*a, **k):
        calls["agentic"] += 1
        raise AssertionError("_agentic_chat must not run when abstaining")

    monkeypatch.setattr(LLMOrchestrator, "_needs_tools", staticmethod(lambda _p: True))
    monkeypatch.setattr(LLMOrchestrator, "_should_abstain", staticmethod(lambda *a, **k: True))
    monkeypatch.setattr(orch, "_agentic_chat", _explode_agentic)

    result = asyncio.run(
        orch.generate(
            "What is the DC to bake a cake with the Celestial Waffle Iron?",
            edition="2e",
        )
    )

    assert calls["agentic"] == 0
    assert result.answer == ABSTENTION_TEXT
    assert result.backend == "abstention"
    assert result.sources == []


def test_empty_context_short_circuits_even_without_abstain_flag():
    """No citable row means no grounding, regardless of the caller's flag.

    Makes the guarantee hold for every caller instead of depending on each one
    having run the calibrated gate first.
    """
    llm = _ExplodingLLM()
    agent = _agent(llm)

    answer, cites = asyncio.run(agent.adjudicate("How do I climb a wall?", context=[]))

    assert answer == ABSTENTION_TEXT
    assert cites == []
    assert llm.stream_calls == 0


def test_rows_without_names_do_not_count_as_grounding():
    """A retrieval hit missing `name` is not a citation and cannot ground."""
    llm = _ExplodingLLM()
    agent = _agent(llm)

    answer, cites = asyncio.run(
        agent.adjudicate(
            "How do I climb a wall?",
            context=[{"source_book": "Core", "name": "", "category": ""}],
        )
    )

    assert answer == ABSTENTION_TEXT
    assert cites == []
    assert llm.stream_calls == 0
