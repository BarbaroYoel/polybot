"""Request and response models. They mirror docs/api-contract.md §2 field by field."""

from pydantic import BaseModel, Field

from app.application.pagination import Page
from app.core.dates import to_iso
from app.domain.entities import (
    CefrLevel,
    Conversation,
    ConversationMode,
    LanguageProfile,
    Message,
    MessageAuthor,
    MessageStatus,
)


class WeeklyGoal(BaseModel):
    conversations: int = Field(default=7, ge=1, le=100)
    minutes: int = Field(default=90, ge=0, le=10_000)


class LanguageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
    name: str = Field(min_length=1, max_length=80)
    level: CefrLevel
    explanation_language: str = Field(default="es", min_length=2, max_length=8)
    weekly_goal: WeeklyGoal = Field(default_factory=WeeklyGoal)


class LanguageUpdate(BaseModel):
    level: CefrLevel | None = None
    weekly_goal: WeeklyGoal | None = None
    is_active: bool | None = None


class LanguageOut(BaseModel):
    id: str
    code: str
    name: str
    level: CefrLevel
    explanation_language: str
    is_active: bool
    archived: bool
    weekly_goal: WeeklyGoal
    created_at: str

    @classmethod
    def from_entity(cls, language: LanguageProfile) -> "LanguageOut":
        return cls(
            id=language.id,
            code=language.code,
            name=language.name,
            level=language.level,
            explanation_language=language.explanation_language,
            is_active=language.is_active,
            archived=language.archived,
            weekly_goal=WeeklyGoal(
                conversations=language.weekly_goal.conversations,
                minutes=language.weekly_goal.minutes,
            ),
            created_at=to_iso(language.created_at),
        )


class ConversationCreate(BaseModel):
    language_id: str = Field(min_length=1)
    mode: ConversationMode = ConversationMode.FREE
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    author: MessageAuthor
    content: str
    translation: str | None
    status: MessageStatus
    created_at: str

    @classmethod
    def from_entity(cls, message: Message) -> "MessageOut":
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            author=message.author,
            content=message.content,
            translation=message.translation,
            status=message.status,
            created_at=to_iso(message.created_at),
        )


class ConversationOut(BaseModel):
    id: str
    language_id: str
    mode: ConversationMode
    title: str
    message_count: int
    last_message_at: str | None
    created_at: str

    @classmethod
    def from_entity(cls, conversation: Conversation) -> "ConversationOut":
        return cls(
            id=conversation.id,
            language_id=conversation.language_id,
            mode=conversation.mode,
            title=conversation.title,
            message_count=conversation.message_count,
            last_message_at=(
                to_iso(conversation.last_message_at) if conversation.last_message_at else None
            ),
            created_at=to_iso(conversation.created_at),
        )


class ConversationPage(BaseModel):
    items: list[ConversationOut]
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: Page[Conversation]) -> "ConversationPage":
        return cls(
            items=[ConversationOut.from_entity(row) for row in page.items],
            next_cursor=page.next_cursor,
        )


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: Page[Message]) -> "MessagePage":
        return cls(
            items=[MessageOut.from_entity(row) for row in page.items],
            next_cursor=page.next_cursor,
        )


class ConversationDetailOut(ConversationOut):
    messages: MessagePage
