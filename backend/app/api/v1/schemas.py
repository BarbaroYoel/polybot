"""Request and response models. They mirror docs/api-contract.md §2 field by field."""

from collections.abc import Iterable, Mapping
from typing import Annotated, Protocol

from pydantic import BaseModel, Field, StringConstraints

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
from app.domain.feedback import MessageFeedback
from app.ports.llm import TurnFeedback


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


# Contract §5 will list the message limit; a Portuguese/Spanish turn fits comfortably in 4000 chars.
MessageContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]


class MessageCreate(BaseModel):
    content: MessageContent


# Contract §5: the text of a translation is bounded like a message; a selection is shorter.
TranslationText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
# ISO 639-1 (`fr`) or a regional variant (`pt-BR`).
LanguageCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=8)]


class TranslateRequest(BaseModel):
    """The stateless translation: a message or a fragment, with the direction the UI decided."""

    text: TranslationText
    source: LanguageCode | None = None
    target: LanguageCode


class TranslateOut(BaseModel):
    translation: str
    # The source used, or `null` when the caller did not send one and the provider detected it.
    detected_source: str | None


class CorrectionOut(BaseModel):
    """One correction card of a closing turn (F3 S7)."""

    original: str
    corrected: str
    explanation: str


class VocabularyOut(BaseModel):
    """One suggested term of the closing turn."""

    term: str
    translation: str
    note: str | None


class _CorrectionLike(Protocol):
    original: str
    corrected: str
    explanation: str


class _VocabularyLike(Protocol):
    term: str
    translation: str
    note: str | None


def _corrections(items: Iterable[_CorrectionLike]) -> list[CorrectionOut]:
    return [
        CorrectionOut(
            original=item.original, corrected=item.corrected, explanation=item.explanation
        )
        for item in items
    ]


def _vocabulary(items: Iterable[_VocabularyLike]) -> list[VocabularyOut]:
    return [
        VocabularyOut(term=item.term, translation=item.translation, note=item.note)
        for item in items
    ]


class MessageFeedbackOut(BaseModel):
    """`Message.feedback`: `null` for tutor messages and for user messages with no closing turn."""

    corrections: list[CorrectionOut]
    vocabulary: list[VocabularyOut]

    @classmethod
    def from_entity(cls, feedback: MessageFeedback) -> "MessageFeedbackOut":
        return cls(
            corrections=_corrections(feedback.corrections),
            vocabulary=_vocabulary(feedback.vocabulary),
        )

    @classmethod
    def from_turn_feedback(cls, feedback: TurnFeedback) -> "MessageFeedbackOut":
        """The closing events are emitted before the rows are read back, from the same drafts."""
        return cls(
            corrections=_corrections(feedback.corrections),
            vocabulary=_vocabulary(feedback.vocabulary),
        )


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    author: MessageAuthor
    content: str
    translation: str | None
    status: MessageStatus
    feedback: MessageFeedbackOut | None = None
    created_at: str

    @classmethod
    def from_entity(cls, message: Message, feedback: MessageFeedback | None = None) -> "MessageOut":
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            author=message.author,
            content=message.content,
            translation=message.translation,
            status=message.status,
            feedback=MessageFeedbackOut.from_entity(feedback) if feedback is not None else None,
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
    def from_page(
        cls,
        page: Page[Message],
        feedback: Mapping[str, MessageFeedback] | None = None,
    ) -> "MessagePage":
        """`feedback` arrives already fetched for the page: the schema never queries (no N+1)."""
        attached = feedback or {}
        return cls(
            items=[MessageOut.from_entity(row, attached.get(row.id)) for row in page.items],
            next_cursor=page.next_cursor,
        )


class ConversationDetailOut(ConversationOut):
    messages: MessagePage
