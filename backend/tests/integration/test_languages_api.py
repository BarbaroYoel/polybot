"""`/languages` against the contract (docs/api-contract.md §2-§4, S4/S6)."""

from fastapi.testclient import TestClient

from app.adapters.db.seed import LANGUAGE_ALEMAN, LANGUAGE_FRANCES, LANGUAGE_INGLES


def test_list_returns_the_non_archived_languages(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/languages")

    assert response.status_code == 200
    languages = response.json()
    assert [language["code"] for language in languages] == ["en", "fr", "de"]
    english = languages[0]
    assert english["level"] == "B1"
    assert english["is_active"] is True
    assert english["archived"] is False
    assert english["weekly_goal"] == {"conversations": 7, "minutes": 90}
    assert english["created_at"].endswith("Z")


def test_creating_a_language_starts_inactive_and_uses_the_explanation_language(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/v1/languages", json={"code": "IT", "name": "Italiano", "level": "A2"}
    )

    assert response.status_code == 201
    created = response.json()
    assert created["code"] == "it", "codes are stored normalized"
    assert created["is_active"] is False
    assert created["explanation_language"] == "es"

    listed = api_client.get("/api/v1/languages").json()
    assert "it" in [language["code"] for language in listed]


def test_a_duplicate_code_returns_a_conflict_envelope(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/languages", json={"code": "fr", "name": "Francés", "level": "A1"}
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "language_already_exists"
    assert error["message"]
    assert error["request_id"] == response.headers["x-request-id"]


def test_activating_a_language_deactivates_the_previous_one(api_client: TestClient) -> None:
    response = api_client.patch(f"/api/v1/languages/{LANGUAGE_FRANCES}", json={"is_active": True})

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    active = [row["code"] for row in api_client.get("/api/v1/languages").json() if row["is_active"]]
    assert active == ["fr"]


def test_patching_the_level_and_the_goal_keeps_the_rest(api_client: TestClient) -> None:
    response = api_client.patch(
        f"/api/v1/languages/{LANGUAGE_INGLES}",
        json={"level": "B2", "weekly_goal": {"conversations": 5, "minutes": 60}},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["level"] == "B2"
    assert updated["weekly_goal"] == {"conversations": 5, "minutes": 60}
    assert updated["is_active"] is True


def test_patching_an_unknown_language_returns_404(api_client: TestClient) -> None:
    response = api_client.patch("/api/v1/languages/not-a-language", json={"is_active": True})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "language_not_found"


def test_deleting_archives_softly_and_hides_the_language(api_client: TestClient) -> None:
    response = api_client.delete(f"/api/v1/languages/{LANGUAGE_ALEMAN}")

    assert response.status_code == 204
    listed = [row["code"] for row in api_client.get("/api/v1/languages").json()]
    assert listed == ["en", "fr"]


def test_the_active_language_cannot_be_archived(api_client: TestClient) -> None:
    response = api_client.delete(f"/api/v1/languages/{LANGUAGE_INGLES}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "active_language_cannot_be_archived"
    assert "en" in [row["code"] for row in api_client.get("/api/v1/languages").json()]


def test_an_unknown_level_is_a_validation_error(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/languages", json={"code": "it", "name": "Italiano", "level": "Z9"}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["fields"][0]["location"].endswith("level")
