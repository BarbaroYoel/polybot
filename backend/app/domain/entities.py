"""Pure domain entities (docs/architecture.md §3: `domain/` imports no infrastructure)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CefrLevel(StrEnum):
    """Language level shown as a badge, never as a selector (ADR-008)."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ConversationMode(StrEnum):
    """Conversation modes of desing.md §7."""

    FREE = "free"
    GUIDED = "guided"
    ROLEPLAY = "roleplay"
    EXERCISE = "exercise"
    LIVE_VOICE = "live_voice"


class MessageAuthor(StrEnum):
    TUTOR = "tutor"
    USER = "user"


class MessageStatus(StrEnum):
    SENT = "sent"
    STREAMING = "streaming"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WeeklyGoal:
    conversations: int = 7
    minutes: int = 90


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    id: str
    code: str
    name: str
    level: CefrLevel
    explanation_language: str
    is_active: bool
    archived: bool
    weekly_goal: WeeklyGoal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Conversation:
    id: str
    language_id: str
    mode: ConversationMode
    title: str
    message_count: int
    last_message_at: datetime | None
    created_at: datetime

    @property
    def activity_at(self) -> datetime:
        """What the history is ordered by: the last message, or the creation when there is none."""
        return self.last_message_at or self.created_at


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    conversation_id: str
    author: MessageAuthor
    content: str
    translation: str | None
    status: MessageStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewLanguage:
    code: str
    name: str
    level: CefrLevel
    explanation_language: str = "es"
    weekly_goal: WeeklyGoal = WeeklyGoal()


@dataclass(frozen=True, slots=True)
class NewConversation:
    language_id: str
    mode: ConversationMode
    title: str
