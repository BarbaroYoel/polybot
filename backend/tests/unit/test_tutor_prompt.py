"""The versioned tutor prompt (F3 S3).

The prompt is a product artifact: it carries the language, the level and the explanation language,
and it is versioned in the repository (docs/roadmap.md §F3). These tests pin the contract the
adapter relies on, not the exact wording.
"""

from app.adapters.llm.prompt import PROMPT_VERSION, TutorPrompt
from app.domain.entities import CefrLevel, MessageAuthor
from app.ports.llm import TurnMessage, TutorContext, TutorTurn


def make_turn() -> TutorTurn:
    return TutorTurn(
        context=TutorContext(
            language_name="Alemán",
            language_code="de",
            level=CefrLevel.B2,
            explanation_language="es",
        ),
        history=[TurnMessage(author=MessageAuthor.USER, content="Hallo!")],
        user_message="Ich möchte einen Kaffee.",
    )


def test_prompt_version_is_explicit() -> None:
    assert PROMPT_VERSION == "tutor.v1"
    assert "tutor.v1" in TutorPrompt.load().system


def test_system_prompt_carries_language_level_and_explanation_language() -> None:
    system = TutorPrompt.load().render_system(make_turn().context)

    assert "Alemán" in system
    assert "B2" in system
    assert "es" in system


def test_system_prompt_keeps_the_tutor_role_and_the_target_language_rule() -> None:
    system = TutorPrompt.load().render_system(make_turn().context)

    assert "tutor" in system.lower()
    assert "Alemán" in system


def test_turn_prompt_renders_the_history_oldest_first_and_the_new_message_last() -> None:
    prompt = TutorPrompt.load().render_turn(make_turn())

    assert "Hallo!" in prompt
    assert "Ich möchte einen Kaffee." in prompt
    assert prompt.index("Hallo!") < prompt.index("Ich möchte einen Kaffee.")
