"""The Piper adapter of the TTS port (F4 S4; ADR-016).

Tested against `tests/fixtures/fake_piper.py`, which takes the same command line and writes a real
WAV: real subprocesses, real files, no model.
"""

import asyncio
import sys
from pathlib import Path

import pytest

from app.adapters.tts.piper import PiperTtsAdapter
from app.domain.errors import TtsUnavailable, VoiceNotAvailable

FAKE_PIPER = Path(__file__).resolve().parents[1] / "fixtures" / "fake_piper.py"
SPEECH_TEXT = "Bonjour, comment allez-vous ?"


def make_voices(tmp_path: Path, *stems: str) -> Path:
    voices = tmp_path / "voices"
    voices.mkdir(parents=True, exist_ok=True)
    for stem in stems:
        (voices / f"{stem}.onnx").write_bytes(b"fake model")
    return voices


def make_adapter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str = "ok",
    *,
    stems: tuple[str, ...] = ("es_ES-davefx-medium", "fr_FR-siwis-medium"),
    timeout: float = 10.0,
) -> PiperTtsAdapter:
    monkeypatch.setenv("FAKE_PIPER_MODE", mode)
    return PiperTtsAdapter(
        command=(sys.executable, str(FAKE_PIPER)),
        voices_dir=make_voices(tmp_path, *stems),
        speech_dir=tmp_path / "speech",
        timeout_seconds=timeout,
    )


def speak(adapter: PiperTtsAdapter, **kwargs: object):
    return asyncio.run(
        adapter.synthesize(SPEECH_TEXT, language_code="fr", **kwargs)  # type: ignore[arg-type]
    )


def test_synthesize_returns_a_wav_and_a_content_addressed_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    speech = speak(make_adapter(monkeypatch, tmp_path))

    assert speech.media_type == "audio/wav"
    assert speech.audio[:4] == b"RIFF"
    assert len(speech.cache_id) == 64


def test_the_same_text_is_synthesized_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = make_adapter(monkeypatch, tmp_path)

    first = speak(adapter)
    second = speak(adapter)

    assert first.cache_id == second.cache_id
    assert second.audio == first.audio
    # One file in the cache, and the second call did not need another process to produce it.
    assert list((tmp_path / "speech").glob("*.wav")) == [
        tmp_path / "speech" / f"{first.cache_id}.wav"
    ]


def test_a_cached_clip_is_served_without_the_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = make_adapter(monkeypatch, tmp_path)
    speech = speak(adapter)

    stored = asyncio.run(adapter.get(speech.cache_id))

    assert stored is not None and stored.audio == speech.audio


def test_a_cache_id_cannot_escape_the_cache_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = make_adapter(monkeypatch, tmp_path)

    assert asyncio.run(adapter.get("../../etc/passwd")) is None
    assert asyncio.run(adapter.get("no-existe")) is None


def test_a_language_without_a_voice_is_a_domain_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = make_adapter(monkeypatch, tmp_path, stems=())

    with pytest.raises(VoiceNotAvailable):
        speak(adapter)


def test_an_unknown_voice_name_is_a_domain_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = make_adapter(monkeypatch, tmp_path)

    with pytest.raises(VoiceNotAvailable):
        speak(adapter, voice="../../etc/shadow")


def test_an_explicit_voice_is_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = make_adapter(monkeypatch, tmp_path, stems=("es_ES-davefx-medium",))
    argv_file = tmp_path / "argv.txt"
    monkeypatch.setenv("FAKE_PIPER_ARGV_FILE", str(argv_file))

    speech = asyncio.run(
        adapter.synthesize(SPEECH_TEXT, language_code="es", voice="es_ES-davefx-medium")
    )

    assert speech.audio[:4] == b"RIFF"
    assert "es_ES-davefx-medium.onnx" in argv_file.read_text(encoding="utf-8")


def test_speed_becomes_the_inverse_length_scale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = make_adapter(monkeypatch, tmp_path)
    argv_file = tmp_path / "argv.txt"
    text_file = tmp_path / "stdin.txt"
    monkeypatch.setenv("FAKE_PIPER_ARGV_FILE", str(argv_file))
    monkeypatch.setenv("FAKE_PIPER_TEXT_FILE", str(text_file))

    speak(adapter, speed=0.5)

    argv = argv_file.read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("--length_scale") + 1] == "2.000"
    assert text_file.read_text(encoding="utf-8") == SPEECH_TEXT


def test_a_failing_engine_is_tts_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(TtsUnavailable):
        speak(make_adapter(monkeypatch, tmp_path, mode="fail"))


def test_a_slow_engine_times_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(TtsUnavailable):
        speak(make_adapter(monkeypatch, tmp_path, mode="slow", timeout=0.3))


def test_a_missing_binary_is_tts_unavailable(tmp_path: Path) -> None:
    adapter = PiperTtsAdapter(
        command=(str(tmp_path / "no-such-piper"),),
        voices_dir=make_voices(tmp_path, "fr_FR-siwis-medium"),
        speech_dir=tmp_path / "speech",
        timeout_seconds=2.0,
    )

    with pytest.raises(TtsUnavailable):
        speak(adapter)
