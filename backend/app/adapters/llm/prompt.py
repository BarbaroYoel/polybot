"""Tutor prompts, versioned in the repository (F3 S3, S7, ADR-020).

Three prompt artifacts live here:

- `tutor.v1.md` + `turn.v1.txt`: the system prompt with the tutor rules and the turn template that
  frames the history and the new message.
- `feedback.v2.md`: the closing-turn prompt. It carries both halves in one versioned file (the
  system rules and the turn template after a marker) so the closing behavior changes in one diff.
  `feedback.v1.md` stays in the tree as the version that closed a turn without practice blocks.
- `translate.v1.md` and `lesson-review.v1.md`: the two short, single-purpose prompts.

`PROMPT_VERSION` and `PROMPT_VERSION_FEEDBACK` are asserted by the tests so a change in behavior is
visible in the diff.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from string import Template

from app.ports.llm import (
    LessonReviewRequest,
    TranslationRequest,
    TurnMessage,
    TutorContext,
    TutorTurn,
)

PROMPT_VERSION = "tutor.v1"
PROMPT_VERSION_FEEDBACK = "feedback.v2"
PROMPT_VERSION_TRANSLATION = "translate.v1"
PROMPT_VERSION_LESSON_REVIEW = "lesson-review.v1"

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_NO_HISTORY = "(todavía no hay mensajes)"
# Splits `feedback.vN.md` into the system prompt and the turn template.
_TURN_MARKER = "<!-- turn -->"


def _render_history(history: Sequence[TurnMessage]) -> str:
    return (
        "\n".join(
            f"{'Estudiante' if message.author.value == 'user' else 'Tutor'}: {message.content}"
            for message in history
        )
        or _NO_HISTORY
    )


@dataclass(frozen=True, slots=True)
class TutorPrompt:
    """The versioned tutor prompt files, ready to render for one turn."""

    system: str
    turn: str

    @classmethod
    def load(cls, version: str = PROMPT_VERSION) -> "TutorPrompt":
        if not version.startswith("tutor."):
            raise ValueError(f"unexpected prompt version: {version}")
        suffix = version.removeprefix("tutor.")
        return cls(
            system=(_PROMPTS_DIR / f"tutor.{suffix}.md").read_text(encoding="utf-8"),
            turn=(_PROMPTS_DIR / f"turn.{suffix}.txt").read_text(encoding="utf-8"),
        )

    def render_system(self, context: TutorContext) -> str:
        return Template(self.system).substitute(
            language_name=context.language_name,
            language_code=context.language_code,
            level=context.level.value,
            explanation_language=context.explanation_language,
        )

    def render_turn(self, turn: TutorTurn) -> str:
        return Template(self.turn).substitute(
            history=_render_history(turn.history),
            user_message=turn.user_message,
        )


@dataclass(frozen=True, slots=True)
class FeedbackPrompt:
    """The closing-turn prompt: the same context, plus the reply the tutor already sent (S7)."""

    system: str
    turn: str

    @classmethod
    def load(cls, version: str = PROMPT_VERSION_FEEDBACK) -> "FeedbackPrompt":
        if not version.startswith("feedback."):
            raise ValueError(f"unexpected prompt version: {version}")
        suffix = version.removeprefix("feedback.")
        text = (_PROMPTS_DIR / f"feedback.{suffix}.md").read_text(encoding="utf-8")
        system, _, turn = text.partition(_TURN_MARKER)
        if not turn.strip():
            raise ValueError(f"{version} has no turn template after {_TURN_MARKER}")
        return cls(system=f"{system.strip()}\n", turn=f"{turn.strip()}\n")

    def render_system(self, context: TutorContext) -> str:
        return Template(self.system).substitute(
            language_name=context.language_name,
            language_code=context.language_code,
            level=context.level.value,
            explanation_language=context.explanation_language,
        )

    def render_turn(self, turn: TutorTurn, reply: str) -> str:
        return Template(self.turn).substitute(
            history=_render_history(turn.history),
            user_message=turn.user_message,
            tutor_reply=reply,
        )


@dataclass(frozen=True, slots=True)
class TranslationPrompt:
    """The translation prompt: the direction in the system side, the text in the turn (ADR-014)."""

    system: str
    turn: str

    @classmethod
    def load(cls, version: str = PROMPT_VERSION_TRANSLATION) -> "TranslationPrompt":
        if not version.startswith("translate."):
            raise ValueError(f"unexpected prompt version: {version}")
        suffix = version.removeprefix("translate.")
        text = (_PROMPTS_DIR / f"translate.{suffix}.md").read_text(encoding="utf-8")
        system, _, turn = text.partition(_TURN_MARKER)
        if not turn.strip():
            raise ValueError(f"{version} has no turn template after {_TURN_MARKER}")
        return cls(system=f"{system.strip()}\n", turn=f"{turn.strip()}\n")

    def render_system(self, request: TranslationRequest) -> str:
        return Template(self.system).substitute(
            source_language=_render_source(request.source_language),
            target_language=request.target_language,
        )

    def render_turn(self, request: TranslationRequest) -> str:
        return Template(self.turn).substitute(text=request.text)


@dataclass(frozen=True, slots=True)
class LessonReviewPrompt:
    """The lesson-review prompt: the lesson result in the turn, the context in the system side."""

    system: str
    turn: str

    @classmethod
    def load(cls, version: str = PROMPT_VERSION_LESSON_REVIEW) -> "LessonReviewPrompt":
        if not version.startswith("lesson-review."):
            raise ValueError(f"unexpected prompt version: {version}")
        suffix = version.removeprefix("lesson-review.")
        text = (_PROMPTS_DIR / f"lesson-review.{suffix}.md").read_text(encoding="utf-8")
        system, _, turn = text.partition(_TURN_MARKER)
        if not turn.strip():
            raise ValueError(f"{version} has no turn template after {_TURN_MARKER}")
        return cls(system=f"{system.strip()}\n", turn=f"{turn.strip()}\n")

    def render_system(self, context: TutorContext) -> str:
        return Template(self.system).substitute(
            language_name=context.language_name,
            language_code=context.language_code,
            level=context.level.value,
            explanation_language=context.explanation_language,
        )

    def render_turn(self, request: LessonReviewRequest) -> str:
        return Template(self.turn).substitute(
            lesson_title=request.lesson_title,
            correct=request.correct,
            total=request.total,
            items=_render_review_items(request),
        )


def _render_review_items(request: LessonReviewRequest) -> str:
    """One line per exercise: what was asked, what the student wrote and whether it was right."""
    lines = []
    for item in request.items:
        verdict = "correcta" if item.correct else f"incorrecta, se esperaba «{item.expected}»"
        lines.append(f"- {item.prompt} → «{item.answer}»: {verdict}")
    return "\n".join(lines)


def _render_source(source_language: str | None) -> str:
    """A missing source is the model's job to detect; it is never invented by the caller."""
    return source_language or "no indicado: detectá del texto"
