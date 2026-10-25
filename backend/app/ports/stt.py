"""The STT port (F4 S1, S3).

`application/` depends on this protocol; the engine that runs the model is an adapter detail
(ADR-004). Whistle is one adapter, not a dependency of the domain or of the use cases, and it is
the adapter — not this port — that knows about WAV headers, threads and temporary files.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Transcription:
    """One transcript (docs/api-contract.md §3).

    `text` is empty when the clip had no speech: the engine answers "" for silence by design, and an
    empty transcript is an answer, not a failure. `language_detected` is `None` when the engine did
    not report the language it used; it is never guessed from the forced one.
    """

    text: str
    language_detected: str | None
    duration_ms: int


class SttPort(Protocol):
    async def transcribe(self, audio: bytes, *, language_code: str | None) -> Transcription:
        """Transcribe one audio payload — the 16 kHz mono 16-bit WAV the browser records.

        The port takes the raw bytes, so the adapter owns the engine and any temporary file it
        needs; the audio is never persisted (S7). `language_code` forces the language of the clip
        and `None` asks the engine to detect it.

        An empty payload, a corrupt file or a shape the engine cannot take is an `InvalidAudio`;
        more audio than the limit is an `AudioTooLong`; a failing engine is `SttUnavailable`. An
        empty transcript is not an error.
        """
