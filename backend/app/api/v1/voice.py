"""`/voice`: what the user said and what the tutor says back (F4 S3, S4).

The endpoint is `multipart/form-data` per docs/api-contract.md §3: the browser posts the recorded
clip and, when the UI knows it, the language of the audio. The audio is read into memory, handed to
the use case and dropped with the request: nothing is persisted (S7).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response
from pydantic import BaseModel, Field, StringConstraints

from app.application.voice import VoiceService
from app.core.dependencies import get_voice_service

router = APIRouter(tags=["voice"])


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
