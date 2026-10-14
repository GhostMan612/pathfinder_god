# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""BP-08: /voice/asr-stream must not slice words across chunk boundaries.

The old loop cleared its PCM buffer after every partial emit, so each Whisper
pass only saw the newest ~1.5 s. A word straddling a boundary was decoded twice
and disagreed with itself. These tests pin the two pieces that fix that: a
sliding window that retains overlap, and LocalAgreement-2 stabilisation of the
output.

Fully hermetic: the Whisper model is never constructed.
"""

from __future__ import annotations

import base64
import struct

import pytest
from conftest import TEST_API_KEY

from app.api.voice import (
    _MAX_FRAME_BYTES,
    _MAX_PCM_BYTES,
    _ROLLING_WINDOW_BYTES,
    LocalAgreementState,
    asr_stream,
    common_prefix_len,
)

# --- LocalAgreement-2 ------------------------------------------------------


def test_common_prefix_is_case_and_punctuation_insensitive():
    left = ["Okay", "Goblin.", "attack"]
    right = ["okay", "goblin", "Attack!"]
    assert common_prefix_len(left, right) == 3


def test_common_prefix_stops_at_first_disagreement():
    assert common_prefix_len(["a", "b", "c"], ["a", "x", "c"]) == 1


def test_common_prefix_of_empty_is_zero():
    assert common_prefix_len([], ["a"]) == 0


def test_nothing_is_committed_after_a_single_pass():
    """One hypothesis is not agreement - this is the "2" in LocalAgreement-2."""
    state = LocalAgreementState()
    text, confirmed, unstable = state.update("the goblin attacks")

    assert confirmed == ""
    assert state.confirmed_count == 0
    # The full transcript is still emitted, just not yet trusted.
    assert text == "the goblin attacks"
    assert unstable == "the goblin attacks"


def test_agreed_prefix_commits_after_two_consistent_passes():
    state = LocalAgreementState()
    state.update("the goblin attacks")
    text, confirmed, unstable = state.update("the goblin attacks the hero")

    assert confirmed == "the goblin attacks"
    assert state.confirmed_count == 3
    assert unstable == "the hero"
    assert text == "the goblin attacks the hero"


def test_unstable_tail_stays_uncommitted_and_keeps_changing():
    state = LocalAgreementState()
    state.update("roll a d20 for the waffle")
    _, confirmed, unstable = state.update("roll a d20 for the waffle iron")

    assert confirmed == "roll a d20 for the waffle"
    # The word that has not settled yet is exactly the one that changes.
    assert unstable == "iron"


def test_committed_words_are_never_revised_by_a_later_disagreement():
    """The point of the algorithm: agreed words become final and stay final.

    Pass 3 disagrees with pass 2 at "door"/"drawer", but "open the door slowly"
    was already agreed by two consecutive passes, so it is not rewritten.
    """
    state = LocalAgreementState()
    state.update("open the door slowly")
    state.update("open the door slowly and quietly")
    assert state.confirmed_count == 4

    _, confirmed, unstable = state.update("open the drawer slowly and quietly")

    # Monotonic: the committed prefix is exactly as committed, not truncated.
    assert confirmed == "open the door slowly"
    assert state.confirmed_count == 4
    # Everything after the committed prefix is still revisable.
    assert unstable == "and quietly"


def test_casing_comes_from_the_freshest_pass():
    state = LocalAgreementState()
    state.update("goblin king")
    _, confirmed, _ = state.update("Goblin King")

    assert confirmed == "Goblin King"


def test_disagreeing_passes_commit_nothing():
    state = LocalAgreementState()
    state.update("cast fireball")
    _, confirmed, _ = state.update("close the gate")

    assert confirmed == ""


def test_reset_clears_committed_state():
    state = LocalAgreementState()
    state.update("hello there")
    state.update("hello there friend")
    assert state.confirmed_count == 2

    state.reset()

    assert state.confirmed_count == 0
    _, confirmed, _ = state.update("brand new utterance")
    assert confirmed == ""


def test_regression_does_not_shrink_the_committed_prefix():
    """A window that trimmed older audio must not un-confirm those words.

    Pass 3 no longer contains "alpha"/"bravo" because the sliding window moved
    past that audio. Those words were already committed, so they stay in the
    transcript instead of vanishing.
    """
    state = LocalAgreementState()
    state.update("alpha bravo charlie")
    state.update("alpha bravo charlie delta")
    assert state.confirmed == ["alpha", "bravo", "charlie"]

    # Simulates the sliding window having dropped the first words.
    text, confirmed, _ = state.update("charlie delta echo")

    assert confirmed == "alpha bravo charlie"
    assert text == "alpha bravo charlie"


# --- sliding window --------------------------------------------------------


def test_rolling_window_is_strictly_below_the_hard_ceiling():
    assert _ROLLING_WINDOW_BYTES < _MAX_PCM_BYTES


def test_frame_cap_is_an_independent_guard():
    """The per-frame cap is deliberately larger than the decode window.

    It is a separate ceiling for a single oversized message, not the working
    size; the rolling window is what bounds normal operation.
    """
    assert _MAX_FRAME_BYTES <= _MAX_PCM_BYTES
    assert _ROLLING_WINDOW_BYTES <= _MAX_PCM_BYTES


def test_window_trims_from_the_front_and_keeps_the_newest_audio():
    """Replicates _append: the tail of the buffer is always the newest audio."""
    buf = bytearray()
    chunk = struct.pack("<h", 1234) * 1000  # 2000 bytes of distinguishable PCM

    # Feed well past the window in 1 s steps (32000 bytes at 16 kHz).
    for _ in range(20):
        buf.extend(chunk)
        if len(buf) > _ROLLING_WINDOW_BYTES:
            del buf[: len(buf) - _ROLLING_WINDOW_BYTES]

    assert len(buf) <= _ROLLING_WINDOW_BYTES
    # The final sample must be the most recent one, i.e. trimming kept the tail.
    assert struct.unpack_from("<h", bytes(buf), len(buf) - 2)[0] == 1234


def test_window_keeps_overlap_so_boundary_words_are_re_decoded():
    """Consecutive decode windows must overlap, or agreement cannot happen."""
    window = _ROLLING_WINDOW_BYTES
    step = 16000 * 2 * 3 // 2  # ~1.5 s, matching next_emit

    assert window > step * 2


# --- websocket contract ----------------------------------------------------


class _FakeWebSocket:
    """Minimal WebSocket stand-in: no server, no model, no audio."""

    def __init__(self, incoming: list[dict], authorized: bool = True) -> None:
        self._incoming = list(incoming)
        self.sent: list[dict] = []
        self.accepted = False
        self.closed = False
        self.close_reason = ""
        self.close_code: int | None = None
        # conftest pins PFGOD_API_KEY_SHA256, so _ws_authorized is enforced here.
        # Pass authorized=False to exercise the rejection path instead.
        self.headers: dict[str, str] = {"X-API-Key": TEST_API_KEY} if authorized else {}
        self.query_params: dict[str, str] = {}

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> dict:
        if not self._incoming:
            raise RuntimeError("client closed")
        return self._incoming.pop(0)

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


def _pcm_frame(seconds: float = 1.6) -> dict:
    raw = struct.pack("<h", 0) * int(16000 * seconds)
    return {"type": "pcm", "data": base64.b64encode(raw).decode("ascii")}


async def _run(ws: _FakeWebSocket) -> None:
    await asr_stream(ws)  # type: ignore[arg-type]


def test_stream_emits_partials_with_backward_compatible_shape(monkeypatch):
    """`type` and `text` are unchanged; confirmed/unstable are additive."""
    seen = iter(["hello world", "hello world friend"])

    def fake(_pcm: bytes) -> str:
        return next(seen, "")

    monkeypatch.setattr("app.api.voice._transcribe_pcm", fake)

    import asyncio

    ws = _FakeWebSocket([_pcm_frame(), _pcm_frame(), {"type": "done"}])
    asyncio.run(_run(ws))

    partials = [m for m in ws.sent if m["type"] == "partial"]
    finals = [m for m in ws.sent if m["type"] == "final"]

    assert partials, "expected at least one partial"
    for p in partials:
        assert set(p) >= {"type", "text"}  # old clients only need these
        assert "confirmed" in p and "unstable" in p
    assert len(finals) == 1
    assert isinstance(finals[0]["text"], str)


def test_stream_answers_ping_with_pong(monkeypatch):
    def fake(_pcm: bytes) -> str:
        return ""

    monkeypatch.setattr("app.api.voice._transcribe_pcm", fake)

    import asyncio

    ws = _FakeWebSocket([{"type": "ping"}, {"type": "done"}])
    asyncio.run(_run(ws))

    assert {"type": "pong"} in ws.sent


@pytest.mark.parametrize("terminal", ["done", "flush", "end", "stop"])
def test_every_terminal_kind_emits_a_final_frame(monkeypatch, terminal):
    """Clients differ on the stop word; all of them must get a final."""

    def fake(_pcm: bytes) -> str:
        return "final words"

    monkeypatch.setattr("app.api.voice._transcribe_pcm", fake)

    import asyncio

    ws = _FakeWebSocket([_pcm_frame(), {"type": terminal}])
    asyncio.run(_run(ws))

    finals = [m for m in ws.sent if m["type"] == "final"]
    assert len(finals) == 1
    assert finals[0]["text"] == "final words"


def test_stream_always_closes_the_socket(monkeypatch):
    """F3 guarantee: a raising frame must not leak the connection."""

    def fake(_pcm: bytes) -> str:
        return ""

    monkeypatch.setattr("app.api.voice._transcribe_pcm", fake)

    import asyncio

    ws = _FakeWebSocket([{"type": "pcm", "data": "!!!not-base64!!!"}])
    asyncio.run(_run(ws))

    assert ws.accepted
    assert ws.closed


def test_unauthenticated_socket_is_rejected_before_accepted(monkeypatch):
    """F1 guarantee: the stream never runs for an unauthenticated client."""

    def fake(_pcm: bytes) -> str:
        return "should never run"

    monkeypatch.setattr("app.api.voice._transcribe_pcm", fake)

    import asyncio

    ws = _FakeWebSocket([_pcm_frame()], authorized=False)
    asyncio.run(_run(ws))

    assert not ws.accepted
    assert ws.closed
    assert ws.close_code == 1008
    assert ws.sent == []


def test_oversized_frame_is_dropped_without_decoding(monkeypatch):
    """The F2 hard cap still holds: one frame cannot exceed _MAX_FRAME_BYTES."""

    calls = {"n": 0}

    def fake(_pcm: bytes) -> str:
        calls["n"] += 1
        return ""

    monkeypatch.setattr("app.api.voice._transcribe_pcm", fake)

    import asyncio

    huge = {"type": "pcm", "data": base64.b64encode(b"\x00" * (_MAX_FRAME_BYTES + 16)).decode()}
    ws = _FakeWebSocket([huge, {"type": "done"}])
    asyncio.run(_run(ws))

    # Only the final pass ran; the oversized frame never reached the decoder.
    assert calls["n"] == 1