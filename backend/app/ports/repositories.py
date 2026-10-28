"""Repository ports. `application/` depends on these, never on the SQLAlchemy adapters."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.domain.blocks import TurnBlock
from app.domain.entities import (
    ActivityCount,
    CefrLevel,
    Conversation,
    FrequentError,
    HistoryEntry,
    LanguageProfile,
    Lesson,
    LessonAnswer,
    LessonAttempt,
    LessonExercise,
    LessonStatus,
    LessonTerm,
    LessonUnit,
    Message,
    MessageStatus,
    NewConversation,
    NewLanguage,
    NewMessage,
    NewPlanSession,
    NewStudyPlan,
    PlanSession,
    StudyPlan,
    WeeklyGoal,
)
from app.domain.feedback import MessageFeedback
from app.ports.llm import TurnFeedback


class LanguageRepository(Protocol):
    async def list_languages(self) -> list[LanguageProfile]:
        """Every non-archived language, oldest first."""

    async def get_language(self, language_id: str) -> LanguageProfile | None: ...

    async def get_language_by_code(self, code: str) -> LanguageProfile | None: ...

    async def add_language(self, draft: NewLanguage) -> LanguageProfile: ...

    async def update_language(
        self,
        language_id: str,
        *,
        level: CefrLevel | None = None,
        weekly_goal: WeeklyGoal | None = None,
        is_active: bool | None = None,
    ) -> LanguageProfile:
        """Updates the given fields; activating one language deactivates the others."""

    async def archive_language(self, language_id: str) -> None: ...


class ConversationRepository(Protocol):
    async def list_conversations(
        self,
        language_id: str,
        *,
        limit: int,
        after: tuple[datetime, str] | None = None,
    ) -> list[Conversation]:
        """Conversations of one language only, most recent activity first."""

    async def get_conversation(self, conversation_id: str) -> Conversation | None: ...

    async def add_conversation(self, draft: NewConversation) -> Conversation: ...

    async def rename_conversation(self, conversation_id: str, title: str) -> Conversation: ...

    async def record_message_activity(self, conversation_id: str, at: datetime) -> None:
        """Bump the message count and the last activity after a message is stored."""

    async def delete_conversation(self, conversation_id: str) -> None: ...


class MessageRepository(Protocol):
    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        after: tuple[datetime, str] | None = None,
    ) -> list[Message]:
        """Messages of one conversation, oldest first."""

    async def add_message(self, draft: NewMessage) -> Message: ...

    async def get_message(self, message_id: str) -> Message | None:
        """One message by id, or `None` when it does not exist."""

    async def update_message(
        self, message_id: str, *, content: str, status: MessageStatus
    ) -> Message:
        """Rewrite a streamed message once the turn closes; returns the stored row."""

    async def set_translation(self, message_id: str, translation: str) -> Message:
        """Store the translation of one message; asking twice never calls the provider twice."""

    async def save_blocks(self, message_id: str, blocks: Sequence[TurnBlock]) -> Message:
        """Attach the practice blocks to one message, replacing the previous ones (ADR-020)."""

    async def list_messages_before(
        self, conversation_id: str, before: Message, *, limit: int
    ) -> list[Message]:
        """The messages older than `before`, oldest first, at most `limit` of them."""

    async def find_message_by_key(self, conversation_id: str, key: str) -> Message | None:
        """The turn already stored for that retry key, if any (idempotent sends)."""

    async def save_feedback(
        self, message_id: str, language_id: str, feedback: TurnFeedback
    ) -> MessageFeedback:
        """Store the closing turn of one user message; a retried turn replaces it (F3 S7).

        `language_id` is the conversation's language and is stored with every vocabulary item, so
        the terms are readable per language later (S8).
        """

    async def feedback_for_messages(self, message_ids: Sequence[str]) -> dict[str, MessageFeedback]:
        """Feedback of the given messages, keyed by message id, in one query (no N+1)."""


class LessonRepository(Protocol):
    """Lessons, their units and their exercises, always filtered by language (F5 S6)."""

    async def list_units(self, language_id: str) -> list[LessonUnit]:
        """Units of one language, in catalog order."""

    async def list_lessons(self, language_id: str) -> list[Lesson]:
        """Lessons of one language, in catalog order: unit position, then lesson position."""

    async def get_lesson(self, lesson_id: str) -> Lesson | None: ...

    async def get_unit(self, unit_id: str) -> LessonUnit | None: ...

    async def list_exercises(self, lesson_id: str) -> list[LessonExercise]:
        """Exercises of one lesson, in order, each with every answer it accepts."""

    async def lesson_statuses(self, language_id: str) -> dict[str, LessonStatus]:
        """Status of every lesson of one language, derived from the stored attempts (S5)."""

    async def list_terms(self, lesson_id: str) -> list[LessonTerm]:
        """The key terms of one lesson, in order: the «vocabulario nuevo» of its result (S2)."""


class LessonAttemptRepository(Protocol):
    async def add_attempt(
        self,
        *,
        lesson_id: str,
        language_id: str,
        answers: Sequence[LessonAnswer],
        feedback: str | None,
    ) -> LessonAttempt:
        """Store one finished practice with its answers, so F6 can read them later (S7)."""


class StudyPlanRepository(Protocol):
    """The plan of one language and the schedule that spreads its catalog (F5 S3, S4, S6)."""

    async def get_plan(self, language_id: str) -> StudyPlan | None:
        """The plan of one language, or `None` when that language has none yet."""

    async def get_plan_by_id(self, plan_id: str) -> StudyPlan | None: ...

    async def add_plan(self, draft: NewStudyPlan, schedule: Sequence[NewPlanSession]) -> StudyPlan:
        """Store the plan and the schedule generated from the catalog, in one transaction."""

    async def adjust_plan(
        self,
        plan_id: str,
        *,
        frequency: int,
        daily_minutes: int,
        schedule: Sequence[NewPlanSession],
    ) -> StudyPlan:
        """Store the new frequency and time and rewrite the whole schedule (F5 S4).

        The previous sessions are deleted and the new ones written in the same transaction, so a
        reader never sees a plan with half a schedule. The goal is never touched: it is what the
        user asked for when the plan was created.
        """

    async def list_sessions(self, plan_id: str) -> list[PlanSession]:
        """The sessions of one plan, in schedule order: week, then position."""


class ProgressRepository(Protocol):
    """Read-only aggregates over the signals F6 already stores (ADR-018: no new schema).

    Every method filters by `language_id`: progress never mixes languages (AGENTS.md §3). Dates are
    naive UTC, the codebase convention (`app/core/dates.py`), and `since` is already the UTC instant
    of the caller's local Monday 00:00.
    """

    async def conversation_activity(self, language_id: str) -> ActivityCount:
        """Conversations with at least one message, and the newest message of the language.

        An empty conversation is not a practice and does not count (F6 S1).
        """

    async def weekly_conversation_count(self, language_id: str, *, since: datetime) -> int:
        """Distinct conversations with at least one message at or after `since` (F6 S1)."""

    async def writing_activity(self, language_id: str) -> ActivityCount:
        """Exercise answers sent in attempts of this language, and the newest attempt (F6 S2)."""

    async def vocabulary_activity(self, language_id: str) -> ActivityCount:
        """Suggested terms stored for this language, and the newest one (F6 S2)."""

    async def frequent_errors(self, language_id: str, *, limit: int) -> list[FrequentError]:
        """Mistakes grouped by their exact pair, already ordered and capped at `limit` (F6 S3).

        Corrections and lesson answers are merged by the adapter: both kinds compete for the same
        top positions, ordered by count and then by their newest occurrence.
        """

    async def history(self, language_id: str, *, limit: int) -> list[HistoryEntry]:
        """Lesson attempts and non-empty conversations, mixed, newest first (F6 S4)."""
