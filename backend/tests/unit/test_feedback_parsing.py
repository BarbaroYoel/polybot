"""The closing turn: JSON extraction, validation and the second Pi invocation (F3 S7).

The closing call is a second Pi invocation whose answer must be JSON, and a language model does
not always obey (docs/api-contract.md §3). The parser is therefore tolerant about the envelope
(plain JSON, ```json fences, prose around it) and strict about the content: the items the client
renders need non-empty strings, an incomplete item is dropped instead of breaking the turn, the
limits of five corrections and eight terms are enforced, and an answer with no usable structure
is an `llm_unavailable` so the chat closes without feedback.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from app.adapters.llm.pi import PiCliAdapter, parse_turn_feedback
from app.adapters.llm.prompt import PROMPT_VERSION_FEEDBACK, FeedbackPrompt
from app.domain.entities import CefrLevel, MessageAuthor
from app.domain.errors import LlmUnavailable
from app.ports.llm import TurnMessage, TutorContext, TutorTurn

FAKE_PI = Path(__file__).resolve().parents[1] / "fixtures" / "fake_pi.py"

CORRECTIONS = [
    {
        "original": "je suis allé au café hier",
        "corrected": "Je suis allé au café hier.",
        "explanation": "Falta el punto final.",
    }
]
VOCABULARY = [{"term": "un café", "translation": "un café", "note": "masculino"}]


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


def payload(corrections: Any = None, vocabulary: Any = None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if corrections is not None:
        data["corrections"] = corrections
    if vocabulary is not None:
        data["vocabulary"] = vocabulary
    return data


def parse(corrections: Any = None, vocabulary: Any = None):
    return parse_turn_feedback(json.dumps(payload(corrections, vocabulary), ensure_ascii=False))


# --- the envelope ---------------------------------------------------------------------------


def test_a_plain_json_object_is_parsed() -> None:
    feedback = parse(CORRECTIONS, VOCABULARY)

    assert [(item.original, item.corrected, item.explanation) for item in feedback.corrections] == [
        ("je suis allé au café hier", "Je suis allé au café hier.", "Falta el punto final.")
    ]
    assert [(item.term, item.translation, item.note) for item in feedback.vocabulary] == [
        ("un café", "un café", "masculino")
    ]


def test_a_fenced_json_block_is_parsed() -> None:
    answer = f"```json\n{json.dumps(payload(CORRECTIONS, VOCABULARY), ensure_ascii=False)}\n```"

    feedback = parse_turn_feedback(answer)

    assert len(feedback.corrections) == 1
    assert feedback.vocabulary[0].term == "un café"


def test_prose_around_the_json_is_ignored() -> None:
    body = json.dumps(payload(CORRECTIONS, VOCABULARY), ensure_ascii=False)
    answer = f"Claro, acá va el cierre del turno:\n\n{body}\n\n¡Buen trabajo!"

    feedback = parse_turn_feedback(answer)

    assert len(feedback.corrections) == 1
    assert len(feedback.vocabulary) == 1


def test_the_first_json_object_wins() -> None:
    first = json.dumps(payload(CORRECTIONS, VOCABULARY), ensure_ascii=False)
    second = json.dumps(payload([], [{"term": "otro", "translation": "other", "note": None}]))
    answer = f"{first}\n{second}"

    feedback = parse_turn_feedback(answer)

    assert [item.term for item in feedback.vocabulary] == ["un café"]


def test_an_empty_but_valid_answer_is_feedback_with_no_items() -> None:
    feedback = parse([], [])

    assert feedback.corrections == ()
    assert feedback.vocabulary == ()


# --- the content ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "",
        "No pude revisar tu mensaje, probá de nuevo.",
        '{"corrections": [',
        "[1, 2, 3]",
        '{"ok": true}',
        '{"corrections": "ninguna"}',
        '{"corrections": [], "vocabulary": {"term": "un café"}}',
    ],
)
def test_an_answer_that_cannot_be_validated_is_a_provider_failure(answer: str) -> None:
    with pytest.raises(LlmUnavailable):
        parse_turn_feedback(answer)


def test_incomplete_items_are_dropped_instead_of_breaking_the_turn() -> None:
    feedback = parse(
        [
            CORRECTIONS[0],
            {"original": "solo original", "explanation": "sin corrección"},
            {"original": "  ", "corrected": "algo", "explanation": "original vacío"},
            {"original": "a", "corrected": "b", "explanation": "  "},
            {"original": 7, "corrected": "b", "explanation": "tipo equivocado"},
            "texto suelto",
        ],
        [
            VOCABULARY[0],
            {"term": "sin traducción", "note": "falta translation"},
            {"term": "", "translation": "vacío"},
            {"term": "sin nota", "translation": "sin nota"},
        ],
    )

    assert [item.original for item in feedback.corrections] == ["je suis allé au café hier"]
    # `note` is optional: only the fields the card needs are required.
    assert [(item.term, item.translation, item.note) for item in feedback.vocabulary] == [
        ("un café", "un café", "masculino"),
        ("sin nota", "sin nota", None),
    ]


def test_the_limits_are_five_corrections_and_eight_terms() -> None:
    corrections = [
        {"original": f"frase {index}", "corrected": f"frase {index}.", "explanation": "puntuación"}
        for index in range(9)
    ]
    vocabulary = [
        {"term": f"término {index}", "translation": f"term {index}", "note": None}
        for index in range(12)
    ]

    feedback = parse(corrections, vocabulary)

    assert [item.original for item in feedback.corrections] == [
        f"frase {index}" for index in range(5)
    ]
    assert [item.term for item in feedback.vocabulary] == [f"término {index}" for index in range(8)]


def test_the_strings_are_trimmed_and_a_blank_note_means_no_note() -> None:
    feedback = parse(
        [
            {
                "original": "  je suis allé  ",
                "corrected": "\tJe suis allé.  ",
                "explanation": "  Falta el punto final.\n",
            }
        ],
        [
            {"term": "  un café ", "translation": " un café\n", "note": "   "},
            {"term": "s'il vous plaît", "translation": "por favor", "note": 42},
        ],
    )

    correction = feedback.corrections[0]
    assert (correction.original, correction.corrected, correction.explanation) == (
        "je suis allé",
        "Je suis allé.",
        "Falta el punto final.",
    )
    assert feedback.vocabulary[0].note is None
    assert feedback.vocabulary[1].note is None


# --- the closing prompt ---------------------------------------------------------------------


def test_the_closing_prompt_is_versioned_and_asks_for_strict_json() -> None:
    prompt = FeedbackPrompt.load()
    system = prompt.render_system(make_turn().context)

    assert PROMPT_VERSION_FEEDBACK == "feedback.v1"
    assert "feedback.v1" in prompt.system
    assert "JSON" in system
    # The prompt must forbid invented errors: the cards are educational, not decorative.
    assert "No inventes errores" in system or "no inventes errores" in system
    assert "Francés" in system and "A1" in system and "es" in system


def test_the_closing_prompt_carries_the_message_the_reply_and_the_history() -> None:
    prompt = FeedbackPrompt.load().render_turn(make_turn(), "Bonjour Ana !")

    assert make_turn().user_message in prompt
    assert "Bonjour Ana !" in prompt
    assert "Bonjour, je m'appelle Ana." in prompt
    # The subject is the message and the reply; the history travels after them, as context only.
    assert prompt.index(make_turn().user_message) < prompt.index("Bonjour Ana !")
    assert prompt.index("Bonjour Ana !") < prompt.index("Bonjour, je m'appelle Ana.")


# --- the adapter's second invocation --------------------------------------------------------


def make_adapter(monkeypatch: pytest.MonkeyPatch, mode: str) -> PiCliAdapter:
    monkeypatch.setenv("FAKE_PI_MODE", mode)
    return PiCliAdapter(command=[sys.executable, str(FAKE_PI)], timeout_seconds=30.0)


def summarize(adapter: PiCliAdapter) -> Any:
    async def run() -> Any:
        return await adapter.summarize_turn(make_turn(), "Bonjour Ana !")

    return asyncio.run(run())


def test_summarize_turn_parses_the_json_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    feedback = summarize(make_adapter(monkeypatch, "feedback-json"))

    assert [(item.original, item.corrected) for item in feedback.corrections] == [
        ("Je suis allé au café hier", "Je suis allé au café hier."),
        ("j'ai prends un café", "je prends un café"),
    ]
    assert [(item.term, item.note) for item in feedback.vocabulary] == [
        ("un café", "masculino"),
        ("s'il vous plaît", None),
    ]


def test_summarize_turn_reports_a_broken_answer_as_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(LlmUnavailable):
        summarize(make_adapter(monkeypatch, "feedback-broken"))


def test_the_closing_call_receives_the_reply_and_the_language_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    system_file = tmp_path / "system.txt"
    monkeypatch.setenv("FAKE_PI_PROMPT_FILE", str(prompt_file))
    monkeypatch.setenv("FAKE_PI_SYSTEM_FILE", str(system_file))

    summarize(make_adapter(monkeypatch, "feedback-json"))
    sent = prompt_file.read_text(encoding="utf-8")
    system = system_file.read_text(encoding="utf-8")

    # The second invocation reads the tutor reply it must judge, the user message and the context.
    assert "Bonjour Ana !" in sent
    assert "Je voudrais un café, s'il vous plaît." in sent
    # "Francés" in system and "A1" in system and "es" in system
    assert "Francés" in system and "A1" in system and "es" in system
    # The output rules live in the system prompt, not in the turn text.
    assert "JSON" in system
    assert "No inventes errores" in system
    assert "No inventes errores" not in sent


def test_the_closing_call_keeps_the_tutor_isolated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    argv_file = tmp_path / "argv.txt"
    monkeypatch.setenv("FAKE_PI_ARGV_FILE", str(argv_file))

    summarize(make_adapter(monkeypatch, "feedback-json"))
    argv = argv_file.read_text(encoding="utf-8").splitlines()

    for flag in (
        "--print",
        "--mode",
        "json",
        "--no-session",
        "--no-tools",
        "--no-builtin-tools",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-mcp",
        "--system-prompt",
    ):
        assert flag in argv
