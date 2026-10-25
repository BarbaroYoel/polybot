"""The LLM port (F3 S1-S2).

`application/` depends on this protocol; the harness that runs the model is an adapter detail
(ADR-004). Pi is one adapter, not a dependency of the domain or the use cases.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities import CefrLevel, MessageAuthor


@dataclass(frozen=True, slots=True)
class TutorContext:
    """What the tutor needs to know about the language being practised (desing.md §6.6)."""

    language_name: str
    language_code: str
    level: CefrLevel
    explanation_language: str


@dataclass(frozen=True, slots=True)
class TurnMessage:
    """One previous message of the conversation, oldest first."""

    author: MessageAuthor
    content: str


@dataclass(frozen=True, slots=True)
class TutorTurn:
    """One turn: the conversation so far plus the message the user just sent."""

    context: TutorContext
    history: Sequence[TurnMessage]
    user_message: str


@dataclass(frozen=True, slots=True)
class CorrectionDraft:
    """One correction of the user message, as the provider proposed it (F3 S7).

    A draft, not a stored row: the adapter validates it (non-empty, trimmed, within the limits)
    before `application/` persists it.
    """

    original: str
    corrected: str
    explanation: str


@dataclass(frozen=True, slots=True)
class VocabularyDraft:
    """One suggested term of the practised language, with its translation in the explanation one."""

    term: str
    translation: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class TurnFeedback:
    """What the closing call of a turn produced (F3 S7)."""

    corrections: Sequence[CorrectionDraft] = ()
    vocabulary: Sequence[VocabularyDraft] = ()

    @property
    def is_empty(self) -> bool:
        """A turn with nothing to report: no rows to store and no events to emit."""
        return not (self.corrections or self.vocabulary)


EMPTY_FEEDBACK = TurnFeedback()


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """One text to translate, with the direction the caller already decided (ADR-014).

    `source_language` is the language code of the original or `None` when the caller does not know
    it and the provider must detect it. `target_language` is never guessed by the adapter: the
    language of the explanation comes from the caller's profile, not from the provider.
    """

    text: str
    target_language: str
    source_language: str | None = None


@dataclass(frozen=True, slots=True)
class LessonReviewItem:
    """One graded exercise, as the tutor needs it to comment on the result (F5 S2)."""

    prompt: str
    answer: str
    expected: str
    correct: bool


@dataclass(frozen=True, slots=True)
class LessonReviewRequest:
    """A finished lesson and its graded answers, oldest first."""

    context: TutorContext
    lesson_title: str
    items: Sequence[LessonReviewItem]

    @property
    def correct(self) -> int:
        return sum(1 for item in self.items if item.correct)

    @property
    def total(self) -> int:
        return len(self.items)


class LlmPort(Protocol):
    def stream_reply(self, turn: TutorTurn) -> AsyncIterator[str]:
        """Yield the tutor reply as text deltas, in order.

        Closing the iterator early asks the adapter to cancel the provider call and release every
        resource it holds (docs/architecture.md §5: cancellation).
        """

    async def summarize_turn(self, turn: TutorTurn, reply: str) -> TurnFeedback:
        """Close a turn that was already answered: corrections and suggested vocabulary (S7).

        A separate invocation of the same provider, so the text the user already read is not
        delayed by the closing step. An unusable answer is an `LlmUnavailable`: the caller keeps
        the reply and skips the feedback (the chat is never broken by this step).
        """

    async def review_lesson(self, request: LessonReviewRequest) -> str:
        """Comment on a finished lesson, in the explanation language (S8, best-effort).

        One short invocation of the same provider. The grading already happened without the model,
        so an unusable answer is an `LlmUnavailable`: the caller keeps the result and stores the
        attempt with no comment instead of failing the lesson.
        """

    async def translate(self, request: TranslationRequest) -> str:
        """Translate one text into `target_language` and return only the translation (ADR-014).

        A short invocation of the same provider: an empty or unusable answer is an
        `LlmUnavailable`, so a translation is never stored as an empty string.
        """
