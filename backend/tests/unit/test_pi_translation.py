"""The Pi adapter's translation operation (S5, ADR-014).

Same harness as `test_pi_adapter.py`: `tests/fixtures/fake_pi.py` speaks the CLI's JSONL protocol,
so the translation runs through real pipes and a real subprocess, offline and deterministic.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from app.adapters.llm.pi import PiCliAdapter
from app.domain.errors import LlmTimeout, LlmUnavailable
from app.ports.llm import TranslationRequest

FAKE_PI = Path(__file__).resolve().parents[1] / "fixtures" / "fake_pi.py"

REQUEST = TranslationRequest(text="Comment ça va ?", target_language="es", source_language="fr")


def make_adapter(monkeypatch: pytest.MonkeyPatch, mode: str, *, timeout: float = 30.0):
    monkeypatch.setenv("FAKE_PI_MODE", mode)
    return PiCliAdapter(command=[sys.executable, str(FAKE_PI)], timeout_seconds=timeout)


def run(adapter: PiCliAdapter, request: TranslationRequest = REQUEST) -> str:
    return asyncio.run(adapter.translate(request))


def test_translate_returns_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(make_adapter(monkeypatch, "translate")) == "¿Cómo estás?"


def test_translate_unwraps_surrounding_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Models like to answer with the sentence in quotes even when asked not to.
    assert run(make_adapter(monkeypatch, "translate-quoted")) == "¿Cómo estás?"


def test_translate_rejects_an_empty_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(LlmUnavailable):
        run(make_adapter(monkeypatch, "translate-empty"))


def test_translate_reports_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(LlmTimeout):
        run(make_adapter(monkeypatch, "slow", timeout=0.4))


def test_the_prompt_carries_the_direction_and_the_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_PI_SYSTEM_FILE", str(tmp_path / "system.md"))
    monkeypatch.setenv("FAKE_PI_PROMPT_FILE", str(tmp_path / "prompt.txt"))

    run(make_adapter(monkeypatch, "translate"), REQUEST)

    system = (tmp_path / "system.md").read_text(encoding="utf-8")
    turn = (tmp_path / "prompt.txt").read_text(encoding="utf-8")
    assert "fr" in system and "es" in system
    assert "Comment ça va ?" in turn


def test_the_translation_never_sees_tools_or_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_PI_ARGV_FILE", str(tmp_path / "argv.txt"))

    run(make_adapter(monkeypatch, "translate"))

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "--no-tools" in argv and "--no-session" in argv
    assert os.getcwd() not in (tmp_path / "argv.txt").read_text(encoding="utf-8")
