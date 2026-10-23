# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""BP-08: unverified inline citations and abstention telemetry.

Verbatim forwarding made the *Sources* block trustworthy, but the model still
writes bracketed tags into its own prose naming rules it was never shown. Those
read as verified, which is worse than no citation at all.

Hermetic throughout: PFGOD_MISS_LOG redirects the sink to tmp_path, so nothing
here ever touches the real data/misses.jsonl.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.agents.rules_lawyer import (
    ABSTENTION_TEXT,
    InlineCitationScrubber,
    RulesLawyerAgent,
    sanitize_inline_citations,
)
from app.telemetry import (
    flush_pending,
    log_miss,
    miss_log_path,
    read_misses,
)


@pytest.fixture(autouse=True)
def miss_log(tmp_path, monkeypatch):
    """Point the telemetry sink at a temp file for every test in this module."""
    target = tmp_path / "misses.jsonl"
    monkeypatch.setenv("PFGOD_MISS_LOG", str(target))
    yield target
    flush_pending()


class _StubLLM:
    """Streams a fixed script of chunks; counts how often it was touched."""

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.stream_calls = 0

    async def stream(self, *a, **k):
        self.stream_calls += 1
        for c in self.chunks:
            yield c

    async def generate(self, *a, **k):  # pragma: no cover - must not run
        raise AssertionError("generate must not be called")

    async def chat(self, *a, **k):  # pragma: no cover - must not run
        raise AssertionError("chat must not be called")


def _agent(llm) -> RulesLawyerAgent:
    agent = RulesLawyerAgent.__new__(RulesLawyerAgent)
    agent.ollama = llm
    agent.settings = type("S", (), {"model_for": staticmethod(lambda _k: "stub")})()
    return agent


CONTEXT = [{"source_book": "Core Rulebook", "name": "Attack", "category": "Combat"}]
VALID = {"[Core Rulebook - Attack]"}


# --- sanitize_inline_citations --------------------------------------------


def test_valid_tag_is_preserved():
    text = "Make an Attack [Core Rulebook - Attack] now."
    cleaned, stripped = sanitize_inline_citations(text, VALID)
    assert cleaned == text
    assert stripped == []


def test_hallucinated_tag_is_stripped_and_reported():
    text = "Grapple for +2 [Core Rulebook - Grapple] to escape."
    cleaned, stripped = sanitize_inline_citations(text, VALID)

    # The prose legitimately mentions grappling; only the bracketed TAG goes.
    assert stripped == ["[Core Rulebook - Grapple]"]
    assert "[" not in cleaned
    assert cleaned == "Grapple for +2 to escape."


def test_tag_matching_is_case_and_whitespace_insensitive():
    text = "See [core   rulebook - attack] for detail."
    cleaned, stripped = sanitize_inline_citations(text, VALID)
    assert cleaned == text
    assert stripped == []


def test_ordinary_brackets_are_not_mistaken_for_citations():
    """Dice notation and editorial brackets must survive untouched."""
    for text in ("Roll [1d20+5] for the check.", "He said [sic] loudly.", "Step [3] of the ritual."):
        cleaned, stripped = sanitize_inline_citations(text, VALID)
        assert cleaned == text, text
        assert stripped == [], text


def test_text_without_brackets_is_returned_unchanged():
    text = "The goblin has 11 hp."
    assert sanitize_inline_citations(text, VALID) == (text, [])


def test_multiple_hallucinations_are_all_stripped():
    text = "[Core Rulebook - Dodge] then [Core Rulebook - Grapple] then [Core Rulebook - Trip]"
    cleaned, stripped = sanitize_inline_citations(text, VALID)
    assert stripped == [
        "[Core Rulebook - Dodge]",
        "[Core Rulebook - Grapple]",
        "[Core Rulebook - Trip]",
    ]
    assert "[" not in cleaned


def test_stripping_does_not_leave_double_spaces():
    text = "Deal 5 damage. [Core Rulebook - Grapple]  Then move."
    cleaned, _ = sanitize_inline_citations(text, VALID)
    assert "  " not in cleaned


# --- streaming scrubber ----------------------------------------------------


def test_scrubber_strips_a_tag_split_across_chunks():
    """The whole point: chunk boundaries must not hide a hallucination."""
    scrubber = InlineCitationScrubber(VALID)
    out = scrubber.feed("You may Attack ")
    out += scrubber.feed("[Core Rulebook - Grap")
    out += scrubber.feed("ple] to move.")
    out += scrubber.finish()

    assert "Grapple" not in out
    assert scrubber.stripped == ["[Core Rulebook - Grapple]"]
    assert "You may Attack" in out


def test_scrubber_keeps_a_valid_tag_split_across_chunks():
    scrubber = InlineCitationScrubber(VALID)
    out = scrubber.feed("Make an Att")
    out += scrubber.feed("ack [Core Rulebook - Att")
    out += scrubber.feed("ack] now.")
    out += scrubber.finish()

    assert "[Core Rulebook - Attack]" in out
    assert scrubber.stripped == []


