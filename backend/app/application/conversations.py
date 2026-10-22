"""Conversation use cases (docs/api-contract.md §3 "Conversaciones y mensajes")."""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol, TypeVar

from app.application.pagination import Page
from app.core.pagination import encode_cursor
from app.domain.entities import (
    Conversation,
    ConversationMode,
    Message,
    NewConversation,
)
from app.domain.errors import ConversationNotFound, LanguageNotFound
from app.ports.repositories import ConversationRepository, LanguageRepository, MessageRepository

# Without an LLM yet, a conversation needs a title the user can rename (desing.md §6.1.1).
DEFAULT_CONVERSATION_TITLE = "Nueva conversación"


class _CursorRow(Protocol):
    id: str


T = TypeVar("T", bound=_CursorRow)


class ConversationService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        languages: LanguageRepository,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._languages = languages

    async def list_conversations(
        self,
        *,
        language_id: str,
        limit: int,
        after: tuple[datetime, str] | None = None,
    ) -> Page[Conversation]:
        await self._require_language(language_id)
        rows = await self._conversations.list_conversations(
            language_id, limit=limit + 1, after=after
        )
        return self._page(rows, limit=limit, key=lambda row: row.activity_at)

    async def get_conversation_detail(
        self,
        conversation_id: str,
        *,
        language_id: str | None = None,
        messages_limit: int,
        messages_after: tuple[datetime, str] | None = None,
    ) -> tuple[Conversation, Page[Message]]:
        conversation = await self._conversations.get_conversation(conversation_id)
        # A conversation is only reachable from its own language (S8).
        if conversation is None or (
            language_id is not None and conversation.language_id != language_id
        ):
            raise ConversationNotFound(conversation_id)

        rows = await self._messages.list_messages(
            conversation_id, limit=messages_limit + 1, after=messages_after
        )
        return conversation, self._page(rows, limit=messages_limit, key=lambda row: row.created_at)

    async def create_conversation(
        self,
        *,
        language_id: str,
        mode: ConversationMode,
        title: str | None = None,
    ) -> Conversation:
        await self._require_language(language_id)
        return await self._conversations.add_conversation(
            NewConversation(
                language_id=language_id,
                mode=mode,
                title=(title or DEFAULT_CONVERSATION_TITLE).strip(),
            )
        )

    async def rename_conversation(self, conversation_id: str, title: str) -> Conversation:
        await self._require_conversation(conversation_id)
        return await self._conversations.rename_conversation(conversation_id, title.strip())

    async def delete_conversation(self, conversation_id: str) -> None:
        await self._require_conversation(conversation_id)
        await self._conversations.delete_conversation(conversation_id)

    async def _require_language(self, language_id: str) -> None:
        if await self._languages.get_language(language_id) is None:
            raise LanguageNotFound(language_id)

    async def _require_conversation(self, conversation_id: str) -> Conversation:
        conversation = await self._conversations.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(conversation_id)
        return conversation

    @staticmethod
    def _page(rows: Sequence[T], *, limit: int, key: Callable[[T], datetime]) -> Page[T]:
        """One extra row was requested: its presence means there is a next page."""
        items = list(rows[:limit])
        has_more = len(rows) > limit
        next_cursor = encode_cursor(key(items[-1]), items[-1].id) if has_more and items else None
        return Page(items=items, next_cursor=next_cursor)
