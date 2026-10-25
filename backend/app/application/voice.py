"""Transcription of a clip the user recorded (F4 S1, S3).

The use case is thin on purpose: it holds the port, so `api/` never sees an adapter and the
language the caller forced is normalized once, here, before the engine reads it.
"""

from app.domain.errors import SpeechNotFound, TtsUnavailable
from app.ports.stt import SttPort, Transcription
from app.ports.tts import Speech, TtsPort


def normalize_language(code: str | None) -> str | None:
    """The language code as the engine expects it (`fr`), or `None` to let it detect the language.

    The UI sends what the language profile holds; a regional variant (`pt-BR`) keeps only its
    primary subtag because that is what the engine takes. An empty value means "detect it".
    """
    if code is None:
        return None
    primary = code.strip().lower().split("-")[0]
    return primary or None


class VoiceService:
    def __init__(self, *, stt: SttPort, tts: TtsPort | None = None) -> None:
        self._stt = stt
        self._tts = tts

    async def transcribe(self, *, audio: bytes, language_code: str | None) -> Transcription:
        """Transcribe one uploaded clip. Nothing is stored: the audio ends with the request (S7)."""
        return await self._stt.transcribe(audio, language_code=normalize_language(language_code))

    async def speak(
        self,
        *,
        text: str,
        language_code: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Speech:
        """Synthesize one clip and cache it by content (S4, ADR-016).

        Only the synthesized audio is stored, never the user's recording: this text is what the
        tutor already wrote or what the user asked to hear.
        """
        if self._tts is None:
            raise TtsUnavailable("no speech engine configured")
        return await self._tts.synthesize(
            text, language_code=normalize_language(language_code) or "", voice=voice, speed=speed
        )

    async def speech(self, cache_id: str) -> Speech:
        """A clip the cache already holds; anything else is `SpeechNotFound` (S4)."""
        if self._tts is None:
            raise TtsUnavailable("no speech engine configured")
        speech = await self._tts.get(cache_id)
        if speech is None:
            raise SpeechNotFound(cache_id)
        return speech
