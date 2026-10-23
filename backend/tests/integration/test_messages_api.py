"""The user turn over HTTP: `POST /conversations/{id}/messages` (F3 S4, S8).

The contract (§3) already lists this endpoint; §1 asks for `Idempotency-Key` whenever a retry
would duplicate a turn, and architecture §5 requires it. These tests pin the observable behavior:
the message is persisted, the conversation activity moves, and a retried send does not create a
second turn.
"""

from fastapi.testclient import TestClient

from app.adapters.db.seed import CONVERSATION_EN_ROUTINE, CONVERSATION_FR_CAFE


def messages_url(conversation_id: str) -> str:
    return f"/api/v1/conversations/{conversation_id}/messages"


def test_a_sent_message_is_persisted_and_appears_in_the_thread(
    api_client: TestClient,
) -> None:
    before = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()

    response = api_client.post(
        messages_url(CONVERSATION_FR_CAFE), json={"content": "Bonjour, je voudrais un café."}
    )

    assert response.status_code == 201
    message = response.json()
    assert message["author"] == "user"
    assert message["status"] == "sent"
    assert message["content"] == "Bonjour, je voudrais un café."
    assert message["conversation_id"] == CONVERSATION_FR_CAFE

    after = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()
    assert after["message_count"] == before["message_count"] + 1
    assert after["messages"]["items"][-1]["id"] == message["id"]
    assert after["last_message_at"] == message["created_at"]


def test_the_same_idempotency_key_returns_the_same_message_without_duplicating_it(
    api_client: TestClient,
) -> None:
    first = api_client.post(
        messages_url(CONVERSATION_FR_CAFE),
        json={"content": "Je m'appelle Ana."},
        headers={"Idempotency-Key": "turn-1"},
    )
    retry = api_client.post(
        messages_url(CONVERSATION_FR_CAFE),
        json={"content": "Je m'appelle Ana."},
        headers={"Idempotency-Key": "turn-1"},
    )

    assert first.status_code == retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]

    detail = api_client.get(f"/api/v1/conversations/{CONVERSATION_FR_CAFE}").json()
    matching = [
        item for item in detail["messages"]["items"] if item["content"] == "Je m'appelle Ana."
    ]
    assert len(matching) == 1


def test_the_same_key_in_another_conversation_is_a_different_turn(
    api_client: TestClient,
) -> None:
    french = api_client.post(
        messages_url(CONVERSATION_FR_CAFE),
        json={"content": "Bonjour"},
        headers={"Idempotency-Key": "turn-1"},
    ).json()
    english = api_client.post(
        messages_url(CONVERSATION_EN_ROUTINE),
        json={"content": "Hello"},
        headers={"Idempotency-Key": "turn-1"},
    ).json()

    assert french["id"] != english["id"]
    assert english["conversation_id"] == CONVERSATION_EN_ROUTINE


def test_two_sends_without_a_key_are_two_turns(api_client: TestClient) -> None:
    first = api_client.post(messages_url(CONVERSATION_FR_CAFE), json={"content": "Encore"}).json()
    second = api_client.post(messages_url(CONVERSATION_FR_CAFE), json={"content": "Encore"}).json()

    assert first["id"] != second["id"]


def test_sending_to_a_missing_conversation_is_a_404(api_client: TestClient) -> None:
    response = api_client.post(messages_url("missing"), json={"content": "Bonjour"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_empty_content_uses_the_error_envelope(api_client: TestClient) -> None:
    response = api_client.post(messages_url(CONVERSATION_FR_CAFE), json={"content": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_content_over_the_limit_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(messages_url(CONVERSATION_FR_CAFE), json={"content": "a" * 4001})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
