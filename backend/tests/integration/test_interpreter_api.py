"""`WS /voice/interpret` (F7, ADR-022).

The endpoint is checked over the fake STT and LLM ports: no engine is loaded and no audio leaves
the test. The suite asserts the contract order (`ready` → `partial` → `segment` → `translation`),
the two ways a session ends (`stop` flushes, `cancel` discards) and the error envelope.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.application.interpreter import InterpreterService
from app.core.dependencies import get_ws_interpreter_service
from app.domain.errors import LlmUnavailable
from app.ports.stt import StreamUpdate
from tests.fakes.llm import FakeLlm
from tests.fakes.stt import FakeStt

URL = "/api/v1/voice/interpret"
SAMPLE_RATE = 16_000


def pcm(seconds: float = 1.0) -> bytes:
    return b"\x00\x00" * int(seconds * SAMPLE_RATE)


@pytest.fixture
def interpreter(api_client: TestClient, fake_stt: FakeStt, fake_llm: FakeLlm) -> InterpreterService:
    service = InterpreterService(stt=fake_stt, llm=fake_llm, debounce_seconds=0.01)
    api_client.app.dependency_overrides[get_ws_interpreter_service] = lambda: service
    return service


def receive_until_close(socket) -> list[dict]:
    events = []
    with pytest.raises(WebSocketDisconnect) as closed:
        while True:
            events.append(socket.receive_json())
    assert closed.value.code == 1000
    return events


def test_ready_then_partial_segment_and_translation(
    api_client: TestClient, interpreter: InterpreterService, fake_stt: FakeStt
) -> None:
    fake_stt.stream_updates = [
        StreamUpdate(text="Bonjour", pending="", language="fr", received_ms=1000)
    ]

    with api_client.websocket_connect(f"{URL}?source=fr&target=es") as socket:
        ready = socket.receive_json()
        assert ready == {
            "type": "ready",
            "format": "pcm_s16le",
            "sample_rate": 16000,
            "source": "fr",
            "target": "es",
        }
        socket.send_bytes(pcm())
        socket.send_json({"type": "stop"})
        events = receive_until_close(socket)

    kinds = [event["type"] for event in events if event["type"] != "partial_translation"]
    assert kinds == ["partial", "segment", "translation"]
    partial = next(event for event in events if event["type"] == "partial")
    segment = next(event for event in events if event["type"] == "segment")
    translation = next(event for event in events if event["type"] == "translation")
    assert partial["text"] == "Bonjour"
    assert segment["text"] == "Bonjour"
    assert translation["text"] == "¿Cómo estás?"
    assert translation["segment_id"] == segment["id"]


def test_a_missing_target_is_a_policy_error(api_client: TestClient) -> None:
    with api_client.websocket_connect(URL) as socket:
        error = socket.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()

    assert error["type"] == "error"
    assert error["error"]["code"] == "invalid_request"
    assert closed.value.code == 1008


def test_an_unsupported_source_is_a_policy_error(api_client: TestClient) -> None:
    with api_client.websocket_connect(f"{URL}?source=ja&target=es") as socket:
        error = socket.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()

    assert error["error"]["code"] == "unsupported_language"
    assert closed.value.code == 1008


def test_cancel_discards_the_window(
    api_client: TestClient, interpreter: InterpreterService, fake_stt: FakeStt
) -> None:
    with api_client.websocket_connect(f"{URL}?source=fr&target=es") as socket:
        socket.receive_json()
        socket.send_bytes(pcm())
        socket.send_json({"type": "cancel"})
        with pytest.raises(WebSocketDisconnect) as closed:
            while True:
                socket.receive_json()

    assert closed.value.code == 1000
    assert closed.value.reason == "cancelled"


def test_an_invalid_pcm_frame_is_a_1003_close(
    api_client: TestClient, interpreter: InterpreterService
) -> None:
    with api_client.websocket_connect(f"{URL}?source=fr&target=es") as socket:
        socket.receive_json()
        socket.send_bytes(b"\x00")
        error = socket.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()

    assert error["error"]["code"] == "invalid_audio"
    assert closed.value.code == 1003


def test_a_translation_failure_keeps_the_segment(
    api_client: TestClient, interpreter: InterpreterService, fake_llm: FakeLlm
) -> None:
    fake_llm.translation_failure = LlmUnavailable("provider down")

    with api_client.websocket_connect(f"{URL}?source=fr&target=es") as socket:
        socket.receive_json()
        socket.send_bytes(pcm())
        socket.send_json({"type": "stop"})
        events = receive_until_close(socket)

    kinds = [event["type"] for event in events]
    assert "segment" in kinds
    assert "translation" not in kinds
    assert any(
        event["type"] == "error" and event["error"]["code"] == "llm_unavailable" for event in events
    )
