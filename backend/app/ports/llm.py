"""The LLM port (F3 S1-S2).

`application/` depends on this protocol; the harness that runs the model is an adapter detail
(ADR-004). Pi is one adapter, not a dependency of the domain or the use cases.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities import CefrLevel, MessageAuthor


@dataclass(frozen=True, slots=True)
class TutorContext:
    """What the tutor needs to know about the language being practised (desing.md §6.6)."""

    language_name: str
    language_code: str
    level: CefrLevel
    explanation_language: str


@dataclass(frozen=True, slots=True)
class TurnMessage:
    """One previous message of the conversation, oldest first."""

    author: MessageAuthor
    content: str


@dataclass(frozen=True, slots=True)
class TutorTurn:
    """One turn: the conversation so far plus the message the user just sent."""

    context: TutorContext
    history: Sequence[TurnMessage]
    user_message: str


class LlmPort(Protocol):
    def stream_reply(self, turn: TutorTurn) -> AsyncIterator[str]:
        """Yield the tutor reply as text deltas, in order.

        Closing the iterator early asks the adapter to cancel the provider call and release every
        resource it holds (docs/architecture.md §5: cancellation).
        """
