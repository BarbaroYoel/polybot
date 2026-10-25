"""The TTS port (F4 S4; ADR-003, ADR-016).

`application/` depends on this protocol; the engine that speaks is an adapter detail (ADR-004).
Piper is one adapter: a subprocess with a local voice, not a dependency of the use cases.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Speech:
    """One synthesized clip (docs/api-contract.md §3 «Voz»).

    `cache_id` is content-addressed: the same text, voice and speed always produce the same id, so
    `GET /voice/speech/{id}` can serve what a previous `POST` synthesized without asking the engine.
    """

    audio: bytes
    media_type: str
    cache_id: str


class TtsPort(Protocol):
    async def synthesize(
        self,
        text: str,
        *,
        language_code: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Speech:
        """Speak `text` in the language of `language_code`.

        A language with no installed voice is a `VoiceNotAvailable`; an engine that fails or takes
        too long is a `TtsUnavailable`. The result is cached by content, so repeating the same call
        never runs the engine twice.
        """

    async def get(self, cache_id: str) -> Speech | None:
        """A previously synthesized clip, or `None` when it is not in the cache."""
