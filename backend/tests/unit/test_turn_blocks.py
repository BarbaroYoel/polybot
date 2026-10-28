"""The typed practice blocks of a turn (ADR-020).

These tests pin the rules the model cannot break: a flat, bounded list; the answers of a drill
never leaving the server before the student answers; and a deterministic grade that keeps accents
(ADR-017's comparison) while ignoring typing.
"""

import json

from app.domain.blocks import (
    MAX_DRILL_ANSWER_CHARS,
    MAX_DRILL_ANSWERS,
    MAX_DRILL_EXPLANATION_CHARS,
    MAX_DRILL_PROMPT_CHARS,
    MAX_PHRASE_CHARS,
    DrillBlock,
    blocks_from_storage,
    blocks_to_storage,
    build_turn_blocks,
    grade_drill,
)


def drill(**overrides: object) -> dict:
    payload = {
        "kind": "drill",
        "prompt": "Pedí un café con leche.",
        "accepted_answers": ["Je voudrais un café au lait"],
        "explanation": "«Au lait» es con leche.",
    }
    payload.update(overrides)
    return payload


def phrase(**overrides: object) -> dict:
    payload = {"kind": "phrase", "text": "Je voudrais un café, s'il vous plaît."}
    payload.update(overrides)
    return payload


# --- what survives ---------------------------------------------------------------------------


def test_blocks_keep_their_order_and_get_positional_ids() -> None:
    blocks = build_turn_blocks([phrase(), drill()])

    assert [block.id for block in blocks] == ["b1", "b2"]
    assert [block.kind.value for block in blocks] == ["phrase", "drill"]


def test_an_unknown_kind_is_dropped_instead_of_rendered() -> None:
    blocks = build_turn_blocks([{"kind": "chart", "data": [1, 2, 3]}, phrase()])

    assert len(blocks) == 1
    assert blocks[0].kind.value == "phrase"


def test_at_most_two_blocks_survive() -> None:
    blocks = build_turn_blocks([phrase(), phrase(), phrase()])

    assert len(blocks) == 2


def test_only_one_interactive_block_survives() -> None:
    blocks = build_turn_blocks([drill(), drill(), phrase()])

    assert len(blocks) == 2
    assert [block.kind.value for block in blocks] == ["drill", "phrase"]


def test_a_drill_without_usable_answers_is_not_a_drill() -> None:
    assert build_turn_blocks([drill(accepted_answers=[])]) == ()
    assert build_turn_blocks([drill(accepted_answers=["  "])]) == ()
    assert build_turn_blocks([drill(accepted_answers="una sola")]) == ()
    assert build_turn_blocks([drill(accepted_answers=["ok", 42])]) == ()


def test_overlong_text_is_dropped_not_truncated() -> None:
    assert build_turn_blocks([phrase(text="a" * (MAX_PHRASE_CHARS + 1))]) == ()
    assert build_turn_blocks([drill(prompt="a" * (MAX_DRILL_PROMPT_CHARS + 1))]) == ()


def test_a_missing_explanation_still_leaves_a_gradable_drill() -> None:
    blocks = build_turn_blocks([drill(explanation=None)])

    assert isinstance(blocks[0], DrillBlock)
    assert blocks[0].explanation == ""


def test_answers_are_trimmed_deduplicated_and_capped() -> None:
    blocks = build_turn_blocks(
        [drill(accepted_answers=["  un café  ", "un café", *(f"variante {n}" for n in range(9))])]
    )

    assert isinstance(blocks[0], DrillBlock)
    assert blocks[0].accepted_answers[0] == "un café"
    assert blocks[0].accepted_answers.count("un café") == 1
    assert len(blocks[0].accepted_answers) == MAX_DRILL_ANSWERS


# --- what the client sees --------------------------------------------------------------------


def test_the_public_view_hides_the_answers_and_the_explanation() -> None:
    blocks = build_turn_blocks([drill()])
    block = blocks[0]
    assert isinstance(block, DrillBlock)

    public = block.public()

    assert public == {"id": "b1", "kind": "drill", "prompt": "Pedí un café con leche."}
    assert "accepted_answers" not in json.dumps(public)
    assert "Au lait" not in json.dumps(public)


def test_storage_round_trips_the_private_fields() -> None:
    blocks = build_turn_blocks([phrase(), drill()])

    stored = blocks_to_storage(blocks)
    rebuilt = blocks_from_storage(stored)

    assert rebuilt == blocks
    assert isinstance(rebuilt[1], DrillBlock)
    assert rebuilt[1].accepted_answers == ("Je voudrais un café au lait",)


def test_storage_skips_what_this_version_cannot_read() -> None:
    rebuilt = blocks_from_storage(
        [
            {"id": "b1", "kind": "chart", "series": []},
            {"kind": "phrase", "text": "sin id"},
            {"id": "b3", "kind": "phrase", "text": "  "},
            {"id": "b4", "kind": "phrase", "text": "Bonjour !"},
            "no soy un objeto",
        ]
    )

    assert [block.id for block in rebuilt] == ["b4"]


def test_a_maximum_turn_stays_under_four_kilobytes() -> None:
    """The per-field caps bound the payload, so no runtime byte check is needed (contract §5)."""
    blocks = build_turn_blocks(
        [
            phrase(text="a" * MAX_PHRASE_CHARS),
            drill(
                prompt="b" * MAX_DRILL_PROMPT_CHARS,
                accepted_answers=["c" * MAX_DRILL_ANSWER_CHARS] * MAX_DRILL_ANSWERS,
                explanation="d" * MAX_DRILL_EXPLANATION_CHARS,
            ),
        ]
    )

    assert len(blocks) == 2
    assert blocks[1].accepted_answers[0] == "c" * MAX_DRILL_ANSWER_CHARS
    size = len(json.dumps(blocks_to_storage(blocks), ensure_ascii=False).encode("utf-8"))
    assert size < 4_096


# --- the grade -------------------------------------------------------------------------------


def test_a_correct_answer_does_not_reveal_the_accepted_ones() -> None:
    block = build_turn_blocks([drill()])[0]
    assert isinstance(block, DrillBlock)

    result = grade_drill(block, "je voudrais un café au lait.")

    assert result.correct is True
    assert result.expected is None
    assert result.explanation == "«Au lait» es con leche."


def test_a_miss_reveals_the_first_accepted_answer() -> None:
    block = build_turn_blocks([drill(accepted_answers=["un café", "un café au lait"])])[0]
    assert isinstance(block, DrillBlock)

    result = grade_drill(block, "un thé")

    assert result.correct is False
    assert result.expected == "un café"


def test_the_grade_keeps_accents_but_ignores_typing() -> None:
    block = build_turn_blocks([drill(accepted_answers=["un café au lait"])])[0]
    assert isinstance(block, DrillBlock)

    # Punctuation, case and spacing are typing; the accent is the word (ADR-017).
    assert grade_drill(block, "  Un cafe au lait ").correct is False
    assert grade_drill(block, "  UN CAFÉ, AU LAIT. ").correct is True
