"""The closing-turn contract over HTTP: `correction`/`vocabulary` events and stored feedback.

F3 S7 asks for corrections and suggested vocabulary when the turn closes, persisted (not just
streamed) so they survive a reload. These tests pin the four things a client can observe: the
events arrive after `message_end` and carry the *user* message id, the conversation detail returns
them with the user message, a failing closing call leaves the chat intact (`message_end`, `sent`,
no feedback events), and the vocabulary is stored under the conversation's language (S8).
"""

import asyncio
import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.conversations import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.adapters.db.languages import SqlAlchemyLanguageRepository
from app.adapters.db.models import VocabularyItemRow
from app.adapters.db.seed import (
    CONVERSATION_EN_ROUTINE,
    CONVERSATION_FR_CAFE,
    LANGUAGE_FRANCES,
)
from app.application.tutor import TutorService
from app.domain.errors import LlmUnavailable
from app.ports.llm import CorrectionDraft, TurnFeedback, VocabularyDraft
from tests.fakes.llm import FakeLlm

FRENCH_TURN = "Je voudrais un café sil vous plait"
FRENCH_REPLY = ["Bonjour", " !"]

FEEDBACK = TurnFeedback(
    corrections=(
        CorrectionDraft(
            original="Je voudrais un café sil vous plait",
            corrected="Je voudrais un café, s'il vous plaît.",
            explanation="Separá la petición con una coma y escribí «s'il vous plaît».",
        ),
    ),
    vocabulary=(
        VocabularyDraft(
            term="s'il vous plaît",
            translation="por favor",
            note="Fórmula de cortesía; se usa al pedir algo.",
        ),
    ),
)

