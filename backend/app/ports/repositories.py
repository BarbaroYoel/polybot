"""Repository ports. `application/` depends on these, never on the SQLAlchemy adapters."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.domain.entities import (
    CefrLevel,
    Conversation,
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
