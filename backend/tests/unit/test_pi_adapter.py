"""The Pi CLI adapter (F3 S1, S2, S3, S6).

The adapter is tested against `tests/fixtures/fake_pi.py`, which speaks the same JSONL protocol
as `pi --print --mode json` (docs/json.md of pi-coding-agent 1.3.0). That keeps the tests
deterministic and offline while still exercising real subprocesses, pipes and cancellation.
"""

import asyncio
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.adapters.llm.pi import PiCliAdapter
from app.domain.entities import CefrLevel, MessageAuthor
from app.domain.errors import LlmTimeout, LlmUnavailable
from app.ports.llm import TurnMessage, TutorContext, TutorTurn

FAKE_PI = Path(__file__).resolve().parents[1] / "fixtures" / "fake_pi.py"


def make_turn() -> TutorTurn:
    return TutorTurn(
        context=TutorContext(
            language_name="Francés",
            language_code="fr",
            level=CefrLevel.A1,
            explanation_language="es",
        ),
        history=[
            TurnMessage(author=MessageAuthor.USER, content="Bonjour, je m'appelle Ana."),
            TurnMessage(author=MessageAuthor.TUTOR, content="Bonjour Ana ! Comment ça va ?"),
        ],
        user_message="Je voudrais un café, s'il vous plaît.",
    )


def make_adapter(monkeypatch: pytest.MonkeyPatch, mode: str, **kwargs: float) -> PiCliAdapter:
    monkeypatch.setenv("FAKE_PI_MODE", mode)
    return PiCliAdapter(
        command=[sys.executable, str(FAKE_PI)],
        timeout_seconds=kwargs.get("timeout_seconds", 30.0),
    )


def collect(adapter: PiCliAdapter) -> list[str]:
    async def run() -> list[str]:
        return [delta async for delta in adapter.stream_reply(make_turn())]

    return asyncio.run(run())


def test_stream_reply_yields_text_deltas_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "ok")

    assert collect(adapter) == ["Bonjour", " !"]


def test_stream_reply_ignores_thinking_and_tool_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    # `fake_pi` emits thinking_start/thinking_delta before the text: only text reaches the caller.
    adapter = make_adapter(monkeypatch, "ok")

    assert "debo saludar" not in "".join(collect(adapter))


def test_prompt_carries_context_history_and_the_new_turn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    system_file = tmp_path / "system.txt"
    monkeypatch.setenv("FAKE_PI_PROMPT_FILE", str(prompt_file))
    monkeypatch.setenv("FAKE_PI_SYSTEM_FILE", str(system_file))
    adapter = make_adapter(monkeypatch, "ok")

    collect(adapter)
    sent = prompt_file.read_text(encoding="utf-8")
    system = system_file.read_text(encoding="utf-8")

    # The system prompt carries the language context (F3 S3).
    assert "Francés" in system and "A1" in system and "fr" in system
    # The turn prompt carries the history and the new message, oldest first.
    assert "Bonjour, je m'appelle Ana." in sent
    assert "Je voudrais un café, s'il vous plaît." in sent
    assert sent.index("Bonjour, je m'appelle Ana.") < sent.index("Je voudrais un café")
    # The full prompt never travels through argv: only the system prompt does.
    assert "Je voudrais un café" not in system


def test_the_repository_stays_out_of_reach(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    argv_file = tmp_path / "argv.txt"
    monkeypatch.setenv("FAKE_PI_ARGV_FILE", str(argv_file))
    adapter = make_adapter(monkeypatch, "ok")

    collect(adapter)
    argv = argv_file.read_text(encoding="utf-8").splitlines()

    for flag in (
        "--print",
        "--no-session",
        "--no-tools",
        "--no-builtin-tools",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-mcp",
    ):
        assert flag in argv
    assert "--system-prompt" in argv
    assert "--mode" in argv and "json" in argv


def test_stream_reply_raises_on_a_provider_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "error")

    with pytest.raises(LlmUnavailable):
        collect(adapter)


def test_stream_reply_raises_when_the_cli_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "fail")

    with pytest.raises(LlmUnavailable):
        collect(adapter)


def test_a_malformed_record_is_reported_instead_of_silently_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = make_adapter(monkeypatch, "garbage")

    with pytest.raises(LlmUnavailable):
        collect(adapter)


def test_an_empty_reply_is_reported_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "empty")

    with pytest.raises(LlmUnavailable):
        collect(adapter)


def test_closing_the_stream_terminates_the_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "pid.txt"
    monkeypatch.setenv("FAKE_PI_PID_FILE", str(pid_file))
    adapter = make_adapter(monkeypatch, "slow")

    async def scenario() -> int:
        stream = adapter.stream_reply(make_turn())
        assert await anext(stream) == "Bon"
        await stream.aclose()
        return int(pid_file.read_text(encoding="utf-8"))

    pid = asyncio.run(scenario())

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    pytest.fail(f"the Pi subprocess {pid} survived the cancelled stream")


def test_a_slow_turn_times_out_instead_of_hanging(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "slow", timeout_seconds=0.5)

    async def scenario() -> Iterator[str]:
        return [delta async for delta in adapter.stream_reply(make_turn())]

    started = time.monotonic()
    with pytest.raises(LlmTimeout):
        asyncio.run(scenario())
    assert time.monotonic() - started < 10
