"""Pi CLI adapter for the LLM port (F3 S1, S2, S6, S7).

The tutor is a Pi instance: one `pi --print --mode json` subprocess per invocation. Pi streams
JSONL records on stdout (`message_update` text deltas, an authoritative `message_end`,
`agent_settled`; see docs/json.md of pi-coding-agent 1.3.0) and this adapter turns them into text
deltas for the turn and into structured feedback for the closing call.

Nothing outside this package knows Pi exists (ADR-004). Every subprocess runs with all tools and
project resources disabled in a throwaway working directory, so the tutor can only read the prompt
it receives on stdin.

The closing call is a second, short invocation of the same isolated binary: it is asked for strict
JSON, and because a model does not always obey, `parse_turn_feedback` accepts a fenced or
surrounded object while refusing anything it cannot validate.
"""

import asyncio
import codecs
import contextlib
import json
import logging
import shutil
import tempfile
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from app.adapters.llm.prompt import FeedbackPrompt, TutorPrompt
from app.domain.errors import LlmTimeout, LlmUnavailable
from app.ports.llm import CorrectionDraft, TurnFeedback, TutorTurn, VocabularyDraft

logger = logging.getLogger(__name__)

# The tutor is a text assistant, not a coding agent: no tools, no repository files, no session
# state, no extensions, no MCP servers. See odd/tasks/f3-real-text-chat.md L5 (security risk).
_ISOLATION_FLAGS = (
    "--no-session",
    "--no-tools",
    "--no-builtin-tools",
    "--no-context-files",
    "--no-extensions",
    "--no-skills",
    "--no-mcp",
)

_FAILURE_MESSAGES = {
    "error": "El tutor no pudo responder. Vuelve a intentar en unos segundos.",
    "aborted": "La respuesta del tutor se interrumpió. Vuelve a intentar.",
    "timeout": "El tutor tardó demasiado en responder. Vuelve a intentar.",
}

_MALFORMED_FEEDBACK = "El tutor devolvió un cierre de turno ilegible. Vuelve a intentar."

# docs/api-contract.md §3: the cards of one turn are bounded, and the prompt asks for the same.
MAX_CORRECTIONS = 5
MAX_VOCABULARY_TERMS = 8


