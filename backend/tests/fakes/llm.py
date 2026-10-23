"""A deterministic double of the `LlmPort` (F3 S2, S5).

The real adapter launches a Pi subprocess and needs a model; the API tests need the turn to be
predictable and offline. The double yields the configured deltas, optionally fails after them, and
keeps the `TutorTurn` it received so a test can assert the context and the history.
"""

from collections.abc import AsyncIterator, Sequence

from app.domain.errors import DomainError
from app.ports.llm import TutorTurn


class FakeLlm:
    """`LlmPort` double: configurable deltas, an optional failure, and the captured turn."""

    def __init__(
        self,
        deltas: Sequence[str] = ("Bonjour", " !"),
        failure: DomainError | None = None,
    ) -> None:
        self.deltas = list(deltas)
        self.failure = failure
        self.turn: TutorTurn | None = None
        self.calls = 0
        self.closed = False

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
