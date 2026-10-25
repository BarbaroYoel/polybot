"""The translation prompt (S5, ADR-014).

The prompt is an artifact of the repository, not a string inside the adapter: its version is
asserted here so a change in translation behavior shows up in the diff.
"""

import pytest

from app.adapters.llm.prompt import PROMPT_VERSION_TRANSLATION, TranslationPrompt
from app.ports.llm import TranslationRequest


def make_request(source: str | None = "fr") -> TranslationRequest:
    return TranslationRequest(
        text="Comment ça va ?",
        target_language="es",
        source_language=source,
    )


def test_the_version_is_declared() -> None:
    assert PROMPT_VERSION_TRANSLATION == "translate.v1"


def test_the_system_prompt_names_both_languages() -> None:
    system = TranslationPrompt.load().render_system(make_request())

    assert "fr" in system
    assert "es" in system


def test_the_turn_carries_the_text_to_translate() -> None:
    turn = TranslationPrompt.load().render_turn(make_request())

    assert "Comment ça va ?" in turn


def test_a_missing_source_asks_the_model_to_detect_it() -> None:
    system = TranslationPrompt.load().render_system(make_request(source=None))

    assert "detect" in system.lower()


def test_a_version_of_another_prompt_family_is_rejected() -> None:
    with pytest.raises(ValueError):
        TranslationPrompt.load("feedback.v1")
