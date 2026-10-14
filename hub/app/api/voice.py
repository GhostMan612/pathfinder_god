# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Voice transcription (ASR) and speech synthesis (TTS).

Both packages are optional extras. If ``faster-whisper`` is not importable the
transcribe endpoint returns 501 with the exact install command, likewise
``/voice/speak`` when ``pyttsx3`` is missing. That keeps the hub install lean:
voice simply comes online once the operator adds the packages.
"""

from __future__ import annotations

import asyncio
import base64 as _b64
import os
import tempfile
import wave
from pathlib import Path
from typing import Annotated

import anyio
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

try:  # optional ASR
    from faster_whisper import WhisperModel

    _FASTER = True
except Exception:  # pragma: no cover - import-level guard
    _FASTER = False


def _decode_wav_16k(path: str):
    """Decode a WAV to a mono float32 16 kHz 1-D array without PyAV.

    faster-whisper 1.2.1 calls av.open(metadata_errors=...), which the PyAV 19.x
    that Python 3.14 wheels require has removed — so the av path 500s. WAV is
    trivially decodeable with the stdlib + numpy, so prefer that and only fall
    back to the av path for non-WAV input.
    """
    try:
        import numpy as np

        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            channels = w.getnchannels()
            width = w.getsampwidth()
            frames = w.readframes(w.getnframes())
        if width == 2:
            arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif width == 4:
            arr = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            return None
        if channels > 1:
            arr = arr.reshape(-1, channels).mean(axis=1)
        if sr != 16000:
            idx = np.linspace(0, len(arr) - 1, int(len(arr) * 16000 / sr))
            arr = np.interp(idx, np.arange(len(arr)), arr)
        return arr.astype(np.float32)
    except Exception:
        return None

try:  # optional TTS
    import pyttsx3

    _TTS = True
except Exception:  # pragma: no cover - import-level guard
    _TTS = False

router = APIRouter(prefix="/voice", tags=["voice"])

_ASR_MODEL = None
_ASR_SIZE = os.environ.get("PFGOD_ASR_MODEL", "tiny")

# Ceilings for the ASR websocket. Without these a client could stream base64
# forever (buf only ever grew) or send a multi-GB upload, and the hub binds
# 0.0.0.0:8000, so any LAN peer could exhaust its RAM.
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_MAX_PCM_BYTES = 16000 * 2 * 60  # 60 s of 16 kHz 16-bit mono
_MAX_FRAME_BYTES = 512 * 1024  # one base64 PCM chunk on the wire
_IDLE_TIMEOUT_S = 120


def _ws_authorized(websocket: WebSocket) -> bool:
    """Websocket auth, enforced only when a key is actually configured.

    get_current_user is an HTTP Depends helper and cannot be reused here, and
    the hub is a local-only app whose Command Center and Spoke clients send no
    credentials at all. Gating unconditionally would break both of them on a
    default install (api_key_sha256 is ""), so this enforces when configured
    and stays open when the operator has deliberately chosen keyless LAN.
    """
    from app.config import get_settings

    expected = (get_settings().api_key_sha256 or "").strip()
    if not expected:
        return True
    from app.api.security import verify_api_key

    key = websocket.headers.get("X-API-Key") or websocket.query_params.get("api_key") or ""
    auth = websocket.headers.get("Authorization") or ""
    if not key and auth.lower().startswith("bearer "):
        key = auth[7:].strip()
    return bool(key) and verify_api_key(key, expected)


def _get_model():
    global _ASR_MODEL
    if _ASR_MODEL is None:
        _ASR_MODEL = WhisperModel(_ASR_SIZE, device="cpu", compute_type="int8")
    return _ASR_MODEL


class TranscribeResponse(BaseModel):
    text: str
    language: str
    duration_s: float


def _transcribe_pcm(pcm: bytes) -> str:
    """Run transcription on an int16 mono 16 kHz PCM block."""
    if not _FASTER:
        return ""
    try:
        import numpy as np

        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if len(arr) < 4000:
            return ""
        segments, _ = _get_model().transcribe(arr, beam_size=1)
        return "".join(seg.text for seg in segments).strip()
    except Exception:
        return ""


@router.websocket("/asr-stream")
async def asr_stream(websocket: WebSocket) -> None:
    """Buffered chunked ASR over a websocket.

    The client streams raw PCM (int16 mono 16 kHz, s16le) as base64 chunks and
    gets back partial transcripts as audio accumulates. This is intentionally
    tempered: it streams partial hypotheses every ~1.5 s of audio, instead of
    waiting for a complete clip like /voice/transcribe. A true overlapping
    windowed decoder (Whisper-Streaming local-agreement) is a straight drop-in
    over this buffer if we want it later.
    """
    if not _ws_authorized(websocket):
        await websocket.close(code=1008, reason="authentication required")
        return

    await websocket.accept()
    buf = bytearray()
    step_bytes = 16000 * 2 * 3 // 2  # ~1.5 s of audio at 16 kHz 16-bit
    next_emit = step_bytes
    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=_IDLE_TIMEOUT_S)
            except (asyncio.TimeoutError, TimeoutError):
                break
            except WebSocketDisconnect:
                break
            kind = msg.get("type")
            if kind == "pcm":
                try:
                    chunk = _b64.b64decode(msg.get("data", ""), validate=True)
                except Exception:
                    continue
                if len(chunk) > _MAX_FRAME_BYTES:
                    continue
                buf.extend(chunk)
                # Bound the buffer: a client streaming forever must not grow it.
                if len(buf) > _MAX_PCM_BYTES:
                    del buf[:-_MAX_PCM_BYTES]
                if len(buf) >= next_emit:
                    # Whisper is seconds-scale on this CPU. Running it inline
                    # froze /health, /ask and every other socket for the whole
                    # decode, so it goes to the worker threadpool.
                    text = await anyio.to_thread.run_sync(_transcribe_pcm, bytes(buf))
                    await websocket.send_json({"type": "partial", "text": text})
                    buf.clear()
                    next_emit += step_bytes
            elif kind == "done":
                text = await anyio.to_thread.run_sync(_transcribe_pcm, bytes(buf))
                buf.clear()
                await websocket.send_json({"type": "final", "text": text})
                break
            elif kind == "ping":
                await websocket.send_json({"type": "pong"})
    except Exception:
        # Not just WebSocketDisconnect: a non-JSON frame raises JSONDecodeError
        # and any other RuntimeError used to skip the close below, leaking the
        # connection and its buffer.
        pass
    finally:
        buf.clear()
        try:
            await websocket.close()
        except Exception:
            pass


def _transcribe_file(data: bytes, suffix: str) -> TranscribeResponse:
    """Blocking: write the upload to a temp file and run Whisper on it."""
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)
        model = _get_model()
        arr = _decode_wav_16k(tmp_path)
        if arr is not None:
            segments, info = model.transcribe(arr, beam_size=1)
        else:
            segments, info = model.transcribe(tmp_path, beam_size=1)
        return TranscribeResponse(
            text="".join(seg.text for seg in segments).strip(),
            language=getattr(info, "language", "en"),
            duration_s=float(info.duration or 0.0),
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: Annotated[UploadFile, File()]) -> TranscribeResponse:
    if not _FASTER:
        raise HTTPException(
            status_code=501,
            detail="faster-whisper is not installed. Run: pip install faster-whisper",
        )
    # Cap before buffering the whole thing: await file.read() with no ceiling let
    # a single request allocate whatever the client chose to send.
    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="empty audio upload")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="audio upload too large")
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    # Whisper plus the WAV decode are CPU-bound and block for seconds on this
    # laptop; keep them off the event loop.
    return await anyio.to_thread.run_sync(_transcribe_file, data, suffix)


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: str = Field("default", max_length=120)


def _synthesize(text: str, voice: str) -> bytes:
    """Blocking: drive pyttsx3/SAPI and read the WAV back."""
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine = pyttsx3.init()
        if voice != "default":
            try:
                engine.setProperty("voice", voice)
            except Exception:
                pass
        engine.save_to_file(text, wav_path)
        engine.runAndWait()
        engine.stop()
        return Path(wav_path).read_bytes()
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


@router.post("/speak")
async def speak(req: SpeakRequest) -> Response:
    if not _TTS:
        raise HTTPException(
            status_code=501,
            detail="pyttsx3 is not installed. Run: pip install pyttsx3",
        )
    # runAndWait() blocks on the OS speech engine; the Command Center calls this
    # once per sentence, so an inline call stalled the loop dozens of times per
    # chat reply.
    wav = await anyio.to_thread.run_sync(_synthesize, req.text, req.voice)
    return Response(content=wav, media_type="audio/wav")
