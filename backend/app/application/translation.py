"""Translation of one message and of a fragment (S1-S5, ADR-014).

The direction is decided here, from the conversation's own language profile, and never from the
globally active language: a translation belongs to the language being practised (AGENTS.md §3).

`api/` calls one of two use cases and serializes the result. Persisting the message translation is
not optional: the chat screen shows it again after a reload, so the stored row is the answer.
"""

from dataclasses import dataclass

from app.domain.entities import Message, MessageAuthor
from app.domain.errors import ConversationNotFound, LanguageNotFound, MessageNotFound
from app.domain.feedback import MessageFeedback
from app.ports.llm import LlmPort, TranslationRequest
from app.ports.repositories import (
    ConversationRepository,
    LanguageRepository,
    MessageRepository,
)


@dataclass(frozen=True, slots=True)
class Translation:
    """A translation and the source it was asked for (`None` when the provider had to detect it)."""

    text: str
    detected_source: str | None


@dataclass(frozen=True, slots=True)
class TranslatedMessage:
    """A stored message plus the closing-turn feedback the detail endpoint would also return."""

    message: Message
    feedback: MessageFeedback | None = None


class TranslationService:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        messages: MessageRepository,
        languages: LanguageRepository,
        llm: LlmPort,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._languages = languages
        self._llm = llm

    async def translate_text(self, *, text: str, source: str | None, target: str) -> Translation:
        """Translate the fragment the user selected: nothing is stored (S2)."""
        translated = await self._llm.translate(
            TranslationRequest(text=text, target_language=target, source_language=source)
        )
        return Translation(text=translated, detected_source=source)

    async def translate_message(
        self, *, conversation_id: str, message_id: str
    ) -> TranslatedMessage:
        """Translate and store the whole message: a stored translation is never asked twice (S2)."""
        conversation = await self._conversations.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(conversation_id)

        message = await self._messages.get_message(message_id)
        if message is None or message.conversation_id != conversation_id:
            raise MessageNotFound(message_id)

        if message.translation:
            return TranslatedMessage(message, await self._feedback(message))

        language = await self._languages.get_language(conversation.language_id)
        if language is None:
            raise LanguageNotFound(conversation.language_id)

        translated = await self._llm.translate(
            TranslationRequest(
                text=message.content,
                target_language=language.explanation_language,
                source_language=language.code,
            )
        )
        stored = await self._messages.set_translation(message.id, translated)
        return TranslatedMessage(stored, await self._feedback(stored))

    async def _feedback(self, message: Message) -> MessageFeedback | None:
        """Only a user message closes a turn; a tutor message has no feedback to attach."""
        if message.author is not MessageAuthor.USER:
            return None
        found = await self._messages.feedback_for_messages([message.id])
        return found.get(message.id)
