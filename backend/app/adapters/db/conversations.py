"""Conversation and message persistence."""

import json
from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    ConversationRow,
    MessageCorrectionRow,
    MessageFeedbackRow,
    MessageRow,
    VocabularyItemRow,
)
from app.core.dates import utc_now
from app.domain.blocks import (
    TurnBlock,
    blocks_from_storage,
    blocks_to_storage,
)
from app.domain.entities import (
    Conversation,
    ConversationMode,
    Message,
    MessageAuthor,
    MessageStatus,
    NewConversation,
    NewMessage,
)
from app.domain.feedback import Correction, MessageFeedback, VocabularyItem
from app.ports.llm import TurnFeedback

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
        blocks=_stored_blocks(row.blocks_json),
    )


def _stored_blocks(raw: str | None) -> tuple[TurnBlock, ...]:
    """Blocks of a message, tolerating a row written by a version this one cannot read (ADR-020)."""
    if not raw:
        return ()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    return blocks_from_storage(items) if isinstance(items, list) else ()


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

    async def get_message(self, message_id: str) -> Message | None:
        row = await self._session.get(MessageRow, message_id)
        return _to_message(row) if row else None

    async def update_message(
        self, message_id: str, *, content: str, status: MessageStatus
    ) -> Message:
        row = await self._session.get(MessageRow, message_id)
        if row is None:
            raise LookupError(message_id)
        row.content = content
        row.status = status.value
        await self._session.flush()
        return _to_message(row)

    async def set_translation(self, message_id: str, translation: str) -> Message:
        row = await self._session.get(MessageRow, message_id)
        if row is None:
            raise LookupError(message_id)
        row.translation = translation
        await self._session.flush()
        return _to_message(row)

    async def save_blocks(self, message_id: str, blocks: Sequence[TurnBlock]) -> Message:
        """Attach the practice blocks to the tutor message, replacing whatever it had (ADR-020).

        A retried turn rewrites the same message, so the blocks are replaced instead of appended:
        the thread never shows two versions of the same drill.
        """
        row = await self._session.get(MessageRow, message_id)
        if row is None:
            raise LookupError(message_id)
        row.blocks_json = json.dumps(blocks_to_storage(blocks), ensure_ascii=False)
        await self._session.flush()
        return _to_message(row)

    async def list_messages_before(
        self, conversation_id: str, before: Message, *, limit: int
    ) -> list[Message]:
        # Newest first to keep the window next to the turn, then reversed for the prompt.
        statement = (
            select(MessageRow)
            .where(
                MessageRow.conversation_id == conversation_id,
                or_(
                    MessageRow.created_at < before.created_at,
                    and_(
                        MessageRow.created_at == before.created_at,
                        MessageRow.id < before.id,
                    ),
                ),
            )
            .order_by(MessageRow.created_at.desc(), MessageRow.id.desc())
            .limit(limit)
        )
        rows = await self._session.scalars(statement)
        return [_to_message(row) for row in reversed(list(rows))]

    async def save_feedback(
        self, message_id: str, language_id: str, feedback: TurnFeedback
    ) -> MessageFeedback:
        """Store the closing turn of one user message (S7), replacing it when it already exists.

        A retried turn (`GET /stream` again with the same message) must not duplicate or fail: the
        previous row is deleted and the new one written, children included by `ON DELETE CASCADE`.
        """
        previous = await self._session.scalar(
            select(MessageFeedbackRow).where(MessageFeedbackRow.message_id == message_id)
        )
        if previous is not None:
            await self._session.delete(previous)
            await self._session.flush()

        created_at = utc_now()
        row = MessageFeedbackRow(id=str(uuid4()), message_id=message_id, created_at=created_at)
        self._session.add(row)
        await self._session.flush()

        corrections: list[Correction] = []
        for position, draft in enumerate(feedback.corrections):
            self._session.add(
                MessageCorrectionRow(
                    id=str(uuid4()),
                    feedback_id=row.id,
                    position=position,
                    original=draft.original,
                    corrected=draft.corrected,
                    explanation=draft.explanation,
                )
            )
            corrections.append(
                Correction(
                    original=draft.original,
                    corrected=draft.corrected,
                    explanation=draft.explanation,
                )
            )

        vocabulary: list[VocabularyItem] = []
        for position, draft in enumerate(feedback.vocabulary):
            self._session.add(
                VocabularyItemRow(
                    id=str(uuid4()),
                    # The conversation's language, never the active one (S8).
                    language_id=language_id,
                    feedback_id=row.id,
                    position=position,
                    term=draft.term,
                    translation=draft.translation,
                    note=draft.note,
                    created_at=created_at,
                )
            )
            vocabulary.append(
                VocabularyItem(
                    term=draft.term,
                    translation=draft.translation,
                    note=draft.note,
                    language_id=language_id,
                )
            )

        await self._session.flush()
        return MessageFeedback(
            message_id=message_id,
            corrections=corrections,
            vocabulary=vocabulary,
            created_at=created_at,
        )

    async def feedback_for_messages(self, message_ids: Sequence[str]) -> dict[str, MessageFeedback]:
        """The closing turns of a page of messages, in one query (no N+1).

        The two `LEFT JOIN`s cross corrections with vocabulary, so the rows are folded back by
        `(message, position)`; both lists are small by contract (5 and 8) and empty for most
        messages, which keeps this cheaper than one query per message.
        """
        ids = list(dict.fromkeys(message_ids))
        if not ids:
            return {}

        statement = (
            select(MessageFeedbackRow, MessageCorrectionRow, VocabularyItemRow)
            .outerjoin(
                MessageCorrectionRow,
                MessageCorrectionRow.feedback_id == MessageFeedbackRow.id,
            )
            .outerjoin(
                VocabularyItemRow,
                VocabularyItemRow.feedback_id == MessageFeedbackRow.id,
            )
            .where(MessageFeedbackRow.message_id.in_(ids))
            .order_by(
                MessageFeedbackRow.message_id,
                MessageCorrectionRow.position,
                VocabularyItemRow.position,
            )
        )
        rows = await self._session.execute(statement)

        corrections: dict[str, dict[int, Correction]] = {}
        vocabulary: dict[str, dict[int, VocabularyItem]] = {}
        # Insertion-ordered, so the answer follows the query even after the cross join repeats rows.
        order: dict[str, None] = {}
        created_at: dict[str, datetime] = {}
        for feedback_row, correction_row, vocabulary_row in rows:
            message_id = feedback_row.message_id
            order.setdefault(message_id, None)
            created_at[message_id] = feedback_row.created_at
            if correction_row is not None:
                corrections.setdefault(message_id, {})[correction_row.position] = Correction(
                    original=correction_row.original,
                    corrected=correction_row.corrected,
                    explanation=correction_row.explanation,
                )
            if vocabulary_row is not None:
                vocabulary.setdefault(message_id, {})[vocabulary_row.position] = VocabularyItem(
                    term=vocabulary_row.term,
                    translation=vocabulary_row.translation,
                    note=vocabulary_row.note,
                    language_id=vocabulary_row.language_id,
                )

        return {
            message_id: MessageFeedback(
                message_id=message_id,
                corrections=list(corrections.get(message_id, {}).values()),
                vocabulary=list(vocabulary.get(message_id, {}).values()),
                created_at=created_at[message_id],
            )
            for message_id in order
        }
