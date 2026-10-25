"""`/voice/speech` and `/voice/speech/{id}` (F4 S4; ADR-016).

The engine is the `FakeTts` double: the tests assert what the endpoint asked for and what it sent
back, and the real Piper binary is exercised by `tests/unit/test_piper_adapter.py`.
"""

from app.domain.errors import TtsUnavailable, VoiceNotAvailable
from tests.fakes.tts import FAKE_WAV, FakeTts


def post_speech(api_client, **overrides: object):
    payload = {"text": "Bonjour, comment allez-vous ?", "language_code": "fr", **overrides}
    return api_client.post("/api/v1/voice/speech", json=payload)


def test_speech_returns_the_audio_and_a_cache_id(api_client, fake_tts: FakeTts) -> None:
    response = post_speech(api_client)

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == FAKE_WAV
    assert len(response.headers["x-speech-id"]) == 64
    assert fake_tts.asked == [
        {
            "text": "Bonjour, comment allez-vous ?",
            "language_code": "fr",
            "voice": None,
            "speed": 1.0,
        }
    ]


def test_voice_and_speed_travel_to_the_engine(api_client, fake_tts: FakeTts) -> None:
    response = post_speech(api_client, voice="fr_FR-siwis-medium", speed=0.5)

    assert response.status_code == 200
    assert fake_tts.asked[0]["voice"] == "fr_FR-siwis-medium"
    assert fake_tts.asked[0]["speed"] == 0.5


def test_the_same_text_keeps_the_same_id(api_client) -> None:
    first = post_speech(api_client)
    second = post_speech(api_client)

    assert first.headers["x-speech-id"] == second.headers["x-speech-id"]


def test_a_stored_clip_can_be_downloaded(api_client) -> None:
    created = post_speech(api_client)
    speech_id = created.headers["x-speech-id"]

    response = api_client.get(f"/api/v1/voice/speech/{speech_id}")

    assert response.status_code == 200
    assert response.content == FAKE_WAV
    assert response.headers["content-type"] == "audio/wav"


def test_an_unknown_clip_is_not_found(api_client) -> None:
    response = api_client.get("/api/v1/voice/speech/" + "0" * 64)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "speech_not_found"


def test_empty_text_is_a_validation_error(api_client, fake_tts: FakeTts) -> None:
    response = post_speech(api_client, text="   ")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_tts.asked == []


def test_too_long_text_is_a_validation_error(api_client, fake_tts: FakeTts) -> None:
    response = post_speech(api_client, text="a" * 2001)

    assert response.status_code == 422
    assert fake_tts.asked == []


def test_speed_outside_the_range_is_a_validation_error(api_client, fake_tts: FakeTts) -> None:
    response = post_speech(api_client, speed=0.4)

    assert response.status_code == 422
    assert fake_tts.asked == []


def test_a_missing_voice_is_an_error_envelope(api_client, fake_tts: FakeTts) -> None:
    fake_tts.failure = VoiceNotAvailable("no voice")

    response = post_speech(api_client)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "voice_not_available"
    assert "voz" in response.json()["error"]["message"]


def test_a_failing_engine_is_a_gateway_error(api_client, fake_tts: FakeTts) -> None:
    fake_tts.failure = TtsUnavailable("piper down")

    response = post_speech(api_client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "tts_unavailable"
