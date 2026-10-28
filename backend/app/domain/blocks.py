"""Practice blocks a tutor turn may carry (ADR-020).

A block is a small, typed object the PWA renders inside the thread: a phrase to listen to or a
one-question drill. The model proposes content, never presentation: it cannot choose a component,
nest blocks or reach the layout. That is the difference with a `render_ui` tool — the contract here
is validated by the domain and the renderer only picks how to draw a known `kind`.

Three rules shape the type:

- The tree is flat. There is no block inside a block, so no recursion and no depth limit to police.
- The turn is bounded. Two blocks at most, one of them interactive: the chat stays a chat.
- The answers of a drill are stored but never sent to the client before the student answers, so the
  exercise cannot be solved by reading the payload (see `public`).

`domain/` imports no infrastructure (docs/architecture.md §3): stdlib only.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.domain.grading import is_correct

# docs/api-contract.md §5: one turn is a sentence, not a lesson plan.
MAX_BLOCKS = 2
MAX_INTERACTIVE_BLOCKS = 1
MAX_PHRASE_CHARS = 200
MAX_DRILL_PROMPT_CHARS = 300
MAX_DRILL_ANSWERS = 5
MAX_DRILL_ANSWER_CHARS = 200
MAX_DRILL_EXPLANATION_CHARS = 400


class BlockKind(StrEnum):
    """The kinds the renderer knows. An unknown kind never reaches the client."""

    PHRASE = "phrase"
    DRILL = "drill"


@dataclass(frozen=True, slots=True)
class PhraseBlock:
    """A sentence of the practised language worth hearing again.

    The audio is not stored: the client synthesizes it with F4's `/voice/speech`, like any other
    message, so a phrase costs no new audio work.
    """

    id: str
    text: str

    @property
    def kind(self) -> BlockKind:
        return BlockKind.PHRASE

    @property
    def interactive(self) -> bool:
        return False

    def public(self) -> dict[str, Any]:
        """What the client receives: no private field is dropped because there is none."""
        return {"id": self.id, "kind": self.kind.value, "text": self.text}

    def storage(self) -> dict[str, Any]:
        return self.public()


@dataclass(frozen=True, slots=True)
class DrillBlock:
    """One question the student answers in the practised language, graded without the model.

    `accepted_answers` is ordered: the first one is what the API reveals after a miss, and all of
    them are accepted by the deterministic comparison of `domain/grading.py`. It never travels to
    the client before the answer, and neither does `explanation`, which usually gives the answer
    away.
    """

    id: str
    prompt: str
    accepted_answers: tuple[str, ...]
    explanation: str

    @property
    def kind(self) -> BlockKind:
        return BlockKind.DRILL

    @property
    def interactive(self) -> bool:
        return True

    @property
    def expected(self) -> str:
        return self.accepted_answers[0]

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "prompt": self.prompt}

    def storage(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "prompt": self.prompt,
            "accepted_answers": list(self.accepted_answers),
            "explanation": self.explanation,
        }


TurnBlock = PhraseBlock | DrillBlock


@dataclass(frozen=True, slots=True)
class DrillAnswer:
    """The result of one drill, as the API answers it (contract §3).

    `expected` is only revealed after a miss; on a correct answer it is `None`, so the response
    cannot be used to harvest the accepted answers one attempt at a time.
    """

    correct: bool
    expected: str | None
    explanation: str


def build_turn_blocks(items: Sequence[Any]) -> tuple[TurnBlock, ...]:
    """Validate what the provider proposed, dropping what does not fit (ADR-020).

    A malformed block is discarded, never repaired: the turn keeps its text and the blocks that
    survived. Order is kept, and the limit of one interactive block is enforced here, not in the
    prompt, because a prompt is a request and this is a rule.
    """
    blocks: list[TurnBlock] = []
    interactive = 0
    for item in items:
        if len(blocks) == MAX_BLOCKS:
            break
        block = _block_from_mapping(item, block_id=f"b{len(blocks) + 1}")
        if block is None:
            continue
        if block.interactive:
            if interactive == MAX_INTERACTIVE_BLOCKS:
                continue
            interactive += 1
        blocks.append(block)
    return tuple(blocks)


def blocks_from_storage(items: Sequence[Any]) -> tuple[TurnBlock, ...]:
    """Rebuild stored blocks, skipping the ones this version no longer understands (ADR-020).

    Storage is read on every conversation load, so a row written by a newer version cannot break
    the thread: an unknown `kind` or a missing field simply leaves the block out.
    """
    blocks: list[TurnBlock] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        block_id = item.get("id")
        if not isinstance(block_id, str) or not block_id.strip():
            continue
        block = _block_from_mapping(item, block_id=block_id.strip())
        if block is not None:
            blocks.append(block)
    return tuple(blocks)


def blocks_to_storage(blocks: Sequence[TurnBlock]) -> list[dict[str, Any]]:
    """The JSON-ready shape stored on the tutor message; round-trips with `blocks_from_storage`."""
    return [block.storage() for block in blocks]


def grade_drill(block: DrillBlock, answer: str) -> DrillAnswer:
    """Grade one drill with the same rules as a lesson exercise (ADR-017).

    The comparison is deterministic on purpose: a drill is checked while the student waits, and
    asking the model would turn a rule into an opinion (and add a provider call to every answer).
    """
    correct = is_correct(answer, block.accepted_answers)
    return DrillAnswer(
        correct=correct,
        expected=None if correct else block.expected,
        explanation=block.explanation,
    )


def _block_from_mapping(item: Any, *, block_id: str) -> TurnBlock | None:
    """One validated block, or `None` when any of its fields cannot be rendered."""
    if not isinstance(item, Mapping):
        return None
    kind = item.get("kind")
    if kind == BlockKind.PHRASE:
        text = _text(item.get("text"), MAX_PHRASE_CHARS)
        if text is None:
            return None
        return PhraseBlock(id=block_id, text=text)
    if kind == BlockKind.DRILL:
        prompt = _text(item.get("prompt"), MAX_DRILL_PROMPT_CHARS)
        answers = _answers(item.get("accepted_answers"))
        if prompt is None or answers is None:
            return None
        # The explanation is optional: a drill without it still teaches, a drill without answers
        # cannot be graded and is therefore not a drill.
        explanation = _text(item.get("explanation"), MAX_DRILL_EXPLANATION_CHARS) or ""
        return DrillBlock(
            id=block_id,
            prompt=prompt,
            accepted_answers=answers,
            explanation=explanation,
        )
    return None


def _text(value: Any, limit: int) -> str | None:
    """A non-empty, trimmed string within the contract limit, or `None`."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > limit:
        return None
    return text


def _answers(value: Any) -> tuple[str, ...] | None:
    """One to five usable answers, in the order the model wrote them."""
    if not isinstance(value, list) or not value:
        return None
    answers: list[str] = []
    for item in value:
        text = _text(item, MAX_DRILL_ANSWER_CHARS)
        if text is None:
            return None
        if text not in answers:
            answers.append(text)
        if len(answers) == MAX_DRILL_ANSWERS:
            break
    return tuple(answers) if answers else None
