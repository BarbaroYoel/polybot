"""The Whistle adapter against a fake engine (F4 S1, S3; ADR-015).

The suite never imports the real `needle`: the tests inject a fake module in `sys.modules`, so no
model is downloaded, no engine is loaded and no audio leaves the machine. Two properties are
checked from the outside — the adapter runs the blocking engine off the event loop, and it hands
the engine samples in memory, never a temporary file (S7).
"""

import array
import asyncio
import io
import os
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from app.adapters.stt.whistle import MAX_SECONDS, WhistleSttAdapter
from app.domain.errors import AudioTooLong, InvalidAudio, SttUnavailable
from app.ports.stt import Transcription
from tests.fakes.stt import FakeWhistleEngine, install_fake_needle

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_RATE = 16_000

# A fake engine package that records, at import time, whether telemetry was already off. It is
# imported for real from `tmp_path`, so the ordering is observed and not just asserted.
FAKE_NEEDLE_PACKAGE = """\
import os
from pathlib import Path

Path(__file__).with_name("imports.log").write_text(
    os.environ.get("NEEDLE_TELEMETRY", "")
)


def transcribe(audio, language=None, keywords=None, word_timestamps=False, weights=None):
    return {"text": "hola mundo", "language": "es", "ttft_ms": 1.0, "decode_tps": 2.0}
"""


