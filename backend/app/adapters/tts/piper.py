"""The Piper adapter of the TTS port (F4 S4; ADR-016).

Piper runs as a subprocess, the way the tutor runs `pi`: the binary and its voices are files on this
machine, so the text never leaves it and the backend gains no inference runtime. Three details carry
the adapter:

1. **One process per phrase.** `piper` reads the text from stdin and writes a WAV; the call is
   blocking, so it runs off the event loop.
2. **Content-addressed cache.** The id is `sha256(voz|velocidad|texto)`: asking twice for the same
   sentence returns the stored clip without starting the engine again.
3. **Nothing half-written.** The engine writes to `<id>.wav.part` and the file is renamed only when
   the process exits cleanly, so a dropped call never leaves a truncated clip in the cache.

Nothing outside this package knows Piper exists (ADR-004).
"""

import asyncio
import hashlib
import logging
import re
from pathlib import Path

from app.domain.errors import TtsUnavailable, VoiceNotAvailable
from app.ports.tts import Speech

logger = logging.getLogger(__name__)

# The voice installed for each language of Whistle (ADR-015): the stems of the `.onnx` files.
# The `high` models are the best Piper offers per language; French has none, so it keeps `medium`.
DEFAULT_VOICES: dict[str, str] = {
    "en": "en_US-lessac-high",
    "de": "de_DE-thorsten-high",
    "fr": "fr_FR-siwis-medium",
    "es": "es_MX-claude-high",
    "it": "it_IT-paola-medium",
    "nl": "nl_NL-mls-medium",
    "pl": "pl_PL-darkman-medium",
}

MEDIA_TYPE = "audio/wav"
_CACHE_ID = re.compile(r"^[0-9a-f]{64}$")


class PiperTtsAdapter:
    """`TtsPort` over the Piper binary: one voice per language, one cache directory."""

    def __init__(
        self,
        *,
        command: tuple[str, ...] = ("piper",),
        voices_dir: Path,
        speech_dir: Path,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._command = command
        self._voices_dir = voices_dir
        self._speech_dir = speech_dir
        self._timeout = timeout_seconds

    async def synthesize(
        self,
        text: str,
        *,
        language_code: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> Speech:
        model = self._resolve_voice(language_code, voice)
        cache_id = _cache_id(text, model.stem, speed)
        cached = await self.get(cache_id)
        if cached is not None:
            return cached

        self._speech_dir.mkdir(parents=True, exist_ok=True)
        target = self._speech_dir / f"{cache_id}.wav"
        partial = target.with_suffix(".part")
        await self._run(model, text, speed, partial)
        partial.replace(target)
        audio = await asyncio.to_thread(target.read_bytes)
        return Speech(audio=audio, media_type=MEDIA_TYPE, cache_id=cache_id)

    async def get(self, cache_id: str) -> Speech | None:
        # The id comes from the URL: only a hex digest can name a file in the cache.
        if not _CACHE_ID.match(cache_id):
            return None
        path = self._speech_dir / f"{cache_id}.wav"
        if not path.is_file():
            return None
        audio = await asyncio.to_thread(path.read_bytes)
        return Speech(audio=audio, media_type=MEDIA_TYPE, cache_id=cache_id)

    def _resolve_voice(self, language_code: str, voice: str | None) -> Path:
        """The `.onnx` of the requested voice, or the language's default (ADR-016)."""
        stem = voice or DEFAULT_VOICES.get(language_code.lower())
        if stem is None:
            raise VoiceNotAvailable(f"no default voice for {language_code}")
        model = (self._voices_dir / f"{stem}.onnx").resolve()
        # A voice name must not escape the voices directory.
        if model.parent != self._voices_dir.resolve() or not model.is_file():
            raise VoiceNotAvailable(stem)
        return model

    async def _run(self, model: Path, text: str, speed: float, output: Path) -> None:
        argv = [
            *self._command,
            "--model",
            str(model),
            "--output_file",
            str(output),
            # Piper slows down when the scale grows, so the UI speed is its inverse.
            "--length_scale",
            f"{1 / speed:.3f}",
        ]
        try:
            async with asyncio.timeout(self._timeout):
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate(text.encode("utf-8"))
                if process.returncode != 0:
                    tail = stderr.decode("utf-8", errors="replace").strip().splitlines()
                    logger.warning("piper exited with %s: %s", process.returncode, tail[-1:])
                    raise TtsUnavailable("piper failed")
        except TimeoutError as error:
            raise TtsUnavailable("piper timed out") from error
        except FileNotFoundError as error:
            # The binary is missing: the feature is unavailable, the app is not broken (ADR-016).
            raise TtsUnavailable(f"{self._command[0]} not found") from error


def _cache_id(text: str, voice: str, speed: float) -> str:
    """Stable id for one clip: the same text, voice and speed always land in the same file."""
    payload = f"{voice}|{speed:.2f}|{text}".encode()
    return hashlib.sha256(payload).hexdigest()
