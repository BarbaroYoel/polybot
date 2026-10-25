"""`POST /voice/transcribe` (F4 S3).

The endpoint is checked twice: over the `FakeStt` port double for the contract payload and the
forwarded language, and over the real Whistle adapter with a fake engine for the failure modes the
adapter produces (corrupt audio, too long audio, an engine that blows up). No model is loaded.
"""

import io
import wave

import pytest
from fastapi.testclient import TestClient

from app.adapters.stt.whistle import WhistleSttAdapter
from app.core.dependencies import get_stt
from app.domain.errors import SttUnavailable
from tests.fakes.stt import FakeStt, FakeWhistleEngine, install_fake_needle

URL = "/api/v1/voice/transcribe"
SAMPLE_RATE = 16_000


def wav_bytes(seconds: float = 0.5) -> bytes:
    """A silent 16 kHz mono 16-bit WAV: the shape the browser records."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(b"\x00" * (int(seconds * SAMPLE_RATE) * 2))
    return buffer.getvalue()


def upload(client: TestClient, audio: bytes, language_code: str | None = None):
    data = {} if language_code is None else {"language_code": language_code}
    return client.post(URL, files={"audio": ("clip.wav", audio, "audio/wav")}, data=data)


@pytest.fixture
def real_adapter(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> FakeWhistleEngine:
    """The real adapter behind the endpoint, with a fake engine in `sys.modules`."""
    engine = FakeWhistleEngine()
    install_fake_needle(monkeypatch, engine)
    api_client.app.dependency_overrides[get_stt] = lambda: WhistleSttAdapter()
    return engine


def test_transcribing_a_clip_answers_the_contract_payload(
    api_client: TestClient, fake_stt: FakeStt
) -> None:
    audio = wav_bytes()

    response = upload(api_client, audio)

    assert response.status_code == 200
    assert response.json() == {
        "text": "Bonjour, comment ça va ?",
        "language_detected": "fr",
        "duration_ms": 3000,
    }
    # The port got the payload whole: the adapter, not the router, decides what to do with it.
    assert fake_stt.calls == [(audio, None)]


def test_the_language_code_is_forwarded_to_the_port(
    api_client: TestClient, fake_stt: FakeStt
) -> None:
    upload(api_client, wav_bytes(), language_code="fr")

    assert fake_stt.calls[0][1] == "fr"


def test_a_missing_audio_field_is_a_validation_error(
    api_client: TestClient, fake_stt: FakeStt
) -> None:
    response = api_client.post(URL)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_stt.calls == []


def test_an_empty_audio_field_is_a_validation_error(
    api_client: TestClient, fake_stt: FakeStt
) -> None:
    response = api_client.post(URL, files={"audio": ("clip.wav", b"", "audio/wav")})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_stt.calls == []


@pytest.mark.parametrize(
    "payload",
    [b"no soy un wav", b"RIFF....WAVEfmt ", b"garbage"],
)
def test_a_corrupt_audio_is_a_client_error(
    api_client: TestClient, real_adapter: FakeWhistleEngine, payload: bytes
) -> None:
    response = upload(api_client, payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_audio"
    assert real_adapter.audio == []


def test_a_wav_that_is_not_16k_mono_is_a_client_error(
    api_client: TestClient, real_adapter: FakeWhistleEngine
) -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(44_100)
        writer.writeframes(b"\x00" * 4_410)

    response = upload(api_client, buffer.getvalue())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_audio"
    # The engine would have raised about `soxr`: the adapter refuses the shape first.
    assert real_adapter.audio == []


def test_a_too_long_wav_is_a_payload_too_large(
    api_client: TestClient, real_adapter: FakeWhistleEngine
) -> None:
    response = upload(api_client, wav_bytes(121))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "audio_too_long"
    assert response.json()["error"]["message"]
    assert real_adapter.audio == []


def test_an_engine_failure_is_a_bad_gateway(
    api_client: TestClient, real_adapter: FakeWhistleEngine
) -> None:
    real_adapter.failure = RuntimeError("needle exploded")

    response = upload(api_client, wav_bytes())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "stt_unavailable"


def test_a_port_failure_reaches_the_client_with_its_own_code(
    api_client: TestClient, fake_stt: FakeStt
) -> None:
    fake_stt.failure = SttUnavailable("engine down")

    response = upload(api_client, wav_bytes())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "stt_unavailable"


def test_silence_answers_empty_text_not_an_error(
    api_client: TestClient, real_adapter: FakeWhistleEngine
) -> None:
    real_adapter.result = {"text": "", "language": "es", "ttft_ms": 1.0, "decode_tps": 2.0}

    response = upload(api_client, wav_bytes())

    assert response.status_code == 200
    assert response.json() == {"text": "", "language_detected": "es", "duration_ms": 500}