EXPECTED_CORRECTIONS = [
    {
        "original": "Je voudrais un café sil vous plait",
        "corrected": "Je voudrais un café, s'il vous plaît.",
        "explanation": "Separá la petición con una coma y escribí «s'il vous plaît».",
    }
]
EXPECTED_VOCABULARY = [
    {
        "term": "s'il vous plaît",
        "translation": "por favor",
        "note": "Fórmula de cortesía; se usa al pedir algo.",
    }
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


def test_the_stream_closes_with_corrections_and_vocabulary_for_the_user_message(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = FEEDBACK
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    events = read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    names = [name for name, _ in events]
    # Order is the contract: the text, the authoritative message, then the closing events.
    assert names == ["token", "token", "message_end", "correction", "vocabulary"]

    correction = events[-2][1]
    assert correction == {"message_id": user_message["id"], "items": EXPECTED_CORRECTIONS}
    vocabulary = events[-1][1]
    assert vocabulary == {"message_id": user_message["id"], "items": EXPECTED_VOCABULARY}
    # The tutor message is not the subject of the feedback: the events point at the user message.
    assert correction["message_id"] != events[2][1]["id"]

    # The closing events announce rows that already exist.
    stored = [
        item
        for item in detail_items(api_client, CONVERSATION_FR_CAFE)
        if item["id"] == user_message["id"]
    ]
    assert len(stored) == 1
    assert stored[0]["feedback"] == {
        "corrections": EXPECTED_CORRECTIONS,
        "vocabulary": EXPECTED_VOCABULARY,
    }


def test_the_detail_returns_the_feedback_so_it_survives_a_reload(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = FEEDBACK
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)
    read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    items = detail_items(api_client, CONVERSATION_FR_CAFE)

    with_feedback = [item["id"] for item in items if item["feedback"] is not None]
    assert with_feedback == [user_message["id"]]
    # Tutor messages never carry feedback, and user messages without a closing turn keep `null`.
    assert all(item["feedback"] is None for item in items if item["author"] == "tutor")
    assert any(item["author"] == "user" and item["feedback"] is None for item in items)


def test_a_failing_closing_call_leaves_the_turn_sent_and_silent(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.summary_failure = LlmUnavailable("the provider died")
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    events = read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    # The chat does not break: `message_end` already left, nothing else does.
    assert [name for name, _ in events] == ["token", "token", "message_end"]
    assert events[-1][1]["status"] == "sent"
    assert events[-1][1]["content"] == "Bonjour !"

    items = detail_items(api_client, CONVERSATION_FR_CAFE)
    user = next(item for item in items if item["id"] == user_message["id"])
    assert user["feedback"] is None
    tutor = next(item for item in items if item["id"] == events[-1][1]["id"])
    assert tutor["status"] == "sent"


def test_the_vocabulary_is_stored_with_the_conversation_language(
    api_client: TestClient,
    fake_llm: FakeLlm,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fake_llm.feedback = FEEDBACK
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)
    read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    async def stored_rows() -> list[tuple[str, str, str]]:
        async with session_factory() as session:
            rows = await session.scalars(select(VocabularyItemRow))
            return [(row.term, row.language_id, row.translation) for row in rows]

    rows = asyncio.run(stored_rows())

    # The turn follows the conversation's language, never the globally active one (S8): English is
    # the active language, and this vocabulary belongs to French.
    assert rows == [("s'il vous plaît", LANGUAGE_FRANCES, "por favor")]


def test_the_closing_call_receives_the_reply_and_the_language_context(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = FEEDBACK
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    assert len(fake_llm.summaries) == 1
    turn, reply = fake_llm.summaries[0]
    assert reply == "Bonjour !"
    assert turn is fake_llm.turn, "the closing call reuses the turn the reply answered"
    assert turn.context.language_name == "Francés"
    assert turn.context.language_code == "fr"
    assert turn.context.explanation_language == "es"
    assert turn.user_message == FRENCH_TURN


def test_a_turn_with_nothing_to_report_emits_no_closing_events(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    # An empty closing answer (all correct, no new vocabulary) is not an error.
    fake_llm.feedback = TurnFeedback(corrections=(), vocabulary=())
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    events = read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    assert [name for name, _ in events] == ["token", "token", "message_end"]
    items = detail_items(api_client, CONVERSATION_FR_CAFE)
    user = next(item for item in items if item["id"] == user_message["id"])
    assert user["feedback"] is None


def test_a_retried_turn_replaces_its_feedback_instead_of_duplicating_it(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = FEEDBACK
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])
    read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    items = detail_items(api_client, CONVERSATION_FR_CAFE)
    with_feedback = [item for item in items if item["feedback"] is not None]
    assert len(with_feedback) == 1
    assert with_feedback[0]["feedback"] == {
        "corrections": EXPECTED_CORRECTIONS,
        "vocabulary": EXPECTED_VOCABULARY,
    }


def test_the_feedback_of_another_language_never_leaks_into_this_conversation(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = FEEDBACK
    french_turn = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)
    read_turn(api_client, CONVERSATION_FR_CAFE, french_turn["id"])

    fake_llm.deltas = ["Nice", "!"]
    fake_llm.feedback = TurnFeedback(corrections=(), vocabulary=())
    english_turn = send_user_message(api_client, CONVERSATION_EN_ROUTINE, "I went for a walk.")
    read_turn(api_client, CONVERSATION_EN_ROUTINE, english_turn["id"])

    english_items = detail_items(api_client, CONVERSATION_EN_ROUTINE)
    assert all(item["feedback"] is None for item in english_items)
    french_items = detail_items(api_client, CONVERSATION_FR_CAFE)
    assert [item["id"] for item in french_items if item["feedback"] is not None] == [
        french_turn["id"]
    ]


class UnwritableFeedback:
    """A message repository whose closing write fails, to prove the turn survives it."""

    def __init__(self, inner: SqlAlchemyMessageRepository) -> None:
        self._inner = inner

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    async def save_feedback(self, *args, **kwargs):
        raise RuntimeError("disk on fire")


def test_a_storage_failure_of_the_feedback_does_not_break_the_turn(
    api_client: TestClient, fake_llm: FakeLlm, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    fake_llm.feedback = FEEDBACK
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    async def scenario() -> list[object]:
        async with session_factory() as session:
            service = TutorService(
                conversations=SqlAlchemyConversationRepository(session),
                messages=UnwritableFeedback(SqlAlchemyMessageRepository(session)),
                languages=SqlAlchemyLanguageRepository(session),
                llm=fake_llm,
                commit=session.commit,
                rollback=session.rollback,
            )
            state = await service.begin_turn(CONVERSATION_FR_CAFE, user_message["id"])
            return [event async for event in service.stream_turn(state)]

    events = asyncio.run(scenario())

    names = [type(event).__name__ for event in events]
    # The turn still completes: the reply is stored as `sent`, only the feedback is skipped.
    assert names[-1] == "TurnCompleted"
    assert "TurnFeedbackReady" not in names

    items = detail_items(api_client, CONVERSATION_FR_CAFE)
    tutor = [item for item in items if item["author"] == "tutor"][-1]
    assert tutor["status"] == "sent"
    assert tutor["content"] == "Bonjour !"
    user = next(item for item in items if item["id"] == user_message["id"])
    assert user["feedback"] is None
