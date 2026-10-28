"""`/voice`: what the user said and what the tutor says back (F4 S3, S4).

The endpoint is `multipart/form-data` per docs/api-contract.md §3: the browser posts the recorded
clip and, when the UI knows it, the language of the audio. The audio is read into memory, handed to
the use case and dropped with the request: nothing is persisted (S7).
"""

import array
import json
import sys
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, StringConstraints
from starlette.websockets import WebSocketDisconnected

from app.application.interpreter import (
    ErrorEvent,
    InterpreterCancelled,
    InterpreterEvent,
    InterpreterService,
    PartialEvent,
    PartialTranslationEvent,
    SegmentEvent,
    TranslationEvent,
)
from app.application.voice import VoiceService, normalize_language
from app.core.dependencies import get_voice_service, get_ws_interpreter_service
from app.domain.errors import InvalidAudio

router = APIRouter(tags=["voice"])

# Whistle's seven languages; the target can be any language the tutor explains in.
STT_LANGUAGES = frozenset({"en", "de", "fr", "es", "it", "nl", "pl"})

# A frame of two seconds at 16 kHz mono 16-bit: more than the contract's ~1 s and still bounded.
MAX_FRAME_BYTES = 16_000 * 2 * 2


class TranscriptionOut(BaseModel):
    """Contract §3: what the engine heard, the language it used and how long the clip was."""

    text: str
    language_detected: str | None
    duration_ms: int


# The clip is bounded by contract §5 (120 s) and by the WAV shape the engine takes (16 kHz mono
# 16-bit); the adapter rejects anything else, and an empty upload is a schema error here.
AudioUpload = Annotated[
    bytes, File(min_length=1, description="16 kHz mono 16-bit WAV, up to 120 s")
]
LanguageCodeForm = Annotated[
    str | None, Form(description="Language of the audio; detect if absent")
]


