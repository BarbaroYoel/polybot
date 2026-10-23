"""The closing turn of a message, as it is stored (F3 S7).

`message_feedback` is 1:1 with the user message; a message with nothing to report has no row at
all, so the API answers `feedback: null` instead of an empty shell. The value objects below are
what the repositories hand to `application/` and `api/`; the drafts the provider returns live in
`app.ports.llm`, because validating them is the adapter's job.

`domain/` imports nothing from infrastructure (docs/architecture.md §3).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Correction:
    """One stored correction of the user message."""

    original: str
    corrected: str
    explanation: str


@dataclass(frozen=True, slots=True)
class VocabularyItem:
    """One stored term; `language_id` is the conversation's language, never the active one (S8).

    The id travels with the item because the vocabulary outlives the conversation and is read per
    language later, not only through its message.
    """

    term: str
    translation: str
    note: str | None
    language_id: str


@dataclass(frozen=True, slots=True)
class MessageFeedback:
    """The closing turn of one user message, reconstructed from storage."""

    message_id: str
    corrections: Sequence[Correction]
    vocabulary: Sequence[VocabularyItem]
    created_at: datetime
