"""The Whistle adapter of the STT port (F4 S1, S3; ADR-015).

Whistle (Cactus Compute) is a 14 MB speech-to-text model that runs on this machine's CPU, so the
audio never leaves it. Three details carry the whole adapter:

1. **Telemetry first.** The package counts anonymous usage unless `NEEDLE_TELEMETRY=0` is set
   *before* it is imported, so the import is lazy and the variable is set on the way in (ADR-015).
2. **Off the loop.** The engine call is blocking CPU work; it runs in a worker thread, never on the
   event loop (docs/conventions.md §2).
3. **No files.** The engine accepts in-memory float samples, so the audio is decoded from the WAV
   bytes and handed over as samples: nothing is persisted, not even for a moment (S7).

The WAV shape is checked here, before the engine sees anything: 16 kHz mono 16-bit is what the
browser records, and any other rate would make the engine raise about resampling instead of
returning a usable domain error.

Nothing outside this package knows `needle` exists (ADR-004).
"""

import array
import asyncio
import os
import sys
import wave
from io import BytesIO
from types import ModuleType
from typing import Any

from app.domain.errors import AudioTooLong, InvalidAudio, SttUnavailable
from app.ports.stt import Transcription

# What the browser records and what Whistle supports natively (S1).
SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # bytes: 16-bit PCM
SAMPLE_SCALE = float(1 << 15)

# Contract §5: 120 s of audio per transcription request.
MAX_SECONDS = 120

# ADR-015: the package phones home with anonymous usage counts unless this is off before import.
TELEMETRY_ENV = "NEEDLE_TELEMETRY"


def _engine() -> ModuleType:
    """Import the STT engine on first use, with telemetry already disabled (ADR-015).

    Lazy on purpose: importing the package is cheap, but the model is not, and `main.py` builds the
    app on every start (`create_app`). The env var is set with `setdefault` so an operator can still
    override it, and it is always set before the import that reads it.
    """
    os.environ.setdefault(TELEMETRY_ENV, "0")
    import needle

    return needle


def _check_wav(audio: bytes, *, max_seconds: int) -> tuple[bytes, int]:
    """Validate the payload and return its PCM frames and its duration in milliseconds.

    Only the header is read here, so a rejected clip costs nothing: the shape the engine cannot take
    and a clip over the limit are domain errors, not engine failures.
    """
    if not audio:
        raise InvalidAudio("empty audio")

    try:
        with wave.open(BytesIO(audio), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            compression = wav.getcomptype()
            frames = wav.getnframes()
            if (
                channels != 1
                or width != SAMPLE_WIDTH
                or rate != SAMPLE_RATE
                or compression != "NONE"
            ):
                raise InvalidAudio(
                    f"unsupported audio: {rate} Hz, {channels} channel(s), {width * 8}-bit"
                )
            if frames > rate * max_seconds:
                raise AudioTooLong(f"{frames / rate:.1f} s")
            pcm = wav.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise InvalidAudio(str(error)) from error

    if not pcm:
        raise InvalidAudio("empty audio")
    return pcm, round(frames * 1000 / rate)


def _samples(pcm: bytes) -> array.array:
    """16-bit PCM frames as the float samples in [-1, 1] the engine takes."""
    shorts = array.array("h")
    shorts.frombytes(pcm)
    if sys.byteorder == "big":
        shorts.byteswap()
    return array.array("f", (value / SAMPLE_SCALE for value in shorts))


class WhistleSttAdapter:
    """`SttPort` over `cactus-needle`: one engine for the process, one thread per transcription."""

    def __init__(self, max_seconds: int = MAX_SECONDS) -> None:
        self._max_seconds = max_seconds

    async def transcribe(self, audio: bytes, *, language_code: str | None) -> Transcription:
        pcm, duration_ms = _check_wav(audio, max_seconds=self._max_seconds)
        # The engine loads the model on the first call (seconds) and then decodes on the CPU: both
        # belong in a worker thread, not on the event loop.
        answer = await asyncio.to_thread(self._run_engine, pcm, language_code)
        return Transcription(
            text=answer.get("text") or "",
            # The engine's own answer, never the language the caller forced (S3).
            language_detected=answer.get("language") or None,
            duration_ms=duration_ms,
        )

    def _run_engine(self, pcm: bytes, language_code: str | None) -> dict[str, Any]:
        """One blocking call. Runs in a worker thread; anything it raises is the engine failing."""
        engine = _engine()
        try:
            answer = engine.transcribe(_samples(pcm), language=language_code)
        except Exception as error:
            raise SttUnavailable(str(error)) from error
        if not isinstance(answer, dict):
            raise SttUnavailable(f"unexpected engine answer: {type(answer).__name__}")
        return answer
