"""The tutor turn over SSE: `GET /conversations/{id}/stream?message_id=` (F3 S5, S6, S8).

The contract (§3) lists the events; these tests pin the observable behavior: the deltas reach the
client as `token`, the stored message arrives as `message_end` *after* it is persisted as `sent`,
the turn uses the conversation's language and its previous messages, and a failure (provider down
or the client walking away) leaves the stored message in `error` with whatever text was emitted.
"""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.conversations import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.adapters.db.languages import SqlAlchemyLanguageRepository
from app.adapters.db.seed import CONVERSATION_EN_ROUTINE, CONVERSATION_FR_CAFE
from app.application.tutor import TurnToken, TutorService
from app.domain.entities import (
    CefrLevel,
    Message,
    MessageAuthor,
    MessageStatus,
    NewMessage,
)
from app.domain.errors import LlmUnavailable
from tests.fakes.llm import FakeLlm

FRENCH_TURN = "Je voudrais un café, s'il vous plaît."
ENGLISH_TURN = "I went for a long walk after lunch."
FRENCH_REPLY = ["Bonjour", " !", " Bienvenue."]

Event = tuple[str, dict]


def messages_url(conversation_id: str) -> str:
    return f"/api/v1/conversations/{conversation_id}/messages"


def stream_path(conversation_id: str) -> str:
    return f"/api/v1/conversations/{conversation_id}/stream"


def send_user_message(api_client: TestClient, conversation_id: str, content: str) -> dict:
    response = api_client.post(messages_url(conversation_id), json={"content": content})
    assert response.status_code == 201, response.text
    return response.json()


def stream_turn(api_client: TestClient, conversation_id: str, message_id: str):
    return api_client.get(stream_path(conversation_id), params={"message_id": message_id})


def read_turn(api_client: TestClient, conversation_id: str, message_id: str) -> list[Event]:
    response = stream_turn(api_client, conversation_id, message_id)
    assert response.status_code == 200, response.text
    return parse_sse(response.text)


def parse_sse(body: str) -> list[Event]:
    """Split the stream into `(event, data)` pairs; each block ends with a blank line."""
    events: list[Event] = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        assert lines[0].startswith("event: "), block
        assert lines[1].startswith("data: "), block
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1][len("data: ") :])))
    return events


def stored_tutor_message(api_client: TestClient, conversation_id: str) -> dict:
    detail = api_client.get(f"/api/v1/conversations/{conversation_id}").json()
    return [item for item in detail["messages"]["items"] if item["author"] == "tutor"][-1]


def make_service(session: AsyncSession, llm: FakeLlm) -> TutorService:
    """The use case wired like the app does, for the parts a stream cannot assert over HTTP."""
    return TutorService(
        conversations=SqlAlchemyConversationRepository(session),
        messages=SqlAlchemyMessageRepository(session),
        languages=SqlAlchemyLanguageRepository(session),
        llm=llm,
        commit=session.commit,
    )


