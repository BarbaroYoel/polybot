"""One live interpreter session (F7, ADR-022).

The WebSocket endpoint only moves bytes and JSON: this module owns the behaviour. Four rules carry
the design:

1. **Windows, not a continuous stream.** T0 measured that Whistle degrades after ~5 s, so each
   window opens a fresh `SttPort.stream` and closes it at `window_seconds`. A 0.5 s overlap keeps
   the boundary word alive; the repeated text is removed before the segment is emitted.
2. **Partials are translated too** (P5), but never on the main path: a small debounce loop
   translates the latest partial while the engine keeps consuming audio. A stale answer is dropped
   by sequence number, and the final segment translation is authoritative.
3. **Sessions are ephemeral** (P2): nothing is stored, neither audio nor text. The UI keeps the
   history in memory.
4. **The UI gets events, not engine details.** Everything the session emits is one of the small
   dataclasses below; the API serializes them with the names of `docs/api-contract.md`.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.errors import InvalidAudio, LlmTimeout, LlmUnavailable, SttUnavailable
from app.ports.llm import LlmPort, TranslationRequest
from app.ports.stt import SttPort

logger = logging.getLogger(__name__)


class InterpreterCancelled(Exception):
    """The client asked to discard the session: no more segments or translations are emitted."""


SAMPLE_RATE = 16_000
WINDOW_SECONDS = 4.5
OVERLAP_SECONDS = 0.5
CHUNK_SECONDS = 1.0
DEBOUNCE_SECONDS = 0.6

_ERROR_MESSAGES = {
    "stt_unavailable": "No pudimos transcribir el audio. Vuelve a intentar en unos segundos.",
    "llm_unavailable": "No pudimos traducir el segmento. El texto original sigue disponible.",
    "llm_timeout": "La traducción tardó demasiado. El texto original sigue disponible.",
    "internal_error": "Ocurrió un error inesperado en el intérprete. Vuelve a intentar.",
}


@dataclass(frozen=True, slots=True)
class PartialEvent:
    """The window's text so far, plus the engine's unconfirmed tail."""

    seq: int
    text: str
    pending: str
    language: str | None
    received_ms: int


@dataclass(frozen=True, slots=True)
class PartialTranslationEvent:
    """A best-effort translation of the latest partial; the final one replaces it."""

    seq: int
    text: str
    target: str


@dataclass(frozen=True, slots=True)
class SegmentEvent:
    """A closed window: the unit that enters the ephemeral history."""

    id: str
    text: str
    language: str | None
    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class TranslationEvent:
    """The authoritative translation of a closed segment."""

    segment_id: str
    text: str
    target: str


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """A failure that does not necessarily end the session (e.g. one translation)."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


InterpreterEvent = (
    PartialEvent | PartialTranslationEvent | SegmentEvent | TranslationEvent | ErrorEvent
)


