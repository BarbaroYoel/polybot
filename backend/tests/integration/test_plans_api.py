"""`/plans` against the contract (F5 S3, S4, S5, S6).

The schedule is derived from the seeded catalog, so these tests never hardcode lesson ids: they
read them from `/lessons`, which is also what the PWA does. A plan is created by the user, adjusted
only when the user asks, and its sessions take their state from real attempts.
"""

from fastapi.testclient import TestClient

from app.adapters.db.seed import LANGUAGE_ALEMAN, LANGUAGE_FRANCES, LANGUAGE_INGLES


def _lesson_ids(client: TestClient, language_id: str) -> list[str]:
    """Every lesson of one language in catalog order, read through the API."""
    response = client.get("/api/v1/lessons", params={"language_id": language_id})
    assert response.status_code == 200, response.text
    return [lesson["id"] for unit in response.json()["units"] for lesson in unit["lessons"]]


def _create(
    client: TestClient,
    language_id: str,
    *,
    goal: str = "Pasar de A1 a B1 en francés",
    frequency: int = 2,
    daily_minutes: int = 20,
) -> dict:
    response = client.post(
        "/api/v1/plans",
        json={
            "language_id": language_id,
            "goal": goal,
            "frequency": frequency,
            "daily_minutes": daily_minutes,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _plan_of(client: TestClient, language_id: str) -> dict | None:
    response = client.get("/api/v1/plans", params={"language_id": language_id})
    assert response.status_code == 200, response.text
    return response.json()["plan"]


def _submit(client: TestClient, lesson_id: str, answers: dict[str, str]) -> dict:
    """Answer a lesson: the caller passes only the exercises it wants to answer."""
    response = client.post(
        f"/api/v1/lessons/{lesson_id}/submit",
        json={"answers": [{"exercise_id": key, "answer": value} for key, value in answers.items()]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _attend(client: TestClient, lesson_id: str, *, perfect: bool) -> None:
    """Go through a lesson with every answer right or every answer wrong (S5's two states)."""
    detail = client.get(f"/api/v1/lessons/{lesson_id}")
    assert detail.status_code == 200, detail.text
    answers = {
        exercise["id"]: "zzz" if not perfect else _expected(client, lesson_id, exercise["id"])
        for exercise in detail.json()["exercises"]
    }
    _submit(client, lesson_id, answers)


def _expected(client: TestClient, lesson_id: str, exercise_id: str) -> str:
    """Answer one exercise correctly by asking the tutorial's own result of a wrong attempt."""
    detail = client.get(f"/api/v1/lessons/{lesson_id}")
    assert detail.status_code == 200, detail.text
    answers = {exercise["id"]: "zzz" for exercise in detail.json()["exercises"]}
    result = _submit(client, lesson_id, answers)
    return next(
        mistake["expected"]
        for mistake in result["mistakes"]
        if mistake["exercise_id"] == exercise_id
    )


def test_a_language_without_a_plan_returns_no_plan(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/plans", params={"language_id": LANGUAGE_FRANCES})

    assert response.status_code == 200, response.text
    assert response.json() == {"language_id": LANGUAGE_FRANCES, "plan": None}


def test_creating_a_plan_spreads_the_catalog_over_weeks(api_client: TestClient) -> None:
    lessons = _lesson_ids(api_client, LANGUAGE_FRANCES)

    plan = _create(api_client, LANGUAGE_FRANCES, frequency=2)

    assert plan["goal"] == "Pasar de A1 a B1 en francés"
    assert plan["frequency"] == 2
    assert plan["daily_minutes"] == 20
    # Every lesson of the catalog gets one session, in catalog order, `frequency` per week.
    assert [session["lesson_id"] for session in plan["sessions"]] == lessons
    assert [session["week"] for session in plan["sessions"]] == [
        index // 2 + 1 for index in range(len(lessons))
    ]
    assert plan["weeks"] == (len(lessons) + 1) // 2
    assert {session["status"] for session in plan["sessions"]} == {"pending"}
    # «Continuar plan» has somewhere to go before the first lesson is practised.
    assert plan["next_session"]["lesson_id"] == lessons[0]


def test_the_plan_belongs_to_one_language_only(api_client: TestClient) -> None:
    created = _create(api_client, LANGUAGE_FRANCES)

    assert _plan_of(api_client, LANGUAGE_FRANCES)["id"] == created["id"]
    assert _plan_of(api_client, LANGUAGE_ALEMAN) is None
    assert _plan_of(api_client, LANGUAGE_INGLES) is None


def test_creating_a_second_plan_for_the_same_language_is_a_conflict(
    api_client: TestClient,
) -> None:
    created = _create(api_client, LANGUAGE_FRANCES)

    response = api_client.post(
        "/api/v1/plans",
        json={
            "language_id": LANGUAGE_FRANCES,
            "goal": "Otro objetivo",
            "frequency": 5,
            "daily_minutes": 60,
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "plan_already_exists"
    # The rejected request changed nothing: the first plan is still the one stored.
    assert _plan_of(api_client, LANGUAGE_FRANCES) == created


def test_creating_a_plan_for_an_unknown_language_is_a_not_found(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/plans",
        json={
            "language_id": "no-existe",
            "goal": "Pasar de A1 a B1 en francés",
            "frequency": 2,
            "daily_minutes": 20,
        },
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "language_not_found"


def test_a_session_takes_its_state_from_the_real_attempt(api_client: TestClient) -> None:
    plan = _create(api_client, LANGUAGE_FRANCES, frequency=2)
    first, second = plan["sessions"][0], plan["sessions"][1]

    _attend(api_client, first["lesson_id"], perfect=True)
    _attend(api_client, second["lesson_id"], perfect=False)

    sessions = _plan_of(api_client, LANGUAGE_FRANCES)["sessions"]
    assert sessions[0]["status"] == "completed"
    # Every answer was wrong: the lesson was attempted and is not done (S5's «en curso»).
    assert sessions[1]["status"] == "in_progress"
    assert sessions[2]["status"] == "pending"


def test_continuing_the_plan_points_at_the_first_session_that_is_not_completed(
    api_client: TestClient,
) -> None:
    plan = _create(api_client, LANGUAGE_FRANCES, frequency=2)
    first, second = plan["sessions"][0], plan["sessions"][1]

    _attend(api_client, first["lesson_id"], perfect=True)

    current = _plan_of(api_client, LANGUAGE_FRANCES)
    assert current["next_session"]["lesson_id"] == second["lesson_id"]

    _attend(api_client, second["lesson_id"], perfect=True)

    assert (
        _plan_of(api_client, LANGUAGE_FRANCES)["next_session"]["lesson_id"]
        == (plan["sessions"][2]["lesson_id"])
    )


def test_adjusting_the_plan_recalculates_the_schedule_and_keeps_the_goal(
    api_client: TestClient,
) -> None:
    plan = _create(api_client, LANGUAGE_FRANCES, frequency=2)
    lessons = _lesson_ids(api_client, LANGUAGE_FRANCES)

    response = api_client.patch(
        f"/api/v1/plans/{plan['id']}",
        json={"frequency": 3, "daily_minutes": 45},
    )

    assert response.status_code == 200, response.text
    adjusted = response.json()
    assert adjusted["frequency"] == 3
    assert adjusted["daily_minutes"] == 45
    # The goal is what the user asked for: only the schedule and the time are adjustable (S4).
    assert adjusted["goal"] == plan["goal"]
    assert [session["lesson_id"] for session in adjusted["sessions"]] == lessons
    assert [session["week"] for session in adjusted["sessions"]] == [
        index // 3 + 1 for index in range(len(lessons))
    ]
    assert adjusted["adjusted_at"] is not None
    assert _plan_of(api_client, LANGUAGE_FRANCES)["weeks"] == adjusted["weeks"]


def test_adjusting_a_plan_that_does_not_exist_is_a_not_found(api_client: TestClient) -> None:
    response = api_client.patch("/api/v1/plans/no-existe", json={"frequency": 3})

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "plan_not_found"


def test_a_frequency_out_of_range_is_refused_and_changes_nothing(api_client: TestClient) -> None:
    plan = _create(api_client, LANGUAGE_FRANCES, frequency=2)

    response = api_client.patch(f"/api/v1/plans/{plan['id']}", json={"frequency": 9})

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert _plan_of(api_client, LANGUAGE_FRANCES) == plan
