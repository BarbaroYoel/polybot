"""The live interpreter session without the WebSocket (F7, ADR-022).

These tests drive `InterpreterService` with the fake ports: no engine, no model and no network. The
contract behaviour lives here — window boundaries, overlap deduplication, partial translations and
the two ways a session stops.
"""

import asyncio

import pytest

from app.application.interpreter import (
    ErrorEvent,
    InterpreterCancelled,
    InterpreterService,
    PartialTranslationEvent,
    SegmentEvent,
    TranslationEvent,
    _dedupe,
)
from app.domain.errors import SttUnavailable
from app.ports.stt import StreamUpdate
from tests.fakes.llm import FakeLlm
from tests.fakes.stt import FakeStt

RATE = 16_000


@pytest.fixture
def fake_stt() -> FakeStt:
    return FakeStt()


@pytest.fixture
def fake_llm() -> FakeLlm:
    return FakeLlm()


def chunks(count: int, delay: float = 0.0):
    async def audio():
        for _ in range(count):
            if delay:
                await asyncio.sleep(delay)
            yield [0.0] * RATE

    return audio


def run(service: InterpreterService, audio) -> list:
    async def collect():
        return [event async for event in service.events(audio(), source="fr", target="es")]

    return asyncio.run(collect())


def service(stt: FakeStt, llm: FakeLlm, *, debounce: float = 0.05) -> InterpreterService:
    return InterpreterService(stt=stt, llm=llm, debounce_seconds=debounce)


def test_the_session_resets_the_engine_every_window(fake_stt: FakeStt, fake_llm: FakeLlm) -> None:
    fake_stt.stream_updates = [
        StreamUpdate(text=f"w{index}", pending="", language="fr", received_ms=(index + 1) * 1000)
        for index in range(6)
    ]

    events = run(service(fake_stt, fake_llm), chunks(6))
    segments = [event for event in events if isinstance(event, SegmentEvent)]

    assert len(segments) == 2
    assert (segments[0].start_ms, segments[0].end_ms) == (0, 4500)
    assert (segments[1].start_ms, segments[1].end_ms) == (4000, 6000)
    # One fresh engine stream per window: the continuous stream degrades after ~5 s (T0).
    assert fake_stt.stream_calls == ["fr", "fr"]


def test_the_final_translation_follows_the_segment(fake_stt: FakeStt, fake_llm: FakeLlm) -> None:
    events = run(service(fake_stt, fake_llm), chunks(1))

    segments = [event for event in events if isinstance(event, SegmentEvent)]
    translations = [event for event in events if isinstance(event, TranslationEvent)]

    assert len(segments) == 1
    assert len(translations) == 1
    assert translations[0].segment_id == segments[0].id
    assert translations[0].text == "¿Cómo estás?"


def test_partial_translations_are_best_effort_and_do_not_block_the_final_one(
    fake_stt: FakeStt, fake_llm: FakeLlm
) -> None:
    fake_stt.stream_updates = [
        StreamUpdate(text=f"w{index}", pending="", language="fr", received_ms=(index + 1) * 1000)
        for index in range(3)
    ]

    events = run(service(fake_stt, fake_llm, debounce=0.01), chunks(3, delay=0.1))

    assert [event for event in events if isinstance(event, PartialTranslationEvent)]
    assert [event for event in events if isinstance(event, TranslationEvent)]
    # At least one partial plus the final segment asked the provider (P5).
    assert len(fake_llm.translations) >= 2


def test_cancel_stops_without_emitting_a_segment(fake_stt: FakeStt, fake_llm: FakeLlm) -> None:
    async def audio():
        yield [0.0] * RATE
        raise InterpreterCancelled

    events = run(service(fake_stt, fake_llm), audio)

    assert not [event for event in events if isinstance(event, SegmentEvent)]
    assert [event for event in events if isinstance(event, TranslationEvent)] == []


def test_an_stt_failure_is_an_error_event(fake_stt: FakeStt, fake_llm: FakeLlm) -> None:
    fake_stt.stream_failure = SttUnavailable("engine down")

    events = run(service(fake_stt, fake_llm), chunks(1))

    errors = [event for event in events if isinstance(event, ErrorEvent)]
    assert [error.code for error in errors] == ["stt_unavailable"]
    assert not [event for event in events if isinstance(event, SegmentEvent)]


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (
            "ask not what your country can do for you",
            "for you ask what you can do",
            "ask what you can do",
        ),
        ("Bonjour, comment ça va ?", "ça va bien", "bien"),
        ("bonjour", "salut", "salut"),
        ("", "bonjour", "bonjour"),
    ],
)
def test_dedupe_removes_the_overlap(previous: str, current: str, expected: str) -> None:
    assert _dedupe(previous, current) == expected
