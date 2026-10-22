"""Use cases: they orchestrate ports and hold the rules that are not HTTP and not SQL."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Page[T]:
    """A page of results and the cursor for the next one, if any (docs/api-contract.md §1)."""

    items: list[T]
    next_cursor: str | None = None