def wav_bytes(
    seconds: float = 1.0,
    *,
    sample_rate: int = SAMPLE_RATE,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """A silent WAV of the requested shape: 16 kHz mono 16-bit unless the test says otherwise."""
    frames = int(seconds * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(sample_rate)
        writer.writeframes(b"\x00" * (frames * channels * sample_width))
    return buffer.getvalue()


def transcribe(audio: bytes, language_code: str | None = None) -> Transcription:
    """Run the real adapter once, on the fake engine currently in `sys.modules`."""
    return asyncio.run(WhistleSttAdapter().transcribe(audio, language_code=language_code))


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> FakeWhistleEngine:
    """A fake `needle` in `sys.modules`: the adapter's import finds the double."""
    fake = FakeWhistleEngine()
    install_fake_needle(monkeypatch, fake)
    return fake


def test_the_adapter_module_does_not_import_the_engine() -> None:
    # `main.py` imports the adapter at startup: the engine (and its model) must wait for the first
    # request, in a fresh interpreter so the ordering is real.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, app.adapters.stt.whistle; print('needle' in sys.modules)",
        ],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert probe.stdout.strip() == "False"


def test_telemetry_is_disabled_before_the_engine_is_imported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    package = tmp_path / "needle"
    package.mkdir()
    (package / "__init__.py").write_text(FAKE_NEEDLE_PACKAGE, encoding="utf-8")
    monkeypatch.delitem(os.environ, "NEEDLE_TELEMETRY", raising=False)
    monkeypatch.syspath_prepend(str(tmp_path))
    assert "needle" not in sys.modules

    try:
        transcribe(wav_bytes())
        imported_with = (package / "imports.log").read_text(encoding="utf-8")
    finally:
        # The fake package was imported for real: do not leak it into the rest of the suite.
        sys.modules.pop("needle", None)

    assert imported_with == "0"
    assert os.environ["NEEDLE_TELEMETRY"] == "0"


def test_a_forced_language_is_forwarded_to_the_engine(engine: FakeWhistleEngine) -> None:
    audio = wav_bytes(0.5)

    result = transcribe(audio, "fr")

    assert engine.languages == ["fr"]
    assert result.text == "hola mundo"


def test_detection_asks_for_no_language_and_reports_the_engine_one(
    engine: FakeWhistleEngine,
) -> None:
    engine.result = {"text": "bonjour", "language": "fr", "ttft_ms": 1.0, "decode_tps": 2.0}

    result = transcribe(wav_bytes())

    assert engine.languages == [None]
    assert result.language_detected == "fr"


def test_a_missing_engine_language_is_not_guessed(engine: FakeWhistleEngine) -> None:
    engine.result = {"text": "bonjour", "ttft_ms": 1.0, "decode_tps": 2.0}

    assert transcribe(wav_bytes()).language_detected is None


def test_the_duration_comes_from_the_wav_frames(engine: FakeWhistleEngine) -> None:
    result = transcribe(wav_bytes(2.5))

    assert result.duration_ms == 2500


def test_an_empty_transcript_is_a_valid_answer(engine: FakeWhistleEngine) -> None:
    # Whistle answers "" for silence by design: that is the answer, not a failure (S3).
    engine.result = {"text": "", "language": "en", "ttft_ms": 1.0, "decode_tps": 2.0}

    result = transcribe(wav_bytes())

    assert result == Transcription(text="", language_detected="en", duration_ms=1000)


def test_an_engine_failure_is_stt_unavailable(engine: FakeWhistleEngine) -> None:
    engine.failure = RuntimeError("needle_last_error: engine exploded")

    with pytest.raises(SttUnavailable):
        transcribe(wav_bytes())


def test_an_unusable_engine_answer_is_stt_unavailable(engine: FakeWhistleEngine) -> None:
    engine.result = ["not", "a", "dict"]  # type: ignore[assignment]

    with pytest.raises(SttUnavailable):
        transcribe(wav_bytes())


@pytest.mark.parametrize("payload", [b"", b"no soy un wav", b"RIFF....WAVEfmt "])
def test_a_payload_that_is_not_a_wav_is_invalid_audio(
    engine: FakeWhistleEngine, payload: bytes
) -> None:
    with pytest.raises(InvalidAudio):
        transcribe(payload)

    assert engine.audio == []


@pytest.mark.parametrize(
    ("sample_rate", "channels", "sample_width"),
    [
        (22_050, 1, 2),  # the extra `soxr` would be needed: refused here, not by the engine
        (48_000, 1, 2),
        (SAMPLE_RATE, 2, 2),
        (SAMPLE_RATE, 1, 1),
        (SAMPLE_RATE, 1, 4),
    ],
)
def test_an_unsupported_wav_shape_is_invalid_audio_before_the_engine_is_touched(
    engine: FakeWhistleEngine, sample_rate: int, channels: int, sample_width: int
) -> None:
    audio = wav_bytes(0.5, sample_rate=sample_rate, channels=channels, sample_width=sample_width)

    with pytest.raises(InvalidAudio):
        transcribe(audio)

    # The engine would have raised its own RuntimeError; the domain error must come first, so a
    # wrong sample rate is never mistaken for an unavailable engine (S3).
    assert engine.audio == []


def test_a_clip_over_the_limit_is_audio_too_long(engine: FakeWhistleEngine) -> None:
    with pytest.raises(AudioTooLong):
        transcribe(wav_bytes(MAX_SECONDS + 1))

    assert engine.audio == []


def test_a_clip_of_exactly_the_limit_is_accepted(engine: FakeWhistleEngine) -> None:
    result = transcribe(wav_bytes(MAX_SECONDS))

    assert result.duration_ms == MAX_SECONDS * 1000
    assert len(engine.audio) == 1


def test_the_engine_gets_raw_samples_and_no_temp_file_is_written(
    engine: FakeWhistleEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the adapter must not write the audio to disk (S7)")

    monkeypatch.setattr("tempfile.mkstemp", forbidden)
    monkeypatch.setattr("tempfile.NamedTemporaryFile", forbidden)
    monkeypatch.setattr("tempfile.TemporaryFile", forbidden)

    transcribe(wav_bytes(0.5))

    samples = engine.audio[0]
    assert isinstance(samples, array.array)
    assert samples.typecode == "f"
    assert len(samples) == SAMPLE_RATE // 2
    assert all(-1.0 <= value <= 1.0 for value in samples)


def test_the_engine_runs_off_the_event_loop(engine: FakeWhistleEngine) -> None:
    transcribe(wav_bytes(0.5))

    # A blocking engine call on the loop would stall every other request (docs/conventions.md §2).
    assert engine.threads and engine.threads[0] != "MainThread"
