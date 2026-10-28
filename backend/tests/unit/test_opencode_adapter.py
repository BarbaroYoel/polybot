"""The OpenCode CLI adapter (ADR-019).

The adapter is tested against `tests/fixtures/fake_opencode.py`, which speaks the JSONL `text`
events of `opencode run --format json`. That keeps the tests deterministic and offline while still
exercising real subprocesses, pipes, cancellation and timeouts.
"""

import asyncio
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.adapters.llm.opencode import OpenCodeCliAdapter
from app.domain.entities import CefrLevel, MessageAuthor
from app.domain.errors import LlmTimeout, LlmUnavailable
from app.ports.llm import (
    LessonReviewItem,
    LessonReviewRequest,
    TranslationRequest,
    TurnMessage,
    TutorContext,
    TutorTurn,
)

FAKE_OPENCODE = Path(__file__).resolve().parents[1] / "fixtures" / "fake_opencode.py"


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


def make_adapter(monkeypatch: pytest.MonkeyPatch, mode: str, **kwargs: float) -> OpenCodeCliAdapter:
    monkeypatch.setenv("FAKE_OPENCODE_MODE", mode)
    return OpenCodeCliAdapter(
        command=[sys.executable, str(FAKE_OPENCODE)],
        model="test/model#variant",
        timeout_seconds=kwargs.get("timeout_seconds", 30.0),
    )


def collect(adapter: OpenCodeCliAdapter) -> list[str]:
    async def run() -> list[str]:
        return [delta async for delta in adapter.stream_reply(make_turn())]

    return asyncio.run(run())


def make_review_request() -> LessonReviewRequest:
    return LessonReviewRequest(
        context=make_turn().context,
        lesson_title="Pedir algo en un café",
        items=[
            LessonReviewItem(
                prompt="Pedir un café",
                answer="Je voudrais un café",
                expected="Je voudrais un café",
                correct=True,
            )
        ],
    )


def test_stream_reply_yields_text_parts_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "ok")

    assert collect(adapter) == ["Bonjour", " !"]


def test_a_part_resent_as_it_grows_yields_only_the_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = make_adapter(monkeypatch, "cumulative")

    assert collect(adapter) == ["Bonjour", " !"]


def test_the_prompt_carries_system_context_history_and_turn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    monkeypatch.setenv("FAKE_OPENCODE_PROMPT_FILE", str(prompt_file))
    adapter = make_adapter(monkeypatch, "ok")

    collect(adapter)
    sent = prompt_file.read_text(encoding="utf-8")

    # The system half carries the language context (F3 S3); the turn half follows it.
    assert "Francés" in sent and "A1" in sent and "fr" in sent
    assert "Bonjour, je m'appelle Ana." in sent
    assert "Je voudrais un café, s'il vous plaît." in sent
    assert sent.index("Francés") < sent.index("Bonjour, je m'appelle Ana.")


def test_the_cli_is_invoked_with_the_configured_agent_and_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    argv_file = tmp_path / "argv.txt"
    prompt_file = tmp_path / "prompt.txt"
    monkeypatch.setenv("FAKE_OPENCODE_ARGV_FILE", str(argv_file))
    monkeypatch.setenv("FAKE_OPENCODE_PROMPT_FILE", str(prompt_file))
    adapter = make_adapter(monkeypatch, "ok")

    collect(adapter)
    argv = argv_file.read_text(encoding="utf-8").splitlines()
    sent = prompt_file.read_text(encoding="utf-8")

    assert argv[:4] == ["run", "--format", "json", "--agent"]
    assert "plan" in argv
    assert "--model" in argv and "test/model#variant" in argv
    assert "--" in argv
    assert sent.startswith("# Tutor de idiomas")


def test_the_tutor_runs_outside_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cwd_file = tmp_path / "cwd.txt"
    monkeypatch.setenv("FAKE_OPENCODE_CWD_FILE", str(cwd_file))
    adapter = make_adapter(monkeypatch, "ok")

    collect(adapter)
    cwd = Path(cwd_file.read_text(encoding="utf-8")).resolve()

    assert cwd.name.startswith("polybot-opencode-")
    assert "/workspaces/polybot" not in str(cwd)


def test_stream_reply_raises_on_a_provider_error_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = make_adapter(monkeypatch, "error")

    with pytest.raises(LlmUnavailable):
        collect(adapter)


def test_stream_reply_raises_when_the_cli_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_a_runaway_reply_is_cut_instead_of_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "huge")

    with pytest.raises(LlmUnavailable):
        collect(adapter)


def test_a_missing_executable_is_a_provider_failure() -> None:
    adapter = OpenCodeCliAdapter(command=["/nonexistent/polybot-opencode"])

    with pytest.raises(LlmUnavailable):
        collect(adapter)
    with pytest.raises(LlmUnavailable):
        asyncio.run(adapter.review_lesson(make_review_request()))


def test_closing_the_stream_terminates_the_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "pid.txt"
    monkeypatch.setenv("FAKE_OPENCODE_PID_FILE", str(pid_file))
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
    pytest.fail(f"the OpenCode subprocess {pid} survived the cancelled stream")


def test_a_slow_turn_times_out_instead_of_hanging(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "slow", timeout_seconds=0.5)

    async def scenario() -> Iterator[str]:
        return [delta async for delta in adapter.stream_reply(make_turn())]

    started = time.monotonic()
    with pytest.raises(LlmTimeout):
        asyncio.run(scenario())
    assert time.monotonic() - started < 10


def test_the_subprocess_runs_in_its_own_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "pid.txt"
    monkeypatch.setenv("FAKE_OPENCODE_PID_FILE", str(pid_file))
    adapter = make_adapter(monkeypatch, "slow")

    async def scenario() -> int:
        stream = adapter.stream_reply(make_turn())
        assert await anext(stream) == "Bon"
        pid = int(pid_file.read_text(encoding="utf-8"))
        assert os.getsid(pid) == pid
        await stream.aclose()
        return pid

    asyncio.run(scenario())


def test_summarize_turn_parses_the_closing_json(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "feedback-json")

    feedback = asyncio.run(adapter.summarize_turn(make_turn(), "Bonjour !"))

    assert feedback.corrections[0].corrected == "Je suis allé au café hier."
    assert feedback.vocabulary[0].term == "un café"


def test_summarize_turn_fails_on_prose_instead_of_guessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = make_adapter(monkeypatch, "feedback-broken")

    with pytest.raises(LlmUnavailable):
        asyncio.run(adapter.summarize_turn(make_turn(), "Bonjour !"))


def test_translate_returns_the_sentence_and_unwraps_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = make_adapter(monkeypatch, "translate-quoted")

    translation = asyncio.run(
        adapter.translate(TranslationRequest(text="How are you?", target_language="es"))
    )

    assert translation == "¿Cómo estás?"


def test_an_empty_translation_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "translate-empty")

    with pytest.raises(LlmUnavailable):
        asyncio.run(
            adapter.translate(TranslationRequest(text="How are you?", target_language="es"))
        )


def test_review_lesson_returns_the_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(monkeypatch, "lesson")

    comment = asyncio.run(adapter.review_lesson(make_review_request()))

    assert "Muy bien" in comment
