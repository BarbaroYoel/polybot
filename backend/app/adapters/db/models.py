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