SpeechText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
SpeechLanguage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=8)
]
VoiceName = Annotated[
    str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class SpeechRequest(BaseModel):
    """Contract §3: what to say, in which language, with which voice and at which speed."""

    text: SpeechText
    language_code: SpeechLanguage
    voice: VoiceName = None
    # 0.5 is slow, 2.0 is fast; the adapter translates it to Piper's length scale.
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


# `audio/wav` is what Piper writes: mono 16-bit at 22.05 kHz.
_SPEECH_RESPONSES = {
    200: {"content": {"audio/wav": {}}, "description": "The synthesized clip"},
    400: {"description": "`voice_not_available`: no installed voice for that language"},
    404: {"description": "`speech_not_found`: the cached clip does not exist"},
    502: {"description": "`tts_unavailable`: the engine failed or is not installed"},
}


@router.post("/voice/transcribe", response_model=TranscriptionOut, summary="Transcribe a clip")
async def transcribe(
    audio: AudioUpload,
    language_code: LanguageCodeForm = None,
    service: VoiceService = Depends(get_voice_service),
) -> TranscriptionOut:
    transcription = await service.transcribe(audio=audio, language_code=language_code)
    return TranscriptionOut(
        text=transcription.text,
        language_detected=transcription.language_detected,
        duration_ms=transcription.duration_ms,
    )


@router.post(
    "/voice/speech",
    summary="Synthesize a clip with Piper (F4 S4)",
    responses=_SPEECH_RESPONSES,
)
async def speak(
    payload: SpeechRequest,
    service: VoiceService = Depends(get_voice_service),
) -> Response:
    """Return the audio and its cache id, so the UI can replay it without asking again (ADR-016)."""
    speech = await service.speak(
        text=payload.text,
        language_code=payload.language_code,
        voice=payload.voice,
        speed=payload.speed,
    )
    return Response(
        content=speech.audio,
        media_type=speech.media_type,
        headers={
            "X-Speech-Id": speech.cache_id,
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.get(
    "/voice/speech/{speech_id}",
    summary="Download a synthesized clip (F4 S4)",
    responses=_SPEECH_RESPONSES,
)
async def get_speech(
    speech_id: str,
    service: VoiceService = Depends(get_voice_service),
) -> Response:
    """Serve a clip the cache already holds; `404 speech_not_found` when it is gone."""
    speech = await service.speech(speech_id)
    return Response(content=speech.audio, media_type=speech.media_type)


def _pcm_to_samples(data: bytes) -> list[float]:
    """Decode one PCM frame from the browser: 16 kHz mono 16-bit little-endian (ADR-022)."""
    if not data:
        raise InvalidAudio("empty frame")
    if len(data) % 2:
        raise InvalidAudio("odd PCM frame")
    if len(data) > MAX_FRAME_BYTES:
        raise InvalidAudio("frame too large")
    shorts = array.array("h")
    shorts.frombytes(data)
    if sys.byteorder == "big":
        shorts.byteswap()
    return [sample / 32768.0 for sample in shorts]


def _error_payload(
    request_id: str,
    code: str,
    message: str,
    details: dict | None = None,
) -> dict:
    """The contract §4 envelope, also used on the WebSocket (ADR-022)."""
    return {
        "type": "error",
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        },
    }


def _event_payload(event: InterpreterEvent, request_id: str) -> dict:
    if isinstance(event, PartialEvent):
        return {
            "type": "partial",
            "seq": event.seq,
            "text": event.text,
            "pending": event.pending,
            "language": event.language,
            "received_ms": event.received_ms,
        }
    if isinstance(event, PartialTranslationEvent):
        return {
            "type": "partial_translation",
            "seq": event.seq,
            "text": event.text,
            "target": event.target,
        }
    if isinstance(event, SegmentEvent):
        return {
            "type": "segment",
            "id": event.id,
            "text": event.text,
            "language": event.language,
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
        }
    if isinstance(event, TranslationEvent):
        return {
            "type": "translation",
            "segment_id": event.segment_id,
            "text": event.text,
            "target": event.target,
        }
    return _error_payload(request_id, event.code, event.message, event.details)


async def _close_with_error(
    websocket: WebSocket,
    request_id: str,
    code: str,
    message: str,
    details: dict | None,
    close_code: int,
) -> None:
    try:
        await websocket.send_json(_error_payload(request_id, code, message, details))
        await websocket.close(code=close_code, reason=code)
    except (WebSocketDisconnect, WebSocketDisconnected):
        return


@router.websocket("/voice/interpret")
async def interpret(
    websocket: WebSocket,
    service: InterpreterService = Depends(get_ws_interpreter_service),
) -> None:
    """Live interpreter: client PCM frames in, transcript and translation events out (F7)."""
    await websocket.accept()
    request_id = uuid.uuid4().hex
    source = normalize_language(websocket.query_params.get("source"))
    target = (websocket.query_params.get("target") or "").strip()

    if not target or len(target) > 8:
        await _close_with_error(
            websocket,
            request_id,
            "invalid_request",
            "Elegí un idioma de destino para interpretar.",
            {},
            1008,
        )
        return
    if source is not None and source not in STT_LANGUAGES:
        await _close_with_error(
            websocket,
            request_id,
            "unsupported_language",
            "El intérprete aún no tiene voz para ese idioma de origen.",
            {"source": source},
            1008,
        )
        return

    await websocket.send_json(
        {
            "type": "ready",
            "format": "pcm_s16le",
            "sample_rate": 16_000,
            "source": source,
            "target": target,
        }
    )

    cancelled = False

    async def audio() -> AsyncIterator[list[float]]:
        nonlocal cancelled
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                # A dropped client is a cancelled session, not an engine failure.
                raise InterpreterCancelled from None
            if message["type"] == "websocket.disconnect":
                raise InterpreterCancelled
            data = message.get("bytes")
            if data is not None:
                yield _pcm_to_samples(data)
                continue
            raw = message.get("text")
            if not raw:
                continue
            try:
                control = json.loads(raw)
            except json.JSONDecodeError as error:
                raise InvalidAudio("invalid control message") from error
            kind = control.get("type")
            if kind == "stop":
                return
            if kind == "cancel":
                cancelled = True
                raise InterpreterCancelled
            raise InvalidAudio(f"unknown control message: {kind}")

    error_code: str | None = None
    try:
        async for event in service.events(audio(), source=source, target=target):
            if isinstance(event, ErrorEvent):
                error_code = event.code
            await websocket.send_json(_event_payload(event, request_id))
    except WebSocketDisconnect:
        return
    except InvalidAudio:
        await _close_with_error(
            websocket,
            request_id,
            "invalid_audio",
            "No pudimos leer ese audio. Enviá PCM de 16 kHz mono 16 bits.",
            {},
            1003,
        )
        return
    finally:
        if error_code in {"stt_unavailable", "internal_error"}:
            close_code = 1011
        elif error_code == "invalid_audio":
            close_code = 1003
        else:
            close_code = 1000
        try:
            await websocket.close(code=close_code, reason="cancelled" if cancelled else "stopped")
        except (WebSocketDisconnect, WebSocketDisconnected):
            # The client may have gone away before this cleanup; the session is already over.
            pass
