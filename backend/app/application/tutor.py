"""The tutor turn: open it, stream it, close it (F3 S5, S6, S7, S8).

`api/` starts a turn and returns an SSE response; this module owns the order of the writes, so the
HTTP layer never decides when the stored message becomes `sent` or `error`.

Three rules drive the design:

- The `streaming` row is committed *before* the first token leaves, so a reconnect always finds the
  turn that is running.
- The closing write is committed *before* `message_end` is emitted, so the event never announces a
  message the database does not have yet.
- The closing step (corrections and vocabulary) runs *after* `message_end` and is allowed to fail:
  the chat is never broken by the feedback (S7).

`commit` arrives as a callable because the stream outlives the request's unit of transaction.
"""

import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from app.domain.entities import (
    Conversation,
    LanguageProfile,
    Message,
    MessageAuthor,
    MessageStatus,
    NewMessage,
)
from app.domain.errors import (
    ConversationNotFound,
    DomainError,
    InvalidTurnMessage,
    LanguageNotFound,
    LlmTimeout,
    LlmUnavailable,
    MessageNotFound,
)
from app.ports.llm import LlmPort, TurnFeedback, TurnMessage, TutorContext, TutorTurn
from app.ports.repositories import (
    ConversationRepository,
    LanguageRepository,
    MessageRepository,
)

logger = logging.getLogger(__name__)

# How much of the conversation travels with the turn: the 30 messages before the new one.
HISTORY_LIMIT = 30


@dataclass(frozen=True, slots=True)
class TurnState:
    """A validated turn: the stored tutor message and what the provider will receive."""

    message: Message
    conversation: Conversation
    language: LanguageProfile
    turn: TutorTurn
    # The user message that opened the turn: the subject of the feedback events (S7).
    user_message_id: str


@dataclass(frozen=True, slots=True)
class TurnToken:
    """One text delta, tagged with the tutor message it belongs to."""

    message_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    """The turn closed: the stored message, final content and `sent`."""

    message: Message


@dataclass(frozen=True, slots=True)
class TurnError:
    """The turn failed; `api/` decides how that looks over HTTP (one mapping, two transports)."""

    error: DomainError


@dataclass(frozen=True, slots=True)
class TurnFeedbackReady:
    """The closing step of the turn: what to correct and which terms to keep (S7)."""

    message_id: str
    feedback: TurnFeedback


TurnEvent = TurnToken | TurnCompleted | TurnError | TurnFeedbackReady


