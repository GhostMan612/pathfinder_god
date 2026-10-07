# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Unit tests for the GM's refuse-to-fabricate gate (orchestrator)."""
from __future__ import annotations

from app.llm.orchestrator import LLMOrchestrator


def _gate(context: list[dict] | None, prompt: str, needs_rules: bool = True) -> bool:
    return LLMOrchestrator._should_abstain(
        object.__new__(LLMOrchestrator), context, prompt, needs_rules
    )


def test_abstains_when_retrieval_found_nothing() -> None:
    assert _gate(None, "what is the DC to swim?", True) is True
    assert _gate([], "what is the DC to swim?", True) is True


def test_confident_name_match_allows_narration() -> None:
    context = [{"name": "Swim", "content": "You move through water at half speed."}]
    assert _gate(context, "tell me about swimming", True) is False


def test_numeric_question_without_numeric_evidence_abstains() -> None:
    context = [{"name": "Swim", "content": "You move through water."}]
    assert _gate(context, "what is the DC to swim?", True) is True


def test_numeric_question_with_numeric_evidence_passes() -> None:
    context = [{"name": "Swim", "content": "Succeed at a DC 15 check to swim."}]
    assert _gate(context, "what is the DC to swim?", True) is False


def test_narration_turn_never_abstains() -> None:
    assert _gate(None, "the door creaks open", False) is False
