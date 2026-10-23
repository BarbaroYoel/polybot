"""A deterministic double of the `LlmPort` (F3 S2, S5, S7).

The real adapter launches a Pi subprocess and needs a model; the API tests need the turn to be
predictable and offline. The double yields the configured deltas, optionally fails after them,
produces the configured closing feedback (or fails the closing call) and keeps what it received so
a test can assert the context, the history and the reply the closing call had to judge.
"""

from collections.abc import AsyncIterator, Sequence

from app.domain.errors import DomainError
from app.ports.llm import EMPTY_FEEDBACK, TurnFeedback, TutorTurn


class FakeLlm:
    """`LlmPort` double: configurable deltas, optional failures, and the captured calls."""

    def __init__(
        self,
        deltas: Sequence[str] = ("Bonjour", " !"),
        failure: DomainError | None = None,
        feedback: TurnFeedback = EMPTY_FEEDBACK,
        summary_failure: DomainError | None = None,
    ) -> None:
        self.deltas = list(deltas)
        self.failure = failure
        self.feedback = feedback
        self.summary_failure = summary_failure
        self.turn: TutorTurn | None = None
        self.calls = 0
        self.closed = False
        # One entry per closing call, in order: what the provider was asked to summarize.
        self.summaries: list[tuple[TutorTurn, str]] = []

    def stream_reply(self, turn: TutorTurn) -> AsyncIterator[str]:
        self.turn = turn
        self.calls += 1
        return self._reply()

    async def _reply(self) -> AsyncIterator[str]:
        try:
            for delta in self.deltas:
                yield delta
            if self.failure is not None:
                raise self.failure
        finally:
            # Mirrors the adapter: closing the iterator releases the provider call.
            self.closed = True

    async def summarize_turn(self, turn: TutorTurn, reply: str) -> TurnFeedback:
        self.summaries.append((turn, reply))
        if self.summary_failure is not None:
            raise self.summary_failure
        return self.feedback
