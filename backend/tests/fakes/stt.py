"""Doubles of the STT port and of the engine behind it (F4 S1, S3; ADR-015).

The real adapter loads Whistle on this machine's CPU; the API tests need a predictable, offline
answer that also records what it was asked to transcribe.

`FakeStt` replaces the port, so `POST /voice/transcribe` is checked without any engine at all.
`FakeWhistleEngine` stands in for the `needle` package instead: the adapter is the real one, and
nothing is downloaded, loaded or resampled.
"""

import sys
import threading
import time
import types
from typing import Any

import pytest

from app.domain.errors import DomainError
from app.ports.stt import StreamUpdate, Transcription

# What the engine answers when a test does not say otherwise (the shape of the real answer).
DEFAULT_ENGINE_RESULT: dict[str, Any] = {
    "text": "hola mundo",
    "language": "es",
    "ttft_ms": 3.0,
    "decode_tps": 12.0,
}


# What the engine answers when a streaming test does not say otherwise (the shape of a chunk).
DEFAULT_STREAM_RESULT: dict[str, Any] = {
    "text": "hola",
    "pending": "",
    "language": "es",
    "received": 1.0,
    "pass_ms": 12.0,
}


class FakeStt:
    """`SttPort` double: a configured transcript, an optional failure, and the captured calls."""

    def __init__(
        self,
        text: str = "Bonjour, comment ça va ?",
        language_detected: str | None = "fr",
        duration_ms: int = 3000,
        failure: DomainError | None = None,
    ) -> None:
        self.text = text
        self.language_detected = language_detected
        self.duration_ms = duration_ms
        self.failure = failure
        # One entry per call, in order: the payload the endpoint received and the language asked.
        self.calls: list[tuple[bytes, str | None]] = []
        # Live stream double: one update per chunk, consumed across all windows of a session.
        self.stream_updates: list[StreamUpdate] = [
            StreamUpdate(text="Bonjour", pending="", language="fr", received_ms=1000)
        ]
        self.stream_index = 0
        self.stream_calls: list[str | None] = []
        self.stream_chunks: list[list[float]] = []
        self.stream_failure: DomainError | None = None

    async def transcribe(self, audio: bytes, *, language_code: str | None) -> Transcription:
        self.calls.append((audio, language_code))
        if self.failure is not None:
            raise self.failure
        return Transcription(
            text=self.text,
            language_detected=self.language_detected,
            duration_ms=self.duration_ms,
        )

    async def stream(self, chunks, *, language_code: str | None):
        """Consume the window and answer one update per chunk (F7)."""
        self.stream_calls.append(language_code)
        if self.stream_failure is not None:
            raise self.stream_failure
        async for chunk in chunks:
            self.stream_chunks.append(list(chunk))
            if self.stream_index < len(self.stream_updates):
                update = self.stream_updates[self.stream_index]
            else:
                update = StreamUpdate(
                    text=f"w{self.stream_index}",
                    pending="",
                    language="fr",
                    received_ms=(self.stream_index + 1) * 1000,
                )
            self.stream_index += 1
            yield update


class FakeWhistleEngine:
    """The `needle` module surface the adapter uses, recording what it was given."""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        failure: BaseException | None = None,
    ) -> None:
        self.result = DEFAULT_ENGINE_RESULT if result is None else result
        self.failure = failure
        # The audio objects handed to the engine, in order: samples, never a path (S7).
        self.audio: list[Any] = []
        # The forced language of each call: `None` means "detect it".
        self.languages: list[str | None] = []
        self.keywords: list[Any] = []
        # One entry per call: the thread the engine ran on, to prove it left the event loop.
        self.threads: list[str] = []
        # Live stream: one result per chunk, then any extra results as the tail.
        self.stream_results: list[dict[str, Any]] | None = None
        self.stream_audio: list[list[float]] = []
        self.stream_languages: list[str | None] = []
        self.stream_threads: list[str] = []
        self.stream_calls: int = 0
        self.stream_delay: float = 0.0

    def transcribe(
        self,
        audio: Any,
        language: str | None = None,
        keywords: Any = None,
        word_timestamps: bool = False,
        weights: Any = None,
    ) -> dict[str, Any]:
        self.audio.append(audio)
        self.languages.append(language)
        self.keywords.append(keywords)
        self.threads.append(threading.current_thread().name)
        if self.failure is not None:
            raise self.failure
        return self.result

    def stream(
        self,
        chunks,
        language: str | None = None,
        keywords: Any = None,
        weights: Any = None,
    ):
        """Consume the blocking chunk iterator and answer one dict per chunk (ADR-022)."""
        self.stream_calls += 1
        self.stream_languages.append(language)
        self.stream_threads.append(threading.current_thread().name)
        if self.failure is not None:
            raise self.failure
        results = self.stream_results
        if results is None:
            results = [DEFAULT_STREAM_RESULT]
        index = 0
        for chunk in chunks:
            if self.stream_delay:
                time.sleep(self.stream_delay)
            self.stream_audio.append(list(chunk))
            if index < len(results):
                yield dict(results[index])
            index += 1
        for result in results[index:]:
            yield dict(result)


def install_fake_needle(
    monkeypatch: pytest.MonkeyPatch, engine: FakeWhistleEngine
) -> types.ModuleType:
    """Put a fake `needle` in `sys.modules` so the adapter imports the double, not the package."""
    module = types.ModuleType("needle")
    module.transcribe = engine.transcribe  # type: ignore[attr-defined]
    module.stream = engine.stream  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "needle", module)
    return module
