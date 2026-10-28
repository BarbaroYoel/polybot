"""The practice blocks of a turn over HTTP (ADR-020).

What a client can observe, and what it must never observe: the `blocks` event arrives after
`message_end` with the tutor message id, the detail returns the blocks so they survive a reload,
the accepted answers and the explanation never travel before the answer, and the drill is graded by
the domain, not by the model.
"""

import json

from fastapi.testclient import TestClient

from app.adapters.db.seed import CONVERSATION_EN_ROUTINE, CONVERSATION_FR_CAFE
from app.domain.blocks import build_turn_blocks
from app.domain.errors import LlmUnavailable
from app.ports.llm import CorrectionDraft, TurnFeedback, VocabularyDraft
from tests.fakes.llm import FakeLlm

FRENCH_TURN = "Je voudrais un café sil vous plait"
FRENCH_REPLY = ["Bonjour", " !"]

PHRASE = "Je voudrais un café, s'il vous plaît."
DRILL_PROMPT = "Pedí un café con leche."
DRILL_ANSWERS = ["Je voudrais un café au lait", "un café au lait"]
DRILL_EXPLANATION = "«Au lait» es con leche."

BLOCKS = build_turn_blocks(
    [
        {"kind": "phrase", "text": PHRASE},
        {
            "kind": "drill",
            "prompt": DRILL_PROMPT,
            "accepted_answers": DRILL_ANSWERS,
            "explanation": DRILL_EXPLANATION,
        },
    ]
)
FEEDBACK = TurnFeedback(blocks=BLOCKS)

EXPECTED_BLOCKS = [
    {"id": "b1", "kind": "phrase", "text": PHRASE},
    {"id": "b2", "kind": "drill", "prompt": DRILL_PROMPT},
]

Event = tuple[str, dict]


def send_user_message(api_client: TestClient, conversation_id: str, content: str) -> dict:
    response = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": content}
    )
    assert response.status_code == 201, response.text
    return response.json()


def read_turn(api_client: TestClient, conversation_id: str, message_id: str) -> list[Event]:
    response = api_client.get(
        f"/api/v1/conversations/{conversation_id}/stream", params={"message_id": message_id}
    )
    assert response.status_code == 200, response.text
    return parse_sse(response.text)


def parse_sse(body: str) -> list[Event]:
    events: list[Event] = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        assert lines[0].startswith("event: "), block
        assert lines[1].startswith("data: "), block
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1][len("data: ") :])))
    return events


def detail_items(api_client: TestClient, conversation_id: str) -> list[dict]:
    detail = api_client.get(f"/api/v1/conversations/{conversation_id}").json()
    return detail["messages"]["items"]


def answer_url(conversation_id: str, message_id: str, block_id: str) -> str:
    return (
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}/blocks/{block_id}/answers"
    )


def turn_with_blocks(api_client: TestClient, fake_llm: FakeLlm) -> tuple[dict, dict, list[Event]]:
    """One turn that closes with blocks: the user message, the tutor message and its events."""
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = FEEDBACK
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)
    events = read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])
    ended = next(data for name, data in events if name == "message_end")
    return user_message, ended, events


# --- the stream ------------------------------------------------------------------------------


