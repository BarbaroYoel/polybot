"""Provider-independent parsing of the answers the LLM port receives (F3 S7, ADR-014).

Both adapters (`pi` and `opencode`) speak a different wire protocol but must validate the model's
answer the same way: a translation is a sentence, not a wrapper, and feedback is strict JSON that a
model may surround with prose or fences. Keeping these rules here means a provider change cannot
silently change what counts as a usable answer.
"""

import json
from typing import Any

from app.domain.blocks import build_turn_blocks
from app.domain.errors import LlmUnavailable
from app.ports.llm import CorrectionDraft, TurnFeedback, VocabularyDraft

# A runaway answer is cut instead of stored: the UI never renders more than this per turn.
MAX_REPLY_CHARS = 20_000

# A translation of a bounded text (docs/api-contract.md §5) is a sentence or a short paragraph; more
# than this is not a translation but the model answering something else.
MAX_TRANSLATION_CHARS = 6_000

# A lesson comment is one to three sentences; anything longer is the model writing a lesson.
MAX_LESSON_COMMENT_CHARS = 1_200

# docs/api-contract.md §3: the cards of one turn are bounded, and the prompt asks for the same.
MAX_CORRECTIONS = 5
MAX_VOCABULARY_TERMS = 8

MALFORMED_FEEDBACK_MESSAGE = "El tutor devolvió un cierre de turno ilegible. Vuelve a intentar."
EMPTY_TRANSLATION_MESSAGE = "El traductor no devolvió texto. Vuelve a intentar."
UNREADABLE_ANSWER_MESSAGE = "El tutor devolvió una respuesta ilegible. Vuelve a intentar."

_WRAPPING_QUOTES = (('"', '"'), ("'", "'"), ("«", "»"), ("“", "”"))


def parse_translation(answer: str) -> str:
    """The translation, or `LlmUnavailable` when the answer is not a usable one (ADR-014).

    The prompt asks for the sentence alone; a model that still wraps it in quotes is unwrapped
    here instead of being stored with them. Nothing else is repaired: an empty answer is a failure,
    not a translation, and a runaway answer is refused instead of truncated.
    """
    text = answer.strip()
    for opening, closing in _WRAPPING_QUOTES:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            text = text[len(opening) : -len(closing)].strip()
            break
    if not text:
        raise LlmUnavailable(EMPTY_TRANSLATION_MESSAGE)
    if len(text) > MAX_TRANSLATION_CHARS:
        raise LlmUnavailable(UNREADABLE_ANSWER_MESSAGE)
    return text


def parse_turn_feedback(answer: str) -> TurnFeedback:
    """Turn the closing answer into feedback: tolerant envelope, strict content (S7, ADR-020).

    Accepts a plain object, a ```json fenced block or an object surrounded by prose, and extracts
    the first decodable JSON object. Anything that cannot be validated is an `LlmUnavailable`: the
    turn keeps its reply and the chat closes without feedback cards.

    The sections are independent on purpose: a broken `blocks` list is dropped without losing the
    corrections, because the text the student already read is the part that must never regress.
    """
    payload = _first_json_object(answer)
    if payload is None or not ("corrections" in payload or "vocabulary" in payload):
        raise LlmUnavailable(MALFORMED_FEEDBACK_MESSAGE)

    corrections: list[CorrectionDraft] = []
    for item in _items(payload, "corrections"):
        draft = _correction(item)
        if draft is not None:
            corrections.append(draft)
        if len(corrections) == MAX_CORRECTIONS:
            break

    vocabulary: list[VocabularyDraft] = []
    for item in _items(payload, "vocabulary"):
        draft = _vocabulary(item)
        if draft is not None:
            vocabulary.append(draft)
        if len(vocabulary) == MAX_VOCABULARY_TERMS:
            break

    return TurnFeedback(
        corrections=tuple(corrections),
        vocabulary=tuple(vocabulary),
        blocks=build_turn_blocks(_block_items(payload)),
    )


def _first_json_object(answer: str) -> dict[str, Any] | None:
    """The first complete JSON object in the answer, fences and prose included."""
    decoder = json.JSONDecoder()
    index = answer.find("{")
    while index != -1:
        try:
            value, _ = decoder.raw_decode(answer, index)
        except json.JSONDecodeError:
            index = answer.find("{", index + 1)
            continue
        if isinstance(value, dict):
            return value
        index = answer.find("{", index + 1)
    return None


def _items(payload: dict[str, Any], name: str) -> list[Any]:
    """The list behind `name`; a missing key means nothing to report, a wrong type is malformed."""
    if name not in payload:
        return []
    value = payload[name]
    if not isinstance(value, list):
        raise LlmUnavailable(MALFORMED_FEEDBACK_MESSAGE)
    return value


def _block_items(payload: dict[str, Any]) -> list[Any]:
    """Proposed blocks: optional and never fatal (ADR-020).

    The domain drops the ones that do not fit, so a wrong type here cannot cost the student the
    corrections of the same turn.
    """
    value = payload.get("blocks")
    return value if isinstance(value, list) else []


def _correction(item: Any) -> CorrectionDraft | None:
    if not isinstance(item, dict):
        return None
    original = _text(item.get("original"))
    corrected = _text(item.get("corrected"))
    explanation = _text(item.get("explanation"))
    if original is None or corrected is None or explanation is None:
        return None
    return CorrectionDraft(original=original, corrected=corrected, explanation=explanation)


def _vocabulary(item: Any) -> VocabularyDraft | None:
    if not isinstance(item, dict):
        return None
    term = _text(item.get("term"))
    translation = _text(item.get("translation"))
    if term is None or translation is None:
        return None
    # `note` is optional: a blank or non-string value simply means there is nothing to add.
    return VocabularyDraft(term=term, translation=translation, note=_text(item.get("note")))


def _text(value: Any) -> str | None:
    """A non-empty, trimmed string, or `None` when the value cannot be rendered."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
