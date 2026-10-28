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
import queue
import sys
import wave
from collections.abc import AsyncIterator, Sequence
from io import BytesIO
from types import ModuleType
from typing import Any

from app.domain.errors import AudioTooLong, InvalidAudio, SttUnavailable
from app.ports.stt import StreamUpdate, Transcription

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


def _update(answer: Any) -> StreamUpdate:
    """Translate one engine dict into the port's shape, rejecting anything unusable (ADR-022)."""
    if not isinstance(answer, dict):
        raise SttUnavailable(f"unexpected stream answer: {type(answer).__name__}")
    received = answer.get("received")
    pass_ms = answer.get("pass_ms")
    return StreamUpdate(
        text=str(answer.get("text") or ""),
        pending=str(answer.get("pending") or ""),
        language=answer.get("language") or None,
        received_ms=round(float(received or 0) * 1000),
        pass_ms=float(pass_ms) if pass_ms is not None else None,
    )


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

    async def stream(
        self,
        chunks: AsyncIterator[Sequence[float]],
        *,
        language_code: str | None,
    ) -> AsyncIterator[StreamUpdate]:
        """Bridge the blocking live engine to asyncio (F7, ADR-022).

        The engine consumes chunks from a blocking iterator in a worker thread and yields one dict
        per chunk. The event loop feeds that iterator and drains the results, so no engine call
        runs on the loop. The caller owns the window: ending `chunks` flushes the engine's tail.
        """
        loop = asyncio.get_running_loop()
        inbox: queue.Queue[Sequence[float] | None] = queue.Queue()
        outbox: asyncio.Queue[StreamUpdate | BaseException | None] = asyncio.Queue()

        def push(item: StreamUpdate | BaseException | None) -> None:
            # The worker can outlive a cancellation; never touch a closed loop.
            if not loop.is_closed():
                loop.call_soon_threadsafe(outbox.put_nowait, item)

        def run_engine() -> None:
            engine = _engine()

            def blocking_chunks():
                while True:
                    item = inbox.get()
                    if item is None:
                        return
                    yield item

            try:
                for answer in engine.stream(blocking_chunks(), language=language_code):
                    push(_update(answer))
            except BaseException as error:
                push(SttUnavailable(str(error)))
            finally:
                push(None)

        # `asyncio.to_thread` keeps the CPU work off the loop; the task only exists so a cancelled
        # stream can stop feeding the worker.
        worker = asyncio.create_task(asyncio.to_thread(run_engine))
        try:
            async for chunk in chunks:
                inbox.put_nowait(chunk)
            inbox.put_nowait(None)
            while True:
                item = await outbox.get()
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            inbox.put_nowait(None)
            if not worker.done():
                worker.cancel()

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
