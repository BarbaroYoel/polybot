"""`/conversations` against the contract (docs/api-contract.md §2-§4, S6-S8)."""

from fastapi.testclient import TestClient

from app.adapters.db.seed import (
    CONVERSATION_EN_ROUTINE,
    CONVERSATION_FR_CAFE,
    LANGUAGE_FRANCES,
    LANGUAGE_INGLES,
)


def test_history_lists_only_the_requested_language(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/conversations", params={"language_id": LANGUAGE_INGLES})

    assert response.status_code == 200
    page = response.json()
    assert [row["title"] for row in page["items"]] == ["Rutina diaria"]
    assert page["next_cursor"] is None
    assert page["items"][0]["message_count"] == 3
    assert page["items"][0]["last_message_at"].endswith("Z")


def test_history_pages_with_an_opaque_cursor(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/conversations", json={"language_id": LANGUAGE_FRANCES, "title": "En el mercado"}
    )
    assert created.status_code == 201

    first = api_client.get(
        "/api/v1/conversations", params={"language_id": LANGUAGE_FRANCES, "limit": 1}
    ).json()
    assert len(first["items"]) == 1
    assert first["next_cursor"]

    second = api_client.get(
        "/api/v1/conversations",
        params={"language_id": LANGUAGE_FRANCES, "limit": 1, "cursor": first["next_cursor"]},
    ).json()
    assert len(second["items"]) == 1
    assert second["items"][0]["id"] != first["items"][0]["id"]
    assert second["next_cursor"] is None


def test_an_invalid_cursor_is_a_client_error(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/conversations", params={"language_id": LANGUAGE_FRANCES, "cursor": "made-up"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_an_unknown_language_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/conversations", params={"language_id": "missing"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "language_not_found"


def test_creating_a_conversation_uses_a_default_title(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/conversations", json={"language_id": LANGUAGE_FRANCES})

    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Nueva conversación"
    assert created["mode"] == "free"
    assert created["message_count"] == 0
    assert created["last_message_at"] is None


def test_creating_a_conversation_for_an_unknown_language_returns_404(
    api_client: TestClient,
) -> None:
    response = api_client.post("/api/v1/conversations", json={"language_id": "missing"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "language_not_found"


def test_detail_returns_the_conversation_with_paged_messages(api_client: TestClient) -> None:
    first = api_client.get(
        f"/api/v1/conversations/{CONVERSATION_FR_CAFE}", params={"messages_limit": 2}
    )

    assert first.status_code == 200
    detail = first.json()
    assert detail["id"] == CONVERSATION_FR_CAFE
    assert detail["message_count"] == 4
    assert len(detail["messages"]["items"]) == 2
    assert detail["messages"]["items"][0]["author"] == "tutor"
    assert detail["messages"]["next_cursor"]

    second = api_client.get(
        f"/api/v1/conversations/{CONVERSATION_FR_CAFE}",
        params={"messages_limit": 2, "messages_cursor": detail["messages"]["next_cursor"]},
    ).json()
    assert len(second["messages"]["items"]) == 2
    assert second["messages"]["next_cursor"] is None
    assert second["messages"]["items"][-1]["translation"] == "¡Buenos días! ¿Qué le gustaría tomar?"


def test_a_conversation_of_another_language_is_not_reachable(api_client: TestClient) -> None:
    response = api_client.get(
        f"/api/v1/conversations/{CONVERSATION_FR_CAFE}", params={"language_id": LANGUAGE_INGLES}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_an_unknown_conversation_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/conversations/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_patch_renames_the_conversation(api_client: TestClient) -> None:
    response = api_client.patch(
        f"/api/v1/conversations/{CONVERSATION_EN_ROUTINE}", json={"title": "Mi rutina"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Mi rutina"


def test_delete_removes_the_conversation_and_its_messages(api_client: TestClient) -> None:
    assert api_client.delete(f"/api/v1/conversations/{CONVERSATION_EN_ROUTINE}").status_code == 204

    assert api_client.get(f"/api/v1/conversations/{CONVERSATION_EN_ROUTINE}").status_code == 404
    history = api_client.get(
        "/api/v1/conversations", params={"language_id": LANGUAGE_INGLES}
    ).json()
    assert history["items"] == []
