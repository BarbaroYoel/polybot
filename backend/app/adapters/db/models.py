"""Table mappings.

Only portable types are used so the schema can move from SQLite to PostgreSQL later without a
rewrite (odd/tasks/f2-backend-skeleton.md, Assumptions): no `JSONB`, no native `ENUM`, no `ARRAY`,
and ids are stored as UUID v4 strings.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class LanguageRow(Base):
    __tablename__ = "languages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    explanation_language: Mapped[str] = mapped_column(String(8), nullable=False, default="es")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weekly_goal_conversations: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    weekly_goal_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # Denormalized so the history page can order and paginate without aggregating messages.
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_conversations_language_activity", "language_id", "last_message_at", "created_at"),
    )


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    author: Mapped[str] = mapped_column(String(8), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="sent")
    # Client-supplied retry key: the same key in a conversation resolves to the same turn (F3).
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_idempotency_key", "conversation_id", "idempotency_key", unique=True),
    )


class MessageFeedbackRow(Base):
    """The closing turn of one user message (F3 S7): 1:1 with the message it reviews.

    A message with nothing to report has no row, so the API answers `feedback: null` instead of an
    empty shell. Tables instead of a JSON column keep the vocabulary queryable per language.
    """

    __tablename__ = "message_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MessageCorrectionRow(Base):
    """One correction of a closing turn, ordered by `position`."""

    __tablename__ = "message_corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    feedback_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_feedback.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    original: Mapped[str] = mapped_column(Text, nullable=False)
    corrected: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_message_corrections_feedback_position", "feedback_id", "position", unique=True),
    )


class VocabularyItemRow(Base):
    """One suggested term, scoped by the conversation's language (F3 S7, S8)."""

    __tablename__ = "vocabulary_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Never the globally active language: the turn follows the conversation (AGENTS.md §3).
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), nullable=False
    )
    feedback_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_feedback.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    term: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_vocabulary_items_feedback_position", "feedback_id", "position", unique=True),
        Index("ix_vocabulary_items_language", "language_id"),
    )


class LessonUnitRow(Base):
    """A catalog unit of one language (desing.md §6.2): vocabulary, grammar, and so on."""

    __tablename__ = "lesson_units"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("ix_lesson_units_language_position", "language_id", "position"),)


class LessonRow(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    unit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lesson_units.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized so every catalog query filters by language in one predicate (F5 S6).
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(2), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    intro: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_lessons_language", "language_id"),
        Index("ix_lessons_unit_position", "unit_id", "position"),
    )


class LessonExerciseRow(Base):
    __tablename__ = "lesson_exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (Index("ix_lesson_exercises_lesson_position", "lesson_id", "position"),)


class LessonExerciseAnswerRow(Base):
    """The answers one exercise accepts, in order: the first one is the expected answer (F5 S8).

    A table instead of a JSON column keeps the schema portable and grading a plain query.
    """

    __tablename__ = "lesson_exercise_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exercise_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lesson_exercises.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_lesson_exercise_answers_exercise_position", "exercise_id", "position"),
    )


class LessonVocabularyRow(Base):
    """A key term of one lesson: what the result shows as its new vocabulary (F5 S2)."""

    __tablename__ = "lesson_vocabulary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    term: Mapped[str] = mapped_column(String(120), nullable=False)
    translation: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_lesson_vocabulary_lesson_position", "lesson_id", "position"),)


class LessonAttemptRow(Base):
    """A finished practice: the lesson result, stored per language for F6 (F5 S2, S7)."""

    __tablename__ = "lesson_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), nullable=False
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("ix_lesson_attempts_language_lesson", "language_id", "lesson_id"),)


class LessonAttemptAnswerRow(Base):
    """One answer of one attempt: what the student wrote and whether it was accepted."""

    __tablename__ = "lesson_attempt_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lesson_attempts.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lesson_exercises.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (Index("ix_lesson_attempt_answers_attempt", "attempt_id"),)


class StudyPlanRow(Base):
    """The plan the user asked for one language (F5 S3). One plan per language, never two."""

    __tablename__ = "study_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Unique as well: the service answers 409 `plan_already_exists` before the database sees a
    # second plan, and the constraint keeps that true even if two requests race.
    language_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("languages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Fixed at creation: the goal is what the user asked for (F5 S4).
    goal: Mapped[str] = mapped_column(String(200), nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Null until the user adjusts the plan: nothing recalculates it by itself (S4).
    adjusted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PlanSessionRow(Base):
    """One lesson placed in a week of the schedule. Its state is derived, never stored (F5 S5)."""

    __tablename__ = "plan_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("ix_plan_sessions_plan_week_position", "plan_id", "week", "position"),)
