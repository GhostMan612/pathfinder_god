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

import os
import tempfile
import wave
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
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


def _get_model():
    global _ASR_MODEL
    if _ASR_MODEL is None:
        _ASR_MODEL = WhisperModel(_ASR_SIZE, device="cpu", compute_type="int8")
    return _ASR_MODEL


class TranscribeResponse(BaseModel):
    text: str
    language: str
    duration_s: float


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: str = "default"


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)) -> TranscribeResponse:
    if not _FASTER:
        raise HTTPException(
            status_code=501,
            detail="faster-whisper is not installed. Run: pip install faster-whisper",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio upload")
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
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
        text = "".join(seg.text for seg in segments).strip()
        return TranscribeResponse(
            text=text, language=getattr(info, "language", "en"), duration_s=float(info.duration or 0.0)
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/speak")
async def speak(req: SpeakRequest) -> Response:
    if not _TTS:
        raise HTTPException(
            status_code=501,
            detail="pyttsx3 is not installed. Run: pip install pyttsx3",
        )
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine = pyttsx3.init()
        if req.voice != "default":
            try:
                engine.setProperty("voice", req.voice)
            except Exception:
                pass
        engine.save_to_file(req.text, wav_path)
        engine.runAndWait()
        engine.stop()
        return Response(content=Path(wav_path).read_bytes(), media_type="audio/wav")
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass
