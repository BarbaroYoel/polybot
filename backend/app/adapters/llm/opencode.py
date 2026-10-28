"""OpenCode CLI adapter for the LLM port (ADR-019).

One `opencode run --format json` subprocess per invocation, against the OpenCode background service
(`opencode serve`). The tutor runs in a throwaway working directory with the read-only `plan` agent:
it can answer text, but it cannot modify the repository. The model is configured, not hardcoded
(`OPENCODE_MODEL`), because each installation authorises different providers.

OpenCode emits JSONL events on stdout. Only `text` parts become reply deltas; `error` records and a
non-zero exit are provider failures. The closing turn, translation and lesson comment reuse the same
`parsing` rules as the Pi adapter, so a provider change cannot change what a usable answer is.
"""

import asyncio
import codecs
import contextlib
import json
import logging
import os
import shutil
import signal
import tempfile
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from app.adapters.llm.parsing import (
    MAX_LESSON_COMMENT_CHARS,
    MAX_REPLY_CHARS,
    UNREADABLE_ANSWER_MESSAGE,
    parse_translation,
    parse_turn_feedback,
)
from app.adapters.llm.prompt import (
    FeedbackPrompt,
    LessonReviewPrompt,
    TranslationPrompt,
    TutorPrompt,
)
from app.domain.errors import LlmTimeout, LlmUnavailable
from app.ports.llm import (
    LessonReviewRequest,
    TranslationRequest,
    TurnFeedback,
    TutorTurn,
)

logger = logging.getLogger(__name__)

_FAILURE_MESSAGES = {
    "error": "El tutor no pudo responder. Vuelve a intentar en unos segundos.",
    "timeout": "El tutor tardó demasiado en responder. Vuelve a intentar.",
}

_EMPTY_LESSON_COMMENT = "El tutor no devolvió un comentario. Vuelve a intentar."


class OpenCodeCliAdapter:
    """`LlmPort` over the OpenCode CLI, one subprocess per invocation (ADR-019)."""

    def __init__(
        self,
        *,
        command: Sequence[str] = ("opencode",),
        model: str | None = None,
        agent: str = "plan",
        translation_agent: str | None = None,
        timeout_seconds: float = 90.0,
        prompt: TutorPrompt | None = None,
        feedback_prompt: FeedbackPrompt | None = None,
        translation_prompt: TranslationPrompt | None = None,
        lesson_review_prompt: LessonReviewPrompt | None = None,
    ) -> None:
        self._command = tuple(command)
        self._model = model or None
        self._agent = agent
        # The `plan` agent narrates its own role; a translation-only agent keeps the answer clean
        # (F7 T6). Defaults to the tutor agent so existing configurations do not change.
        self._translation_agent = translation_agent or agent
        self._timeout = timeout_seconds
        self._prompt = prompt or TutorPrompt.load()
        self._feedback = feedback_prompt or FeedbackPrompt.load()
        self._translation = translation_prompt or TranslationPrompt.load()
        self._lesson_review = lesson_review_prompt or LessonReviewPrompt.load()

    def _argv(self, prompt: str, *, agent: str | None = None) -> list[str]:
        argv = [
            *self._command,
            "run",
            "--format",
            "json",
            "--agent",
            agent or self._agent,
        ]
        if self._model:
            argv.extend(["--model", self._model])
        # `--` keeps a prompt that starts with a dash from being read as a flag.
        argv.extend(["--", prompt])
        return argv

    @staticmethod
    def _full_prompt(system: str, turn: str) -> str:
        """OpenCode has no `--system-prompt`: both halves travel in the message, system first."""
        return f"{system.rstrip()}\n\n{turn.lstrip()}"

    async def stream_reply(self, turn: TutorTurn) -> AsyncIterator[str]:
        prompt = self._full_prompt(
            self._prompt.render_system(turn.context), self._prompt.render_turn(turn)
        )
        try:
            async with asyncio.timeout(self._timeout):
                async with self._run(prompt) as (process, stderr_task):
                    async for delta in self._deltas(process.stdout):
                        yield delta
                    await process.wait()

                    if process.returncode != 0:
                        self._log_failure(process.returncode, await stderr_task)
                        raise LlmUnavailable(_FAILURE_MESSAGES["error"])
        except TimeoutError as exc:
            raise LlmTimeout(_FAILURE_MESSAGES["timeout"]) from exc

    async def summarize_turn(self, turn: TutorTurn, reply: str) -> TurnFeedback:
        """Close the turn: the same provider, asked for strict JSON (S7)."""
        prompt = self._full_prompt(
            self._feedback.render_system(turn.context),
            self._feedback.render_turn(turn, reply),
        )
        return parse_turn_feedback(await self._complete(prompt))

    async def review_lesson(self, request: LessonReviewRequest) -> str:
        """One short invocation for the lesson comment; best-effort in the caller (F5 S2)."""
        prompt = self._full_prompt(
            self._lesson_review.render_system(request.context),
            self._lesson_review.render_turn(request),
        )
        answer = (await self._complete(prompt)).strip()
        if not answer:
            raise LlmUnavailable(_EMPTY_LESSON_COMMENT)
        return answer[:MAX_LESSON_COMMENT_CHARS]

    async def translate(self, request: TranslationRequest) -> str:
        """One short invocation that returns only the translation (ADR-014)."""
        prompt = self._full_prompt(
            self._translation.render_system(request),
            self._translation.render_turn(request),
        )
        return parse_translation(await self._complete(prompt, agent=self._translation_agent))

    async def _complete(self, prompt: str, *, agent: str | None = None) -> str:
        """Run one invocation to the end and return the whole answer."""
        try:
            async with asyncio.timeout(self._timeout):
                async with self._run(prompt, agent=agent) as (process, stderr_task):
                    answer = await self._collected(process.stdout)
                    await process.wait()

                    if process.returncode != 0:
                        self._log_failure(process.returncode, await stderr_task)
                        raise LlmUnavailable(_FAILURE_MESSAGES["error"])
        except TimeoutError as exc:
            raise LlmTimeout(_FAILURE_MESSAGES["timeout"]) from exc

        return answer

    @asynccontextmanager
    async def _run(
        self, prompt: str, *, agent: str | None = None
    ) -> AsyncIterator[tuple[Any, Any]]:
        """Run one isolated invocation and guarantee the subprocess and its cwd are released."""
        # A neutral cwd keeps project settings and context files out of the tutor's reach.
        workdir = tempfile.mkdtemp(prefix="polybot-opencode-")
        try:
            process = await asyncio.create_subprocess_exec(
                *self._argv(prompt, agent=agent),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                # Its own session lets `_terminate` kill the whole group, children included.
                start_new_session=True,
            )
        except OSError as exc:
            # A missing or non-executable binary is the provider failing to start, not a bug in the
            # API: every caller already degrades on `LlmUnavailable`.
            shutil.rmtree(workdir, ignore_errors=True)
            logger.warning("opencode could not start: %s", type(exc).__name__)
            raise LlmUnavailable(_FAILURE_MESSAGES["error"]) from exc
        except BaseException:
            shutil.rmtree(workdir, ignore_errors=True)
            raise

        assert process.stdout and process.stderr  # guaranteed by PIPE
        stderr_task = asyncio.create_task(process.stderr.read())
        try:
            yield process, stderr_task
        finally:
            stderr_task.cancel()
            await _terminate(process)
            shutil.rmtree(workdir, ignore_errors=True)

    async def _deltas(self, stdout: asyncio.StreamReader) -> AsyncIterator[str]:
        saw_text = False
        written = 0
        seen: dict[str, str] = {}

        async for record in _records(stdout):
            kind = record.get("type")

            if kind == "error":
                # Only the type: the payload can carry provider-side detail.
                logger.warning("opencode returned an error record")
                raise LlmUnavailable(_FAILURE_MESSAGES["error"])

            if kind != "text":
                continue

            part = record.get("part") or {}
            text = part.get("text")
            if not isinstance(text, str) or not text:
                continue

            part_id = part.get("id")
            if isinstance(part_id, str):
                previous = seen.get(part_id, "")
                # Some providers resend the whole part as it grows: yield only the suffix.
                delta = text[len(previous) :] if text.startswith(previous) else text
                seen[part_id] = text
            else:
                delta = text

            if not delta:
                continue
            written += len(delta)
            if written > MAX_REPLY_CHARS:
                raise LlmUnavailable(_FAILURE_MESSAGES["error"])
            saw_text = True
            yield delta

        if not saw_text:
            raise LlmUnavailable(_FAILURE_MESSAGES["error"])

    async def _collected(self, stdout: asyncio.StreamReader) -> str:
        """Read the whole answer, keeping the newest text of each part in arrival order."""
        order: list[str] = []
        parts: dict[str, str] = {}
        anonymous: list[str] = []

        async for record in _records(stdout):
            kind = record.get("type")

            if kind == "error":
                logger.warning("opencode returned an error record")
                raise LlmUnavailable(_FAILURE_MESSAGES["error"])

            if kind != "text":
                continue

            part = record.get("part") or {}
            text = part.get("text")
            if not isinstance(text, str) or not text:
                continue

            part_id = part.get("id")
            if isinstance(part_id, str):
                if part_id not in parts:
                    order.append(part_id)
                parts[part_id] = text
            else:
                anonymous.append(text)

        answer = "".join(parts[part_id] for part_id in order) + "".join(anonymous)
        if not answer.strip():
            raise LlmUnavailable(_FAILURE_MESSAGES["error"])
        return answer

    @staticmethod
    def _log_failure(returncode: int, stderr: bytes) -> None:
        tail = stderr.decode("utf-8", errors="replace").strip().splitlines()
        logger.warning(
            "opencode exited with %s: %s", returncode, tail[-1] if tail else "(no stderr)"
        )


async def _records(stdout: asyncio.StreamReader) -> AsyncIterator[dict[str, Any]]:
    """Split stdout on LF only and decode UTF-8 incrementally."""
    decoder = codecs.getincrementaldecoder("utf-8")()
    buffer = ""
    while True:
        chunk = await stdout.read(4096)
        if not chunk:
            break
        buffer += decoder.decode(chunk)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            record = _parse_record(line)
            if record is not None:
                yield record

    buffer += decoder.decode(b"", final=True)
    record = _parse_record(buffer)
    if record is not None:
        yield record


def _parse_record(line: str) -> dict[str, Any] | None:
    line = line.rstrip("\r")
    if not line.strip():
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError as exc:
        raise LlmUnavailable(UNREADABLE_ANSWER_MESSAGE) from exc
    if not isinstance(record, dict):
        raise LlmUnavailable(UNREADABLE_ANSWER_MESSAGE)
    return record


async def _terminate(process: asyncio.subprocess.Process) -> None:
    """Kill the subprocess group if it is still alive; cancellation leaves nothing running."""
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            # `start_new_session=True` made the child a group leader: kill its children too.
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with contextlib.suppress(Exception):
        await process.wait()
