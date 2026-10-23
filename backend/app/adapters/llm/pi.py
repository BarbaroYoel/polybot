"""Pi CLI adapter for the LLM port (F3 S1, S2, S6).

The tutor is a Pi instance: one `pi --print --mode json` subprocess per turn. Pi streams JSONL
records on stdout (`message_update` text deltas, an authoritative `message_end`, `agent_settled`;
see docs/json.md of pi-coding-agent 1.3.0) and this adapter turns them into text deltas.

Nothing outside this package knows Pi exists (ADR-004). The subprocess runs with every tool and
project resource disabled in a throwaway working directory, so the tutor can only read the prompt
it receives on stdin.
"""

import asyncio
import codecs
import contextlib
import json
import logging
import shutil
import tempfile
from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.adapters.llm.prompt import TutorPrompt
from app.domain.errors import LlmTimeout, LlmUnavailable
from app.ports.llm import TutorContext, TutorTurn

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
}


class PiCliAdapter:
    """`LlmPort` over the Pi CLI, one subprocess per turn."""

    def __init__(
        self,
        *,
        command: Sequence[str] = ("pi",),
        model: str | None = None,
        timeout_seconds: float = 60.0,
        prompt: TutorPrompt | None = None,
    ) -> None:
        self._command = tuple(command)
        self._model = model or None
        self._timeout = timeout_seconds
        self._prompt = prompt or TutorPrompt.load()

    def _argv(self, context: TutorContext) -> list[str]:
        argv = [
            *self._command,
            "--print",
            "--mode",
            "json",
            *_ISOLATION_FLAGS,
            "--system-prompt",
            self._prompt.render_system(context),
        ]
        if self._model:
            argv.extend(["--model", self._model])
        return argv

    async def stream_reply(self, turn: TutorTurn) -> AsyncIterator[str]:
        argv = self._argv(turn.context)
        prompt = self._prompt.render_turn(turn)
        # A neutral cwd keeps project settings and context files out of the tutor's reach.
        workdir = tempfile.mkdtemp(prefix="polybot-tutor-")
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
        )
        assert process.stdin and process.stdout and process.stderr  # guaranteed by PIPE
        stderr_task = asyncio.create_task(process.stderr.read())
        try:
            process.stdin.write(prompt.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

            async with asyncio.timeout(self._timeout):
                async for delta in self._deltas(process.stdout):
                    yield delta
                await process.wait()

            if process.returncode != 0:
                self._log_failure(process.returncode, await stderr_task)
                raise LlmUnavailable(_FAILURE_MESSAGES["error"])
        except TimeoutError as exc:
            raise LlmTimeout("El tutor tardó demasiado en responder. Vuelve a intentar.") from exc
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

    @staticmethod
    def _log_failure(returncode: int, stderr: bytes) -> None:
        tail = stderr.decode("utf-8", errors="replace").strip().splitlines()
        logger.warning("pi exited with %s: %s", returncode, tail[-1] if tail else "(no stderr)")


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