def test_the_stream_emits_tokens_and_stores_the_tutor_message(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = ["Bonjour", " !"]
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    events = read_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    assert [name for name, _ in events] == ["token", "token", "message_end"]
    tutor_message_id = events[0][1]["message_id"]
    assert {data["message_id"] for name, data in events if name == "token"} == {tutor_message_id}
    assert "".join(data["delta"] for name, data in events if name == "token") == "Bonjour !"

    ended = events[-1][1]
    assert ended == {
        "id": tutor_message_id,
        "conversation_id": CONVERSATION_FR_CAFE,
        "author": "tutor",
        "content": "Bonjour !",
        "translation": None,
        "status": "sent",
        "created_at": ended["created_at"],
    }
    assert ended["created_at"].endswith("Z")

    # The event is not the source of truth: the row survives the stream already persisted.
    detail = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()
    tutors = [item for item in detail["messages"]["items"] if item["id"] == tutor_message_id]
    assert len(tutors) == 1
    assert tutors[0]["status"] == "sent"
    assert tutors[0]["content"] == "Bonjour !"
    assert detail["messages"]["items"][-1]["id"] == tutor_message_id
    assert detail["message_count"] == 6


def test_the_turn_uses_the_conversation_language_and_history(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    french_turn = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)
    read_turn(api_client, CONVERSATION_FR_CAFE, french_turn["id"])

    french = fake_llm.turn
    assert french is not None
    assert french.context.language_name == "Francés"
    assert french.context.language_code == "fr"
    assert french.context.level == CefrLevel.A1
    assert french.context.explanation_language == "es"
    assert french.user_message == FRENCH_TURN
    history = [message.content for message in french.history]
    # Oldest first, everything before the new turn, and the new turn only once (as user_message).
    assert history[0] == (
        "¡Hola! Soy tu tutor de idiomas. Podemos conversar, practicar vocabulario, "
        "corregir tus frases o simular situaciones de la vida real.\n\n"
        "¿Qué te gustaría hacer hoy?"
    )
    assert history[-1] == "Bonjour ! Qu'est-ce que vous aimeriez prendre ?"
    assert FRENCH_TURN not in history
    assert all(message.author.value in {"tutor", "user"} for message in french.history)

    # The active language is English, and this conversation is French: the turn follows the
    # conversation, never the global active language (S8).
    english_turn = send_user_message(api_client, CONVERSATION_EN_ROUTINE, ENGLISH_TURN)
    read_turn(api_client, CONVERSATION_EN_ROUTINE, english_turn["id"])

    english = fake_llm.turn
    assert english is not None
    assert english.context.language_name == "Inglés"
    assert english.context.language_code == "en"
    assert english.context.level == CefrLevel.B1
    assert english.user_message == ENGLISH_TURN
    english_history = [message.content for message in english.history]
    assert "I woke up early and went for a run before work." in english_history
    assert ENGLISH_TURN not in english_history
    assert FRENCH_TURN not in english_history


def test_streaming_a_missing_conversation_is_a_404(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)
    before = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()

    response = api_client.get(
        stream_path("does-not-exist"), params={"message_id": user_message["id"]}
    )

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "conversation_not_found"
    assert error["message"]
    assert fake_llm.calls == 0
    after = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()
    assert after["message_count"] == before["message_count"]


def test_streaming_a_message_from_another_conversation_is_a_404(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    foreign = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)
    before = api_client.get(f"/api/v1/conversations/{CONVERSATION_EN_ROUTINE}").json()

    response = api_client.get(
        stream_path(CONVERSATION_EN_ROUTINE), params={"message_id": foreign["id"]}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "message_not_found"
    assert fake_llm.calls == 0
    after = api_client.get(f"/api/v1/conversations/{CONVERSATION_EN_ROUTINE}").json()
    assert after["message_count"] == before["message_count"]


def test_streaming_a_tutor_message_is_rejected(api_client: TestClient, fake_llm: FakeLlm) -> None:
    detail = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()
    tutor_message = next(item for item in detail["messages"]["items"] if item["author"] == "tutor")

    response = api_client.get(
        stream_path(CONVERSATION_FR_CAFE), params={"message_id": tutor_message["id"]}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_turn_message"
    assert error["message"] == "Solo se puede transmitir un mensaje del usuario."
    assert fake_llm.calls == 0
    after = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()
    assert after["message_count"] == detail["message_count"]


def test_a_provider_failure_emits_the_envelope_and_marks_the_message_error(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.deltas = ["Bonjour"]
    fake_llm.failure = LlmUnavailable("the provider died")
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    response = stream_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])
    assert response.status_code == 200
    events = parse_sse(response.text)

    assert [name for name, _ in events] == ["token", "error"]
    error = events[-1][1]["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == "llm_unavailable"
    # The contract message wins over whatever the provider said.
    assert error["message"] == "El tutor no pudo responder. Vuelve a intentar en unos segundos."
    # The `error` event carries the same request id as the response (contract §4).
    assert error["request_id"] == response.headers["x-request-id"]

    stored = stored_tutor_message(api_client, CONVERSATION_FR_CAFE)
    assert stored["status"] == "error"
    assert stored["content"] == "Bonjour"


def test_abandoning_the_stream_keeps_the_partial_text_and_marks_the_message_error(
    api_client: TestClient,
    fake_llm: FakeLlm,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fake_llm.deltas = FRENCH_REPLY
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    async def abandoned_turn() -> None:
        async with session_factory() as session:
            service = make_service(session, fake_llm)
            state = await service.begin_turn(CONVERSATION_FR_CAFE, user_message["id"])
            stream: AsyncIterator[object] = service.stream_turn(state)
            first = await anext(stream)
            assert isinstance(first, TurnToken)
            assert first.delta == "Bonjour"
            # What the HTTP layer does when the client disconnects mid-turn.
            await stream.aclose()

    asyncio.run(abandoned_turn())

    assert fake_llm.closed, "the provider call must be closed, not left running (S6)"
    stored = stored_tutor_message(api_client, CONVERSATION_FR_CAFE)
    assert stored["status"] == "error"
    assert stored["content"] == "Bonjour"


def test_the_tutor_message_is_already_streaming_before_the_first_token(
    api_client: TestClient, fake_llm: FakeLlm, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    async def begin() -> Message:
        async with session_factory() as session:
            state = await make_service(session, fake_llm).begin_turn(
                CONVERSATION_FR_CAFE, user_message["id"]
            )
            # A different session proves the commit already happened.
            async with session_factory() as reader:
                stored = await SqlAlchemyMessageRepository(reader).get_message(state.message.id)
            assert stored is not None
            return stored

    stored = asyncio.run(begin())

    assert stored.status is MessageStatus.STREAMING
    assert stored.content == ""
    assert stored.author is MessageAuthor.TUTOR
    assert fake_llm.calls == 0, "the provider is not called until the stream is consumed"


def test_the_history_window_is_the_thirty_messages_before_the_turn(
    api_client: TestClient, fake_llm: FakeLlm, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async def scenario() -> list[str]:
        async with session_factory() as session:
            messages = SqlAlchemyMessageRepository(session)
            for index in range(35):
                await messages.add_message(
                    NewMessage(
                        conversation_id=CONVERSATION_FR_CAFE,
                        author=MessageAuthor.USER,
                        content=f"message {index:02d}",
                    )
                )
            latest = await messages.add_message(
                NewMessage(
                    conversation_id=CONVERSATION_FR_CAFE,
                    author=MessageAuthor.USER,
                    content="the new turn",
                )
            )
            await session.commit()

            state = await make_service(session, fake_llm).begin_turn(
                CONVERSATION_FR_CAFE, latest.id
            )
            return [message.content for message in state.turn.history]

    history = asyncio.run(scenario())

    # Only the 30 messages closest to the turn travel, oldest first, and the turn itself once.
    assert len(history) == 30
    assert history[0] == "message 05"
    assert history[-1] == "message 34"
    assert "the new turn" not in history
    assert "" not in history


def test_the_stream_is_text_event_stream(api_client: TestClient, fake_llm: FakeLlm) -> None:
    user_message = send_user_message(api_client, CONVERSATION_FR_CAFE, FRENCH_TURN)

    response = stream_turn(api_client, CONVERSATION_FR_CAFE, user_message["id"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