class PiCliAdapter:
    """`LlmPort` over the Pi CLI, one subprocess per invocation."""

    def __init__(
        self,
        *,
        command: Sequence[str] = ("pi",),
        model: str | None = None,
        timeout_seconds: float = 60.0,
        prompt: TutorPrompt | None = None,
        feedback_prompt: FeedbackPrompt | None = None,
    ) -> None:
        self._command = tuple(command)
        self._model = model or None
        self._timeout = timeout_seconds
        self._prompt = prompt or TutorPrompt.load()
        self._feedback = feedback_prompt or FeedbackPrompt.load()

    def _argv(self, system_prompt: str) -> list[str]:
        argv = [
            *self._command,
            "--print",
            "--mode",
            "json",
            *_ISOLATION_FLAGS,
            "--system-prompt",
            system_prompt,
        ]
        if self._model:
            argv.extend(["--model", self._model])
        return argv

    async def stream_reply(self, turn: TutorTurn) -> AsyncIterator[str]:
        argv = self._argv(self._prompt.render_system(turn.context))
        prompt = self._prompt.render_turn(turn)
        try:
            async with self._run(argv, prompt) as (process, stderr_task):
                async with asyncio.timeout(self._timeout):
                    async for delta in self._deltas(process.stdout):
                        yield delta
                    await process.wait()

                if process.returncode != 0:
                    self._log_failure(process.returncode, await stderr_task)
                    raise LlmUnavailable(_FAILURE_MESSAGES["error"])
        except TimeoutError as exc:
            raise LlmTimeout(_FAILURE_MESSAGES["timeout"]) from exc

    async def summarize_turn(self, turn: TutorTurn, reply: str) -> TurnFeedback:
        """Close the turn: a second short invocation that returns the structured feedback (S7)."""
        argv = self._argv(self._feedback.render_system(turn.context))
        prompt = self._feedback.render_turn(turn, reply)
        try:
            async with self._run(argv, prompt) as (process, stderr_task):
                async with asyncio.timeout(self._timeout):
                    answer = await self._collected(process.stdout)
                    await process.wait()

                if process.returncode != 0:
                    self._log_failure(process.returncode, await stderr_task)
                    raise LlmUnavailable(_FAILURE_MESSAGES["error"])
        except TimeoutError as exc:
            raise LlmTimeout(_FAILURE_MESSAGES["timeout"]) from exc

        return parse_turn_feedback(answer)

    @asynccontextmanager
    async def _run(self, argv: Sequence[str], prompt: str) -> AsyncIterator[tuple[Any, Any]]:
        """Run one isolated invocation and guarantee the subprocess and its cwd are released."""
        # A neutral cwd keeps project settings and context files out of the tutor's reach.
        workdir = tempfile.mkdtemp(prefix="polybot-tutor-")
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
        except BaseException:
            shutil.rmtree(workdir, ignore_errors=True)
            raise

        assert process.stdin and process.stdout and process.stderr  # guaranteed by PIPE
        stderr_task = asyncio.create_task(process.stderr.read())
        try:
            process.stdin.write(prompt.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
            yield process, stderr_task
        finally:
            stderr_task.cancel()
            await _terminate(process)
            shutil.rmtree(workdir, ignore_errors=True)

    async def _deltas(self, stdout: asyncio.StreamReader) -> AsyncIterator[str]:
        completed = False
        saw_text = False
        async for record in _records(stdout):
            kind = record.get("type")

            if kind == "message_update":
                event = record.get("assistantMessageEvent") or {}
                event_type = event.get("type")
                if event_type == "text_delta":
                    delta = event.get("delta")
                    if isinstance(delta, str) and delta:
                        saw_text = True
                        yield delta
                elif event_type == "error":
                    reason = str(event.get("reason") or "error")
                    logger.warning("pi stream error: %s", event.get("error"))
                    raise LlmUnavailable(_FAILURE_MESSAGES.get(reason, _FAILURE_MESSAGES["error"]))

            elif kind == "message_end":
                message = record.get("message") or {}
                if message.get("role") != "assistant":
                    continue
                stop_reason = message.get("stopReason")
                if stop_reason in _FAILURE_MESSAGES:
                    raise LlmUnavailable(_FAILURE_MESSAGES[stop_reason])
                completed = True

            elif kind == "agent_settled":
                break

        if not completed or not saw_text:
            raise LlmUnavailable(_FAILURE_MESSAGES["error"])

    async def _collected(self, stdout: asyncio.StreamReader) -> str:
        """Read the whole answer, preferring the authoritative `message_end` over the deltas."""
        completed = False
        chunks: list[str] = []
        async for record in _records(stdout):
            kind = record.get("type")

            if kind == "message_update":
                event = record.get("assistantMessageEvent") or {}
                event_type = event.get("type")
                if event_type == "error":
                    reason = str(event.get("reason") or "error")
                    logger.warning("pi stream error: %s", event.get("error"))
                    raise LlmUnavailable(_FAILURE_MESSAGES.get(reason, _FAILURE_MESSAGES["error"]))
                delta = event.get("delta")
                if event_type == "text_delta" and isinstance(delta, str):
                    chunks.append(delta)

            elif kind == "message_end":
                message = record.get("message") or {}
                if message.get("role") != "assistant":
                    continue
                stop_reason = message.get("stopReason")
                if stop_reason in _FAILURE_MESSAGES:
                    raise LlmUnavailable(_FAILURE_MESSAGES[stop_reason])
                # The final message replaces the deltas: the answer is never duplicated.
                chunks = [_message_text(message)]
                completed = True

            elif kind == "agent_settled":
                break

        if not completed:
            raise LlmUnavailable(_FAILURE_MESSAGES["error"])
        return "".join(chunks)

    @staticmethod
    def _log_failure(returncode: int, stderr: bytes) -> None:
        tail = stderr.decode("utf-8", errors="replace").strip().splitlines()
        logger.warning("pi exited with %s: %s", returncode, tail[-1] if tail else "(no stderr)")


def parse_turn_feedback(answer: str) -> TurnFeedback:
    """Turn the closing answer into feedback: tolerant envelope, strict content (S7).

    Accepts a plain object, a ```json fenced block or an object surrounded by prose, and extracts
    the first decodable JSON object. Anything that cannot be validated is an `LlmUnavailable`: the
    turn keeps its reply and the chat closes without feedback cards.
    """
    payload = _first_json_object(answer)
    if payload is None or not ("corrections" in payload or "vocabulary" in payload):
        raise LlmUnavailable(_MALFORMED_FEEDBACK)

    corrections: list[CorrectionDraft] = []
    for item in _items(payload, "corrections"):
        draft = _correction(item)
        if draft is not None:
            corrections.append(draft)
        if len(corrections) == MAX_CORRECTIONS:
            break

    vocabulary: list[VocabularyDraft] = []
    for item in _items(payload, "vocabulary"):
        draft = _vocabulary(item)
        if draft is not None:
            vocabulary.append(draft)
        if len(vocabulary) == MAX_VOCABULARY_TERMS:
            break

    return TurnFeedback(corrections=tuple(corrections), vocabulary=tuple(vocabulary))


def _first_json_object(answer: str) -> dict[str, Any] | None:
    """The first complete JSON object in the answer, fences and prose included."""
    decoder = json.JSONDecoder()
    index = answer.find("{")
    while index != -1:
        try:
            value, _ = decoder.raw_decode(answer, index)
        except json.JSONDecodeError:
            index = answer.find("{", index + 1)
            continue
        if isinstance(value, dict):
            return value
        index = answer.find("{", index + 1)
    return None


def _items(payload: dict[str, Any], name: str) -> list[Any]:
    """The list behind `name`; a missing key means nothing to report, a wrong type is malformed."""
    if name not in payload:
        return []
    value = payload[name]
    if not isinstance(value, list):
        raise LlmUnavailable(_MALFORMED_FEEDBACK)
    return value


def _correction(item: Any) -> CorrectionDraft | None:
    if not isinstance(item, dict):
        return None
    original = _text(item.get("original"))
    corrected = _text(item.get("corrected"))
    explanation = _text(item.get("explanation"))
    if original is None or corrected is None or explanation is None:
        return None
    return CorrectionDraft(original=original, corrected=corrected, explanation=explanation)


def _vocabulary(item: Any) -> VocabularyDraft | None:
    if not isinstance(item, dict):
        return None
    term = _text(item.get("term"))
    translation = _text(item.get("translation"))
    if term is None or translation is None:
        return None
    # `note` is optional: a blank or non-string value simply means there is nothing to add.
    return VocabularyDraft(term=term, translation=translation, note=_text(item.get("note")))


def _text(value: Any) -> str | None:
    """A non-empty, trimmed string, or `None` when the value cannot be rendered."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _message_text(message: dict[str, Any]) -> str:
    """The text blocks of an assistant message, in order."""
    parts = message.get("content") or []
    if not isinstance(parts, list):
        return ""
    return "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
    )


async def _records(stdout: asyncio.StreamReader) -> AsyncIterator[dict[str, Any]]:
    """Split stdout on LF only (docs/json.md framing) and decode UTF-8 incrementally."""
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
        raise LlmUnavailable(
            "El tutor devolvió una respuesta ilegible. Vuelve a intentar."
        ) from exc
    if not isinstance(record, dict):
        raise LlmUnavailable("El tutor devolvió una respuesta inesperada. Vuelve a intentar.")
    return record


async def _terminate(process: asyncio.subprocess.Process) -> None:
    """Kill the subprocess if it is still alive; cancellation must not leave it running."""
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
    with contextlib.suppress(Exception):
        await process.wait()