def test_scrubber_emits_incrementally_and_only_flushes_at_the_end():
    scrubber = InlineCitationScrubber(VALID)
    assert scrubber.feed("plain text") == "plain text"
    # A dangling opener is held back; the safe prefix before it still streams.
    assert scrubber.feed(" [Core Rulebook - Grap") == " "
    assert scrubber.finish() == ""
    # An unterminated tag at end-of-stream is dropped, not shown to the player.
    assert scrubber.stripped == ["[Core Rulebook - Grap"]


def test_scrubber_flushes_a_complete_tail_at_end_of_stream():
    """A closed tag in the final chunk is emitted by finish(), not dropped."""
    scrubber = InlineCitationScrubber(VALID)
    emitted = scrubber.feed("Make an Attack ")
    # The chunk ends with an open bracket, so only the safe prefix streams now.
    emitted += scrubber.feed("[Core Rulebook - Attack] now")
    emitted += scrubber.finish()

    assert emitted == "Make an Attack [Core Rulebook - Attack] now"
    assert scrubber.stripped == []


# --- streaming adjudication ------------------------------------------------


def _collect(chunks, context=CONTEXT, abstain=False):
    llm = _StubLLM(chunks)
    agent = _agent(llm)

    async def run():
        gen, cites = await agent.stream_adjudication(
            query="How does grappling work?",
            edition="2e",
            context=context,
            abstain=abstain,
        )
        return "".join([c async for c in gen]), cites

    return asyncio.run(run()), llm


def test_adjudication_strips_hallucinated_inline_citation():
    (text, _cites), llm = _collect(["You may Attack. [Core Rulebook - Grapple] ends your turn."])

    assert "Grapple" not in text
    assert llm.stream_calls == 1
    flush_pending()


def test_adjudication_records_bad_inline_citation_in_the_miss_log(miss_log):
    _collect(["Attack works. [Core Rulebook - Grapple] too."])
    flush_pending()

    rows = read_misses(miss_log)
    bad = [r for r in rows if r["event"] == "bad_inline_citation"]
    assert bad, rows
    assert "[Core Rulebook - Grapple]" in bad[0]["details"]["stripped"]


def test_adjudication_records_abstention(miss_log):
    (text, cites), llm = _collect([], context=[], abstain=True)

    assert text == ABSTENTION_TEXT
    assert cites == []
    assert llm.stream_calls == 0
    flush_pending()

    rows = read_misses(miss_log)
    assert any(r["event"] == "abstain" for r in rows), rows


def test_abstention_row_records_route_score_and_reason(miss_log):
    async def run():
        agent = _agent(_StubLLM([]))
        gen, _ = await agent.stream_adjudication(
            query="DC for a cake?",
            edition="2e",
            context=[],
            abstain=True,
            route_score=7,
        )
        return [c async for c in gen]

    asyncio.run(run())
    flush_pending()

    row = read_misses(miss_log)[0]
    assert row["event"] == "abstain"
    assert row["route_score"] == 7
    assert row["details"]["reason"] == "flagged"
    assert row["query"] == "DC for a cake?"
    assert "ts" in row


def test_no_retrieval_is_recorded_distinctly_from_a_flag(miss_log):
    _collect([], context=[])
    flush_pending()

    row = read_misses(miss_log)[0]
    assert row["details"]["reason"] == "no_retrieval"


def test_clean_answer_logs_nothing(miss_log):
    _collect(["Make an Attack action. [Core Rulebook - Attack] is legal."])
    flush_pending()

    assert read_misses(miss_log) == []


# --- telemetry robustness --------------------------------------------------


def test_telemetry_never_raises_on_an_unwritable_path(tmp_path, monkeypatch):
    """A broken sink must not break a rules ruling.

    Pointed at a path whose parent is a regular file, so mkdir() fails.
    """
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("PFGOD_MISS_LOG", str(blocker / "misses.jsonl"))

    log_miss("abstain", "q")
    flush_pending()  # must not raise

    assert not (blocker / "misses.jsonl").exists()


def test_telemetry_never_raises_when_the_target_is_a_directory(tmp_path, monkeypatch):
    """An unopenable sink (IsADirectoryError) is swallowed too."""
    as_dir = tmp_path / "sink"
    as_dir.mkdir()
    monkeypatch.setenv("PFGOD_MISS_LOG", str(as_dir))

    log_miss("abstain", "q")
    flush_pending()  # must not raise


def test_telemetry_default_path_is_the_repo_data_dir(monkeypatch):
    monkeypatch.delenv("PFGOD_MISS_LOG", raising=False)
    assert miss_log_path().name == "misses.jsonl"
    assert miss_log_path().parent.name == "data"


def test_rows_are_valid_jsonl(miss_log):
    log_miss("abstain", "first")
    flush_pending()
    log_miss("bad_inline_citation", "second", route_score=3)
    flush_pending()

    raw = miss_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 2
    for line in raw:
        json.loads(line)  # must parse


def test_query_text_is_truncated(miss_log):
    log_miss("abstain", "x" * 5_000)
    flush_pending()

    assert len(read_misses(miss_log)[0]["query"]) <= 300
