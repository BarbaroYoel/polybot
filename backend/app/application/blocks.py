"""Answering one drill of a turn (ADR-020).

The drill is graded here, not in the UI and not by the model: `domain/grading.py` decides what
counts as the same answer, exactly like a lesson exercise (ADR-017). That is why the endpoint can
be stateless: no attempt is stored, so `/progress` keeps deriving from the signals it already has
(ADR-018) and a second answer simply grades again.

The endpoint reads the stored block, so the accepted answers never have to travel to the browser to
be checked — the client sends what the student typed, nothing else.
"""

from app.domain.blocks import DrillAnswer, DrillBlock, grade_drill
from app.domain.errors import (
    BlockNotAnswerable,
    BlockNotFound,
    ConversationNotFound,
    MessageNotFound,
)
from app.ports.repositories import ConversationRepository, MessageRepository


class BlockService:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        messages: MessageRepository,
    ) -> None:
        self._conversations = conversations
        self._messages = messages

    async def answer(
        self,
        *,
        conversation_id: str,
        message_id: str,
        block_id: str,
        answer: str,
    ) -> DrillAnswer:
        """Grade one answer of a drill that belongs to `message_id` (contract §3).

        A message of another conversation is `message_not_found`, never a leak: the same rule the
        stream and the translation already follow.
        """
        conversation = await self._conversations.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(conversation_id)

        message = await self._messages.get_message(message_id)
        if message is None or message.conversation_id != conversation_id:
            raise MessageNotFound(message_id)

        block = next((item for item in message.blocks if item.id == block_id), None)
        if block is None:
            raise BlockNotFound(block_id)
        if not isinstance(block, DrillBlock):
            # A phrase has nothing to answer: 400, not a silent empty result.
            raise BlockNotAnswerable(block_id)

        return grade_drill(block, answer)