class InterpreterService:
    """Builds one ephemeral session per WebSocket connection."""

    def __init__(
        self,
        *,
        stt: SttPort,
        llm: LlmPort,
        window_seconds: float = WINDOW_SECONDS,
        overlap_seconds: float = OVERLAP_SECONDS,
        chunk_seconds: float = CHUNK_SECONDS,
        debounce_seconds: float = DEBOUNCE_SECONDS,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._window_samples = round(window_seconds * SAMPLE_RATE)
        self._overlap_samples = round(overlap_seconds * SAMPLE_RATE)
        self._chunk_samples = round(chunk_seconds * SAMPLE_RATE)
        self._overlap_ms = round(overlap_seconds * 1000)
        self._debounce = debounce_seconds

    def events(
        self,
        audio: AsyncIterator[Sequence[float]],
        *,
        source: str | None,
        target: str,
    ) -> AsyncIterator[InterpreterEvent]:
        """Return the session's events in order; closing the iterator cancels the work."""
        session = _InterpreterSession(
            stt=self._stt,
            llm=self._llm,
            audio=audio,
            source=source,
            target=target,
            window_samples=self._window_samples,
            overlap_samples=self._overlap_samples,
            chunk_samples=self._chunk_samples,
            overlap_ms=self._overlap_ms,
            debounce=self._debounce,
        )
        return session.events()


class _InterpreterSession:
    def __init__(
        self,
        *,
        stt: SttPort,
        llm: LlmPort,
        audio: AsyncIterator[Sequence[float]],
        source: str | None,
        target: str,
        window_samples: int,
        overlap_samples: int,
        chunk_samples: int,
        overlap_ms: int,
        debounce: float,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._audio = audio
        self._source = source
        self._target = target
        self._window_samples = window_samples
        self._overlap_samples = overlap_samples
        self._chunk_samples = chunk_samples
        self._overlap_ms = overlap_ms
        self._debounce = debounce

        self._queue: asyncio.Queue[InterpreterEvent | None] = asyncio.Queue()
        self._partial_seq = 0
        self._latest_partial: tuple[int, str] | None = None
        self._partial_event = asyncio.Event()
        self._partial_loop: asyncio.Task[None] | None = None
        self._last_partial_text = ""
        self._partial_translated_text = ""
        self._translations: set[asyncio.Task[None]] = set()
        self._translation_lock = asyncio.Lock()
        self._previous_raw = ""
        self._stopped = False
        self._cancelled = False
        self._audio_error: BaseException | None = None

    async def events(self) -> AsyncIterator[InterpreterEvent]:
        self._partial_loop = asyncio.create_task(self._translate_partials())
        worker = asyncio.create_task(self._run())
        try:
            while True:
                event = await self._queue.get()
                if event is None:
                    break
                yield event
        finally:
            self._stopped = True
            worker.cancel()
            self._partial_loop.cancel()
            for task in list(self._translations):
                task.cancel()
            await asyncio.gather(
                worker, self._partial_loop, *self._translations, return_exceptions=True
            )

    async def _run(self) -> None:
        try:
            await self._consume()
        except asyncio.CancelledError:
            raise
        except SttUnavailable as error:
            await self._emit_error("stt_unavailable", str(error))
        except InvalidAudio as error:
            await self._emit_error("invalid_audio", str(error))
        except Exception as error:  # noqa: BLE001 - the session must end with a contract error
            logger.exception("Interpreter session failed")
            await self._emit_error("internal_error", str(error))
        finally:
            await self._finish_translations()
            await self._queue.put(None)

    async def _consume(self) -> None:
        raw: asyncio.Queue[Sequence[float] | None] = asyncio.Queue()
        reader = asyncio.create_task(self._read_audio(raw))
        prefix: list[float] = []
        start_ms = 0
        try:
            while True:
                feeder = _WindowFeeder(
                    raw,
                    prefix=prefix,
                    max_samples=self._window_samples,
                    chunk_samples=self._chunk_samples,
                    carry_samples=self._overlap_samples,
                    start_ms=start_ms,
                )
                texts: list[str] = []
                language = self._source
                updates = self._stt.stream(feeder, language_code=self._source)
                async for update in updates:
                    if update.language:
                        language = update.language
                    texts.append(update.text.strip())
                    text = _join(texts)
                    await self._partial(text, update.pending, language, update.received_ms)

                if self._cancelled:
                    return
                raw_text = _join(texts)
                text = _dedupe(self._previous_raw, raw_text)
                self._previous_raw = raw_text
                if text:
                    segment = SegmentEvent(
                        id=uuid.uuid4().hex,
                        text=text,
                        language=language,
                        start_ms=max(0, feeder.start_ms),
                        end_ms=max(0, feeder.end_ms),
                    )
                    await self._queue.put(segment)
                    self._latest_partial = None
                    self._start_translation(segment)

                if feeder.finished:
                    break
                prefix = feeder.carry + feeder.leftover
                start_ms = max(0, feeder.end_ms - self._overlap_ms)
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
        if self._audio_error is not None:
            raise self._audio_error

    async def _read_audio(self, raw: asyncio.Queue[Sequence[float] | None]) -> None:
        try:
            async for chunk in self._audio:
                if chunk:
                    await raw.put(list(chunk))
        except InterpreterCancelled:
            self._cancelled = True
        except BaseException as error:  # noqa: BLE001 - re-raised after the window is closed
            self._audio_error = error
        finally:
            await raw.put(None)

    async def _partial(
        self, text: str, pending: str, language: str | None, received_ms: int
    ) -> None:
        pending = pending.strip()
        if not text and not pending:
            return
        self._partial_seq += 1
        seq = self._partial_seq
        await self._queue.put(PartialEvent(seq, text, pending, language, received_ms))
        if text and text != self._last_partial_text:
            self._latest_partial = (seq, text)
            self._last_partial_text = text
            self._partial_event.set()

    def _start_translation(self, segment: SegmentEvent) -> None:
        task = asyncio.create_task(self._translate_final(segment))
        self._translations.add(task)
        task.add_done_callback(self._translations.discard)

    async def _translate_final(self, segment: SegmentEvent) -> None:
        try:
            async with self._translation_lock:
                translated = await self._translate(segment.text)
        except (LlmUnavailable, LlmTimeout) as error:
            await self._emit_error(_translation_code(error), str(error), {"segment_id": segment.id})
            return
        except Exception as error:  # noqa: BLE001 - one failed translation must not kill the session
            logger.exception("Interpreter translation failed")
            await self._emit_error("internal_error", str(error), {"segment_id": segment.id})
            return
        if translated:
            await self._queue.put(TranslationEvent(segment.id, translated, self._target))

    async def _translate_partials(self) -> None:
        while not self._stopped:
            await self._partial_event.wait()
            self._partial_event.clear()
            if self._stopped:
                return
            await asyncio.sleep(self._debounce)
            if self._stopped:
                return
            latest = self._latest_partial
            if latest is None:
                continue
            seq, text = latest
            if text == self._partial_translated_text:
                continue
            try:
                async with self._translation_lock:
                    latest = self._latest_partial
                    if latest is None or latest != (seq, text):
                        continue
                    translated = await self._translate(text)
            except (LlmUnavailable, LlmTimeout) as error:
                await self._emit_error(_translation_code(error), str(error), {"seq": seq})
                continue
            except Exception as error:  # noqa: BLE001 - a partial is best-effort
                logger.exception("Interpreter partial translation failed")
                await self._emit_error("internal_error", str(error), {"seq": seq})
                continue
            if translated and self._latest_partial == (seq, text):
                await self._queue.put(PartialTranslationEvent(seq, translated, self._target))
                self._partial_translated_text = text

    async def _translate(self, text: str) -> str:
        request = TranslationRequest(
            text=text,
            target_language=self._target,
            source_language=self._source,
        )
        return (await self._llm.translate(request)).strip()

    async def _finish_translations(self) -> None:
        self._stopped = True
        self._partial_event.set()
        if self._partial_loop is not None:
            try:
                await asyncio.wait_for(self._partial_loop, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError):
                self._partial_loop.cancel()
        pending = [task for task in self._translations if not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _emit_error(
        self, code: str, detail: str, details: dict[str, Any] | None = None
    ) -> None:
        logger.warning("Interpreter %s: %s", code, detail)
        message = _ERROR_MESSAGES.get(code, _ERROR_MESSAGES["internal_error"])
        await self._queue.put(ErrorEvent(code, message, details or {}))


def _translation_code(error: Exception) -> str:
    return "llm_timeout" if isinstance(error, LlmTimeout) else "llm_unavailable"


def _join(texts: Sequence[str]) -> str:
    return " ".join(" ".join(texts).split())


_WORD = re.compile(r"[^\w']+", re.UNICODE)


def _dedupe(previous: str, current: str) -> str:
    """Remove the words of `current` already said at the end of `previous` (ADR-022 overlap)."""
    if not previous or not current:
        return current
    previous_words = [word for word in _WORD.split(previous.lower()) if word]
    current_words = [word for word in _WORD.split(current.lower()) if word]
    limit = min(len(previous_words), len(current_words))
    for size in range(limit, 0, -1):
        if previous_words[-size:] == current_words[:size]:
            tokens = current.split()
            return " ".join(tokens[size:])
    return current


class _WindowFeeder:
    """Async iterator of ~1 s chunks for one engine window (ADR-022).

    It owns the overlap: it keeps the last `carry_samples` of the audio it yielded and leaves the
    samples it read past the boundary in `leftover`, so the next window can start with both without
    losing or duplicating audio.
    """

    def __init__(
        self,
        raw: asyncio.Queue[Sequence[float] | None],
        *,
        prefix: Sequence[float],
        max_samples: int,
        chunk_samples: int,
        carry_samples: int,
        start_ms: int,
    ) -> None:
        self._raw = raw
        self._buffer = list(prefix)
        self._max_samples = max_samples
        self._chunk_samples = chunk_samples
        self._carry_samples = carry_samples
        self._start_ms = start_ms
        self._yielded = 0
        self._finished = False
        self._leftover: list[float] = []
        self._carry: list[float] = []
        self._window: list[float] = []
        self._exhausted = False

    @property
    def finished(self) -> bool:
        """True when the audio source ended inside this window."""
        return self._finished

    @property
    def leftover(self) -> list[float]:
        return self._leftover

    @property
    def carry(self) -> list[float]:
        return self._carry

    @property
    def start_ms(self) -> int:
        return self._start_ms

    @property
    def end_ms(self) -> int:
        return self._start_ms + round(self._yielded * 1000 / SAMPLE_RATE)

    def __aiter__(self) -> _WindowFeeder:
        return self

    async def __anext__(self) -> list[float]:
        if self._exhausted:
            raise StopAsyncIteration
        if self._yielded >= self._max_samples:
            self._leftover = self._buffer
            self._buffer = []
            self._exhausted = True
            raise StopAsyncIteration
        while len(self._buffer) < self._chunk_samples and not self._finished:
            item = await self._raw.get()
            if item is None:
                self._finished = True
                break
            self._buffer.extend(item)
        if not self._buffer:
            self._exhausted = True
            raise StopAsyncIteration
        take = min(
            self._chunk_samples,
            self._max_samples - self._yielded,
            len(self._buffer),
        )
        chunk = self._buffer[:take]
        del self._buffer[:take]
        self._yielded += take
        self._window.extend(chunk)
        if self._carry_samples:
            self._carry = self._window[-self._carry_samples :]
        return chunk
