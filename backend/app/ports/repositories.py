"""Repository ports. `application/` depends on these, never on the SQLAlchemy adapters."""

from datetime import datetime
from typing import Protocol

from app.domain.entities import (
    CefrLevel,
    Conversation,
    LanguageProfile,
    Message,
    NewConversation,
    NewLanguage,
    WeeklyGoal,
)


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