class TutorService:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        messages: MessageRepository,
        languages: LanguageRepository,
        llm: LlmPort,
        commit: Callable[[], Awaitable[None]],
        history_limit: int = HISTORY_LIMIT,
        rollback: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._languages = languages
        self._llm = llm
        self._commit = commit
        self._history_limit = history_limit
        # Only for the closing step: a failed write must not poison the request's session.
        self._rollback = rollback

    async def begin_turn(self, conversation_id: str, message_id: str) -> TurnState:
        """Validate the turn, load its context and store the tutor message as `streaming`."""
        conversation = await self._conversations.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(conversation_id)

        message = await self._messages.get_message(message_id)
        # A message is only reachable from its own conversation (S8).
        if message is None or message.conversation_id != conversation_id:
            raise MessageNotFound(message_id)
        if message.author is not MessageAuthor.USER:
            raise InvalidTurnMessage(message_id)

        # The turn follows the conversation's language, never the globally active one (S8).
        language = await self._languages.get_language(conversation.language_id)
        if language is None:
            raise LanguageNotFound(conversation.language_id)

        history = await self._messages.list_messages_before(
            conversation_id, message, limit=self._history_limit
        )
        stored = await self._messages.add_message(
            NewMessage(
                conversation_id=conversation_id,
                author=MessageAuthor.TUTOR,
                content="",
                status=MessageStatus.STREAMING,
            )
        )
        await self._conversations.record_message_activity(conversation_id, stored.created_at)
        # The placeholder must be visible before the first token: the client can reconnect to it.
        await self._commit()

        return TurnState(
            message=stored,
            conversation=conversation,
            language=language,
            turn=TutorTurn(
                context=_tutor_context(language),
                history=[TurnMessage(author=row.author, content=row.content) for row in history],
                user_message=message.content,
            ),
            user_message_id=message.id,
        )

    async def stream_turn(self, state: TurnState) -> AsyncIterator[TurnEvent]:
        """Yield the provider deltas, then close the turn; never leave a half-written row behind."""
        deltas = self._llm.stream_reply(state.turn)
        written: list[str] = []
        try:
            async for delta in deltas:
                written.append(delta)
                yield TurnToken(message_id=state.message.id, delta=delta)
        except (LlmUnavailable, LlmTimeout) as exc:
            # The turn failed: the text already shown stays, the status says it is incomplete.
            await self._store(state.message, "".join(written), MessageStatus.ERROR)
            yield TurnError(error=exc)
            return
        except BaseException:
            # The client walked away (S6): kill the provider call, keep what was written, say
            # `error`, and let the cancellation continue on its way.
            with contextlib.suppress(BaseException):
                await _close(deltas)
            await self._abandon(state.message, "".join(written))
            raise
        else:
            await _close(deltas)

        message = await self._store(state.message, "".join(written), MessageStatus.SENT)
        yield TurnCompleted(message=message)

        # Only now: `message_end` already left, so nothing below can retract the turn (S7).
        feedback = await self._close_turn(state, message.content)
        if feedback is not None:
            yield TurnFeedbackReady(message_id=state.user_message_id, feedback=feedback)

    async def _store(self, message: Message, content: str, status: MessageStatus) -> Message:
        updated = await self._messages.update_message(message.id, content=content, status=status)
        # Committed here, not at request teardown: `message_end` must not outrun the row.
        await self._commit()
        return updated

    async def _close_turn(self, state: TurnState, reply: str) -> TurnFeedback | None:
        """Corrections and vocabulary for the user message, or nothing when that step fails.

        S7: a broken closing call must not break the chat. The reply is already stored as `sent`
        and `message_end` already left, so the stream simply ends without the feedback events and
        the conversation detail keeps `feedback: null` for that message.
        """
        try:
            feedback = await self._llm.summarize_turn(state.turn, reply)
        except Exception:
            # Not `BaseException`: a cancelled stream still propagates (S6).
            logger.warning(
                "closing turn for message %s failed; feedback skipped",
                state.user_message_id,
                exc_info=True,
            )
            return None

        if feedback.is_empty:
            # Nothing to correct and nothing new to learn: no rows, no events, `feedback: null`.
            return None

        try:
            await self._messages.save_feedback(
                state.user_message_id, state.conversation.language_id, feedback
            )
            # Committed before the events: they announce rows that already exist.
            await self._commit()
        except Exception:
            logger.warning(
                "storing feedback for message %s failed",
                state.user_message_id,
                exc_info=True,
            )
            await self._discard()
            return None
        return feedback

    async def _abandon(self, message: Message, content: str) -> None:
        """Best effort: a cancelled request still records what the user already saw."""
        with contextlib.suppress(Exception):
            await self._store(message, content, MessageStatus.ERROR)

    async def _discard(self) -> None:
        """Leave the session usable after a failed write; never raise from the closing step."""
        if self._rollback is None:
            return
        with contextlib.suppress(Exception):
            await self._rollback()


def _tutor_context(language: LanguageProfile) -> TutorContext:
    return TutorContext(
        language_name=language.name,
        language_code=language.code,
        level=language.level,
        explanation_language=language.explanation_language,
    )


async def _close(deltas: AsyncIterator[str]) -> None:
    """Close the provider iterator so the adapter can release its subprocess (S6)."""
    aclose = getattr(deltas, "aclose", None)
    if aclose is None:
        return
    with contextlib.suppress(Exception):
        await aclose()
