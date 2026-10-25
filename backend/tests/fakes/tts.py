"""A deterministic double of the `TtsPort` (F4 S4, ADR-016)."""

import hashlib

from app.domain.errors import DomainError
from app.ports.tts import Speech

# The smallest thing a browser accepts as a WAV: the tests care about the bytes travelling, not
# about what they sound like.
FAKE_WAV = b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 28


class FakeTts:
    """`TtsPort` double: records every ask, answers content-addressed bytes, can fail on purpose."""

    def __init__(
        self,
        audio: bytes = FAKE_WAV,
        failure: DomainError | None = None,
        get_failure: DomainError | None = None,
    ) -> None:
        self.audio = audio
        self.failure = failure
        self.get_failure = get_failure
        self.calls: list[dict[str, object]] = []
        self.clips: dict[str, Speech] = {}

    async def synthesize(
        self,
        text: str,
        *,
        language_code: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Speech:
        self.calls.append(
            {"text": text, "language_code": language_code, "voice": voice, "speed": speed}
        )
        if self.failure is not None:
            raise self.failure
        cache_id = hashlib.sha256(
            f"{language_code}|{voice}|{speed:.2f}|{text}".encode()
        ).hexdigest()
        speech = Speech(audio=self.audio, media_type="audio/wav", cache_id=cache_id)
        self.clips[cache_id] = speech
        return speech

    async def get(self, cache_id: str) -> Speech | None:
        if self.get_failure is not None:
            raise self.get_failure
        return self.clips.get(cache_id)

    @property
    def asked(self) -> list[dict[str, object]]:
        """What the endpoint asked for, in order."""
        return list(self.calls)