def test_the_blocks_arrive_after_message_end_with_the_tutor_message_id(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    _, tutor, events = turn_with_blocks(api_client, fake_llm)

    names = [name for name, _ in events]
    assert names == ["token", "token", "message_end", "blocks"]

    blocks = events[-1][1]
    # The blocks belong to the reply, not to the message the student wrote.
    assert blocks["message_id"] == tutor["id"]
    assert blocks["items"] == EXPECTED_BLOCKS


def test_the_blocks_come_before_the_feedback_of_the_user_message(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = TurnFeedback(
        corrections=(
            CorrectionDraft(
                original="sil vous plait",
                corrected="s'il vous plaît",
                explanation="La fórmula de cortesía lleva apóstrofo.",
            ),
        ),
        vocabulary=(VocabularyDraft(term="s'il vous plaît", translation="por favor"),),
        blocks=BLOCKS,
    )
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    events = read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    # Contract §3: the reply, its blocks, then the feedback of what the student wrote.
    assert [name for name, _ in events] == [
        "token",
        "token",
        "message_end",
        "blocks",
        "correction",
        "vocabulary",
    ]


def test_the_client_payload_never_carries_the_accepted_answers(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    _, _, events = turn_with_blocks(api_client, fake_llm)

    payload = json.dumps(events[-1][1], ensure_ascii=False)

    assert "accepted_answers" not in payload
    assert "au lait" not in payload.lower()
    assert DRILL_EXPLANATION not in payload


def test_the_blocks_survive_a_reload_with_the_tutor_message(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    user_message, tutor, _ = turn_with_blocks(api_client, fake_llm)

    items = detail_items(api_client, CONVERSATION_FR_CAFE)
    by_id = {item["id"]: item for item in items}

    assert by_id[tutor["id"]]["blocks"] == EXPECTED_BLOCKS
    # A user message never carries blocks: they are the reply's, not the student's.
    assert by_id[user_message["id"]]["blocks"] == []


def test_a_failed_closing_call_leaves_the_turn_without_blocks(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.summary_failure = LlmUnavailable("sin proveedor")
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    events = read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    assert [name for name, _ in events] == ["token", "token", "message_end"]
    tutors = [item for item in detail_items(api_client, CONVERSATION_FR_CAFE) if item["blocks"]]
    assert tutors == []


# --- answering the drill ---------------------------------------------------------------------


def test_a_correct_answer_is_confirmed_without_revealing_the_alternatives(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    _, tutor, _ = turn_with_blocks(api_client, fake_llm)

    response = api_client.post(
        answer_url(CONVERSATION_FR_CAFE, tutor["id"], "b2"),
        json={"answer": "je voudrais un café au lait"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "correct": True,
        "expected": None,
        "explanation": DRILL_EXPLANATION,
    }
    # The response must not become a way to harvest the second accepted answer.
    assert "un café au lait" not in json.dumps(response.json(), ensure_ascii=False)


def test_a_miss_shows_the_first_accepted_answer(api_client: TestClient, fake_llm: FakeLlm) -> None:
    _, tutor, _ = turn_with_blocks(api_client, fake_llm)

    response = api_client.post(
        answer_url(CONVERSATION_FR_CAFE, tutor["id"], "b2"), json={"answer": "un thé"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["correct"] is False
    assert body["expected"] == DRILL_ANSWERS[0]
    assert body["explanation"] == DRILL_EXPLANATION


def test_answering_twice_grades_again_and_changes_nothing(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    """ADR-020: the drill is stateless, so `/progress` keeps its own signals (ADR-018)."""
    _, tutor, _ = turn_with_blocks(api_client, fake_llm)
    url = answer_url(CONVERSATION_FR_CAFE, tutor["id"], "b2")

    first = api_client.post(url, json={"answer": "un café au lait"})
    second = api_client.post(url, json={"answer": "un café au lait"})

    assert first.status_code == 200 and second.status_code == 200
    assert first.json() == second.json()
    blocks = [item for item in detail_items(api_client, CONVERSATION_FR_CAFE) if item["blocks"]]
    assert blocks[0]["blocks"] == EXPECTED_BLOCKS


def test_a_phrase_is_not_an_exercise(api_client: TestClient, fake_llm: FakeLlm) -> None:
    _, tutor, _ = turn_with_blocks(api_client, fake_llm)

    response = api_client.post(
        answer_url(CONVERSATION_FR_CAFE, tutor["id"], "b1"), json={"answer": "algo"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "block_not_answerable"


def test_a_missing_block_is_not_found(api_client: TestClient, fake_llm: FakeLlm) -> None:
    _, tutor, _ = turn_with_blocks(api_client, fake_llm)

    response = api_client.post(
        answer_url(CONVERSATION_FR_CAFE, tutor["id"], "b9"), json={"answer": "algo"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "block_not_found"


def test_a_block_of_another_conversation_is_not_reachable(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    _, tutor, _ = turn_with_blocks(api_client, fake_llm)

    response = api_client.post(
        answer_url(CONVERSATION_EN_ROUTINE, tutor["id"], "b2"), json={"answer": "algo"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "message_not_found"


def test_an_empty_answer_is_a_validation_error(api_client: TestClient, fake_llm: FakeLlm) -> None:
    _, tutor, _ = turn_with_blocks(api_client, fake_llm)

    response = api_client.post(
        answer_url(CONVERSATION_FR_CAFE, tutor["id"], "b2"), json={"answer": "   "}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
