"""Conversation and message persistence."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import ConversationRow, MessageRow
from app.core.dates import utc_now
from app.domain.entities import (
    Conversation,
    ConversationMode,
    Message,
    MessageAuthor,
    MessageStatus,
    NewConversation,
    NewMessage,
)

# What the history is ordered by: the last message, or the creation when the conversation is empty.
_ACTIVITY = func.coalesce(ConversationRow.last_message_at, ConversationRow.created_at)


def _to_conversation(row: ConversationRow) -> Conversation:
    return Conversation(
        id=row.id,
        language_id=row.language_id,
        mode=ConversationMode(row.mode),
        title=row.title,
        message_count=row.message_count,
        last_message_at=row.last_message_at,
        created_at=row.created_at,
    )


def _to_message(row: MessageRow) -> Message:
    return Message(
        id=row.id,
        conversation_id=row.conversation_id,
        author=MessageAuthor(row.author),
        content=row.content,
        translation=row.translation,
        status=MessageStatus(row.status),
        created_at=row.created_at,
    )


class SqlAlchemyConversationRepository:
    """`ConversationRepository` port over SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_conversations(
        self,
        language_id: str,
        *,
        limit: int,
        after: tuple[datetime, str] | None = None,
    ) -> list[Conversation]:
        statement = select(ConversationRow).where(ConversationRow.language_id == language_id)
        if after is not None:
            activity_at, row_id = after
            statement = statement.where(
                or_(
                    _ACTIVITY < activity_at,
                    and_(_ACTIVITY == activity_at, ConversationRow.id < row_id),
                )
            )
        rows = await self._session.scalars(
            statement.order_by(_ACTIVITY.desc(), ConversationRow.id.desc()).limit(limit)
        )
        return [_to_conversation(row) for row in rows]

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        row = await self._session.get(ConversationRow, conversation_id)
        return _to_conversation(row) if row else None

    async def add_conversation(self, draft: NewConversation) -> Conversation:
        row = ConversationRow(
            id=str(uuid4()),
            language_id=draft.language_id,
            mode=draft.mode.value,
            title=draft.title,
            message_count=0,
            last_message_at=None,
            created_at=utc_now(),
        )
        self._session.add(row)
        await self._session.flush()
        return _to_conversation(row)

    async def rename_conversation(self, conversation_id: str, title: str) -> Conversation:
        row = await self._session.get(ConversationRow, conversation_id)
        if row is None:
            raise LookupError(conversation_id)
        row.title = title
        await self._session.flush()
        return _to_conversation(row)

    async def delete_conversation(self, conversation_id: str) -> None:
        row = await self._session.get(ConversationRow, conversation_id)
        if row is None:
            raise LookupError(conversation_id)
        await self._session.delete(row)
        await self._session.flush()

    async def record_message_activity(self, conversation_id: str, at: datetime) -> None:
        row = await self._session.get(ConversationRow, conversation_id)
        if row is None:
            raise LookupError(conversation_id)
        row.message_count += 1
        row.last_message_at = at
        await self._session.flush()


class SqlAlchemyMessageRepository:
    """`MessageRepository` port over SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        after: tuple[datetime, str] | None = None,
    ) -> list[Message]:
        statement = select(MessageRow).where(MessageRow.conversation_id == conversation_id)
        if after is not None:
            created_at, row_id = after
            statement = statement.where(
                or_(
                    MessageRow.created_at > created_at,
                    and_(MessageRow.created_at == created_at, MessageRow.id > row_id),
                )
            )
        rows = await self._session.scalars(
            statement.order_by(MessageRow.created_at, MessageRow.id).limit(limit)
        )
        return [_to_message(row) for row in rows]

    async def add_message(self, draft: NewMessage) -> Message:
        row = MessageRow(
            id=str(uuid4()),
            conversation_id=draft.conversation_id,
            author=draft.author.value,
            content=draft.content,
            translation=draft.translation,
            status=draft.status.value,
            idempotency_key=draft.idempotency_key,
            created_at=utc_now(),
        )
        self._session.add(row)
        await self._session.flush()
        return _to_message(row)

    async def find_message_by_key(self, conversation_id: str, key: str) -> Message | None:
        row = await self._session.scalar(
            select(MessageRow).where(
                MessageRow.conversation_id == conversation_id,
                MessageRow.idempotency_key == key,
            )
        )
        return _to_message(row) if row else None
