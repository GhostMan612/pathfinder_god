# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""BP-08 Pillar C (calibrated router) + Pillar A (abstention gate) tests.

Pure and hermetic: the scorer and the abstention gate are deterministic
functions, so no Ollama, no database and no network are involved.
"""

from __future__ import annotations

import pytest

from app.llm.orchestrator import LLMOrchestrator


@pytest.fixture
def gate():
    """Expose the two gate methods bound to a bare instance.

    Constructing a real LLMOrchestrator would build httpx clients; these
    methods only read class-level regexes, so a stub is enough and keeps the
    test hermetic.
    """

    class _Probe:
        _should_abstain = LLMOrchestrator._should_abstain
        _retrieval_confident = LLMOrchestrator._retrieval_confident
        _NUMERIC_QUESTION = LLMOrchestrator._NUMERIC_QUESTION
        _RULES_STRONG = LLMOrchestrator._RULES_STRONG
        _RULES_WEAK = LLMOrchestrator._RULES_WEAK
        _RULES_INTENT = LLMOrchestrator._RULES_INTENT
        _NARRATIVE = LLMOrchestrator._NARRATIVE
        _MECHANICAL_QUESTION = LLMOrchestrator._MECHANICAL_QUESTION
        _rules_score = LLMOrchestrator._rules_score
        _RULES_THRESHOLD = LLMOrchestrator._RULES_THRESHOLD

    return _Probe()


def routes(q: str) -> bool:
    return LLMOrchestrator._rules_score(q) >= LLMOrchestrator._RULES_THRESHOLD


# ── Pillar C: must route to the Rules Lawyer ─────────────────────


@pytest.mark.parametrize(
    "query",
    [
        "What is the DC to swim across a fast river?",
        "How does grappling work mechanically?",
        "Can I take two attacks of opportunity?",
        "What happens if I fall prone?",
        "Can I swim in chain mail?",
        "How much damage does a longsword do?",
        "Is grappling a legal action?",
        "What is my armor class with a shield?",
        "What are the rules for crits?",
        "Does a shield give me a bonus to AC?",
    ],
)
def test_mechanical_questions_route_to_rules(query: str):
    assert routes(query), f"missed a rules question: {query!r}"


# ── Pillar C: must NOT be routed to the Rules Lawyer ─────────────


@pytest.mark.parametrize(
    "query",
    [
        "I attack the goblin with my sword.",
        "We sneak into the dark cave.",
        "The dragon breathes fire at us.",
        "I open the vault door and step inside.",
        "He looks at me suspiciously.",
        "We run for our lives!",
        "I push the heavy door open.",
        "I swing at the bandit and roll for damage.",
    ],
)
def test_narrative_turns_stay_with_the_gm(query: str):
    assert not routes(query), f"over-routed a narrative turn: {query!r}"


def test_router_is_deterministic_and_cheap():
    """No LLM round-trip: same input, same score, no I/O."""
    q = "What is the DC to swim across a fast river?"
    first = LLMOrchestrator._rules_score(q)
    second = LLMOrchestrator._rules_score(q)
    assert first == second >= LLMOrchestrator._RULES_THRESHOLD
    assert LLMOrchestrator._rules_score("") == 0
    assert LLMOrchestrator._rules_score("   ") == 0


# ── Pillar A: abstention gate ────────────────────────────────────


def test_abstains_when_retrieval_is_empty(gate):
    assert gate._should_abstain([], "What is the DC to swim?", True)


def test_abstains_when_retrieved_rule_is_unrelated(gate):
    """A named rule that is not what was asked about is not evidence."""
    context = [{"name": "Tack", "content": "You can move past an ally."}]
    assert gate._should_abstain(context, "What is the DC to swim?", True)


def test_abstains_when_numeric_question_has_no_numeric_evidence(gate):
    """Rule matched by name, but the excerpt holds no figure to quote."""
    context = [{"name": "Swim", "content": "Swimming requires an Athletics check."}]
    assert gate._should_abstain(context, "What is the DC to Swim?", True)


def test_answers_when_retrieval_supplies_the_number(gate):
    context = [
        {"name": "Swim", "content": "The DC is 10 for calm water and 15 for fast."}
    ]
    assert not gate._should_abstain(context, "What is the DC to Swim?", True)


def test_never_abstains_on_a_narrative_turn(gate):
    assert not gate._should_abstain([], "I attack the goblin.", False)


def test_refusal_text_forbids_invented_numbers():
    """The refusal is the entire contract - no clause is injected anywhere.

    The prompt-based backstop is gone by design: BP-08 replaced "ask the model
    nicely" with a deterministic refusal, so there is nothing left to attach.
    """
    from app.agents.rules_lawyer import ABSTENTION_TEXT

    assert "I don't have that rule in my books" in ABSTENTION_TEXT
    assert not hasattr(LLMOrchestrator, "_abstention_clause")


def test_abstention_clause_reaches_the_streaming_lawyer(monkeypatch):
    """Pillar A on the streaming path: deterministic refusal, no LLM call.

    Since the zero-LLM short-circuit, abstain=True never reaches Ollama at all,
    so there is nothing to capture in a system prompt - the refusal IS the
    output. test_abstention_zero_llm.py pins the call-count guarantee; this
    test pins the streaming *surface* the orchestrator consumes.
    """
    import asyncio

    from app.agents.rules_lawyer import ABSTENTION_TEXT, RulesLawyerAgent
    from app.llm.ollama_client import OllamaClient

    def explode(*a, **k):
        raise AssertionError("abstain=True must not call the model")

    monkeypatch.setattr(OllamaClient, "stream", explode)
    monkeypatch.setattr(OllamaClient, "generate", explode)

    agent = RulesLawyerAgent.__new__(RulesLawyerAgent)  # no __init__ side effects
    agent.ollama = OllamaClient("http://127.0.0.1:1")  # never contacted
    agent.settings = type("S", (), {"model_for": staticmethod(lambda _k: "stub")})()

    async def run():
        gen, cites = await agent.stream_adjudication(
            query="What is the DC to bake a cake with the Waffle Iron?",
            edition="2e",
            context=[],
            abstain=True,
        )
        return [c async for c in gen], cites

    chunks, citations = asyncio.run(run())
    assert chunks == [ABSTENTION_TEXT]
    assert citations == []  # zero fabricated citations


def test_thin_context_is_refused_without_reaching_the_model(monkeypatch):
    """Thin context must short-circuit, not prompt the model to cooperate.

    BP-08 tightened this from "carry an instruction and hope": empty retrieval
    now returns the deterministic refusal and never calls Ollama, so the model
    cannot paraphrase, embellish, or ignore the instruction.
    """
    import asyncio

    from app.agents.rules_lawyer import ABSTENTION_TEXT, RulesLawyerAgent
    from app.llm.ollama_client import OllamaClient

    async def explode(*a, **k):
        raise AssertionError("thin context must not reach the model")
        yield ""  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(OllamaClient, "stream", explode)

    agent = RulesLawyerAgent.__new__(RulesLawyerAgent)
    agent.ollama = OllamaClient("http://127.0.0.1:1")
    agent.settings = type("S", (), {"model_for": staticmethod(lambda _k: "stub")})()

    async def run():
        gen, cites = await agent.stream_adjudication(
            query="something borderline", context=[], abstain=False
        )
        return [c async for c in gen], cites

    chunks, citations = asyncio.run(run())
    assert chunks == [ABSTENTION_TEXT]
    assert citations == []