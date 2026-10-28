"""`/lessons` against the contract (F5 S1, S2, S6, S8).

The catalog is the seeded example content, so these tests do not hardcode lesson ids: they read
them from the API, which is also what the PWA does.
"""

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters.db.seed import LANGUAGE_ALEMAN, LANGUAGE_FRANCES, LANGUAGE_INGLES
from app.adapters.llm.pi import PiCliAdapter
from app.core.dependencies import get_llm
from app.domain.errors import LlmUnavailable
from tests.fakes.llm import FakeLlm

MISSING_PI = str(Path(tempfile.gettempdir()) / "polybot-pi-does-not-exist")


def _catalog(client: TestClient, language_id: str) -> dict:
    response = client.get("/api/v1/lessons", params={"language_id": language_id})
    assert response.status_code == 200, response.text
    return response.json()


def _first_lesson(client: TestClient, language_id: str) -> dict:
    return _catalog(client, language_id)["units"][0]["lessons"][0]


def _lesson_with(client: TestClient, language_id: str, title: str) -> dict:
    for unit in _catalog(client, language_id)["units"]:
        for lesson in unit["lessons"]:
            if lesson["title"] == title:
                return lesson
    raise AssertionError(f"{title} is not in the seeded catalog")


def _detail(client: TestClient, lesson_id: str) -> dict:
    response = client.get(f"/api/v1/lessons/{lesson_id}")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def client_without_pi(api_client: TestClient) -> Iterator[TestClient]:
    """The same app and database, with the real adapter aimed at an absent executable.

    `raise_server_exceptions=False` so an unhandled failure reaches the test as the 500 a browser
    would receive instead of a traceback; the provider still runs for real.
    """
    api_client.app.dependency_overrides[get_llm] = lambda: PiCliAdapter(command=[MISSING_PI])
    with TestClient(api_client.app, raise_server_exceptions=False) as client:
        yield client


def _submit(client: TestClient, lesson_id: str, answers: dict[str, str]) -> dict:
    response = client.post(
        f"/api/v1/lessons/{lesson_id}/submit",
        json={"answers": [{"exercise_id": key, "answer": value} for key, value in answers.items()]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_the_catalog_lists_the_units_and_lessons_of_one_language(
    api_client: TestClient,
) -> None:
    catalog = _catalog(api_client, LANGUAGE_INGLES)

    assert catalog["language_id"] == LANGUAGE_INGLES
    assert catalog["language_name"] == "Inglés"
    assert catalog["level"] == "B1"
    assert [unit["kind"] for unit in catalog["units"]] == ["vocabulary", "situational"]
    first_unit = catalog["units"][0]
    assert first_unit["title"] == "Vocabulario: pedir y pagar"
    assert [lesson["title"] for lesson in first_unit["lessons"]] == [
        "Pedir algo en un café",
        "Pagar y dejar propina",
    ]
    assert first_unit["lessons"][0]["difficulty"] == "A2"
    assert first_unit["lessons"][0]["estimated_minutes"] == 5
    assert all(
        lesson["status"] == "pending" for unit in catalog["units"] for lesson in unit["lessons"]
    ), "nobody practised yet"
    assert catalog["next_lesson"]["title"] == "Pedir algo en un café"


def test_the_catalog_never_mixes_languages(api_client: TestClient) -> None:
    english = _catalog(api_client, LANGUAGE_INGLES)
    french = _catalog(api_client, LANGUAGE_FRANCES)

    english_titles = {lesson["id"] for unit in english["units"] for lesson in unit["lessons"]}
    french_titles = {lesson["id"] for unit in french["units"] for lesson in unit["lessons"]}
    assert english_titles.isdisjoint(french_titles)
    assert len(english_titles) == len(french_titles) == 4


def test_a_catalog_of_an_unknown_language_is_a_not_found(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/lessons", params={"language_id": "no-existe"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "language_not_found"


def test_a_catalog_without_language_id_is_a_schema_error(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/lessons")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_the_detail_keeps_the_accepted_answers_out_of_the_response(
    api_client: TestClient,
) -> None:
    lesson = _first_lesson(api_client, LANGUAGE_INGLES)

    detail = _detail(api_client, lesson["id"])

    assert detail["unit_title"] == "Vocabulario: pedir y pagar"
    assert detail["unit_kind"] == "vocabulary"
    assert detail["title"] == "Pedir algo en un café"
    assert detail["intro"]
    assert len(detail["exercises"]) == 4
    assert set(detail["exercises"][0]) == {"id", "position", "prompt", "kind", "options"}
    # ADR-021: a written exercise carries no options; the choice one offers them, without answers.
    assert detail["exercises"][0]["kind"] == "writing"
    assert detail["exercises"][0]["options"] == []
    choice = detail["exercises"][-1]
    assert choice["kind"] == "choice"
    assert len(choice["options"]) == 4
    assert "accepted_answers" not in choice


def test_the_detail_of_another_language_is_a_not_found(api_client: TestClient) -> None:
    lesson = _first_lesson(api_client, LANGUAGE_FRANCES)

    response = api_client.get(
        f"/api/v1/lessons/{lesson['id']}", params={"language_id": LANGUAGE_INGLES}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "lesson_not_found"


def test_the_detail_of_an_unknown_lesson_is_a_not_found(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/lessons/no-existe")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "lesson_not_found"


def test_a_perfect_attempt_completes_the_lesson_and_recommends_the_next_one(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    lesson = _first_lesson(api_client, LANGUAGE_INGLES)
    detail = _detail(api_client, lesson["id"])
    answers = {
        detail["exercises"][0]["id"]: "I'd like a coffee, please",
        detail["exercises"][1]["id"]: "Could you bring me the bill, please?",
        detail["exercises"][2]["id"]: "to take away please",
        detail["exercises"][3]["id"]: "I'd like a coffee, please.",
    }

    result = _submit(api_client, lesson["id"], answers)

    assert (result["correct"], result["total"]) == (4, 4)
    assert result["completed"] is True
    assert result["mistakes"] == []
    assert [term["term"] for term in result["vocabulary"]] == ["I'd like", "the bill"]
    assert result["feedback"] == fake_llm.lesson_comment
    assert result["next_lesson"]["title"] == "Pagar y dejar propina"
    assert len(fake_llm.lesson_reviews) == 1
    review = fake_llm.lesson_reviews[0]
    assert review.lesson_title == "Pedir algo en un café"
    assert (review.correct, review.total) == (4, 4)

    catalog = _catalog(api_client, LANGUAGE_INGLES)
    assert catalog["units"][0]["lessons"][0]["status"] == "completed"
    assert catalog["next_lesson"]["title"] == "Pagar y dejar propina"


def test_a_missed_answer_keeps_the_lesson_in_progress_with_its_explanation(
    api_client: TestClient,
) -> None:
    lesson = _lesson_with(api_client, LANGUAGE_ALEMAN, "Verbos con preposición fija")
    detail = _detail(api_client, lesson["id"])
    answers = {
        detail["exercises"][0]["id"]: "Es hangt vom Wetter ab",
        detail["exercises"][1]["id"]: "Ich denke an dich",
        detail["exercises"][2]["id"]: "Er freut sich über den Besuch",
    }

    result = _submit(api_client, lesson["id"], answers)

    assert (result["correct"], result["total"]) == (2, 3)
    assert result["completed"] is False
    # The recommendation is the first lesson of the catalog that is not finished, in order: the
    # failed attempt leaves this one «en curso» and the earlier, never practised one comes first.
    assert result["next_lesson"]["title"] == "Preposiciones con dativo"
    mistake = result["mistakes"][0]
    assert mistake["answer"] == "Es hangt vom Wetter ab"
    assert mistake["expected"] == "Es hängt vom Wetter ab"
    assert mistake["explanation"]

    statuses = [
        lesson["status"]
        for unit in _catalog(api_client, LANGUAGE_ALEMAN)["units"]
        for lesson in unit["lessons"]
    ]
    assert len(statuses) == 4
    assert "in_progress" in statuses


def test_grading_ignores_case_and_punctuation_but_not_accents(api_client: TestClient) -> None:
    lesson = _lesson_with(api_client, LANGUAGE_FRANCES, "Saludar y presentarse")
    detail = _detail(api_client, lesson["id"])

    apostrophe_free = _submit(
        api_client,
        lesson["id"],
        {
            detail["exercises"][0]["id"]: "bonjour comment allez-vous",
            detail["exercises"][1]["id"]: "je m appelle ana",
            detail["exercises"][2]["id"]: "enchantée",
            detail["exercises"][3]["id"]: "Comment allez-vous ?",
        },
    )

    assert apostrophe_free["correct"] == 4, "case and punctuation are typing, not knowledge"

    accents = _submit(
        api_client,
        lesson["id"],
        {
            detail["exercises"][0]["id"]: "Bonjour, comment allez-vous ?",
            detail["exercises"][1]["id"]: "Je m'appelle Ana",
            detail["exercises"][2]["id"]: "enchante",
            detail["exercises"][3]["id"]: "Comment allez-vous ?",
        },
    )

    assert accents["correct"] == 3, "an accent changes the word: «enchanté» is not «enchante»"
    assert accents["mistakes"][0]["expected"] == "Enchanté"


def test_a_submit_that_skips_an_exercise_is_refused(api_client: TestClient) -> None:
    lesson = _first_lesson(api_client, LANGUAGE_INGLES)
    detail = _detail(api_client, lesson["id"])

    response = api_client.post(
        f"/api/v1/lessons/{lesson['id']}/submit",
        json={
            "answers": [
                {"exercise_id": detail["exercises"][0]["id"], "answer": "I'd like a coffee"}
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "missing_lesson_answers"
    # A refused submit stores nothing: every lesson is still pending (S5).
    statuses = [
        lesson["status"]
        for unit in _catalog(api_client, LANGUAGE_INGLES)["units"]
        for lesson in unit["lessons"]
    ]
    assert set(statuses) == {"pending"}


def test_the_same_exercise_answered_twice_is_a_schema_error(api_client: TestClient) -> None:
    lesson = _first_lesson(api_client, LANGUAGE_INGLES)
    detail = _detail(api_client, lesson["id"])
    exercise_id = detail["exercises"][0]["id"]

    response = api_client.post(
        f"/api/v1/lessons/{lesson['id']}/submit",
        json={
            "answers": [
                {"exercise_id": exercise_id, "answer": "I'd like a coffee"},
                {"exercise_id": exercise_id, "answer": "I would like a coffee"},
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_provider_failure_keeps_the_result_without_a_comment(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.lesson_comment_failure = LlmUnavailable("el tutor no respondió")
    lesson = _lesson_with(api_client, LANGUAGE_FRANCES, "Pagar con tarjeta")
    detail = _detail(api_client, lesson["id"])

    result = _submit(
        api_client,
        lesson["id"],
        {
            detail["exercises"][0]["id"]: "Puis-je payer par carte",
            detail["exercises"][1]["id"]: "Je n'ai pas de monnaie",
            detail["exercises"][2]["id"]: "Merci, à bientôt",
        },
    )

    assert result["feedback"] is None, "the closing comment is best-effort, never required"
    assert result["completed"] is True
    statuses = [
        lesson["status"]
        for unit in _catalog(api_client, LANGUAGE_FRANCES)["units"]
        for lesson in unit["lessons"]
    ]
    assert "completed" in statuses, "the attempt was stored anyway"


def test_a_missing_pi_executable_still_grades_the_lesson(
    api_client: TestClient, client_without_pi: TestClient
) -> None:
    """The real adapter against a binary that is not there: a provider failure, not a 500 (S8).

    The comment is best-effort, so a tutor that cannot even start must leave the deterministic
    grade and the stored attempt untouched instead of failing the whole submit.
    """
    lesson = _first_lesson(client_without_pi, LANGUAGE_INGLES)
    detail = _detail(client_without_pi, lesson["id"])
    answers = {
        detail["exercises"][0]["id"]: "I'd like a coffee, please",
        detail["exercises"][1]["id"]: "Could you bring me the bill, please?",
        detail["exercises"][2]["id"]: "to take away please",
        detail["exercises"][3]["id"]: "I'd like a coffee, please.",
    }

    response = client_without_pi.post(
        f"/api/v1/lessons/{lesson['id']}/submit",
        json={"answers": [{"exercise_id": key, "answer": value} for key, value in answers.items()]},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert (result["correct"], result["total"]) == (4, 4)
    assert result["completed"] is True
    assert result["feedback"] is None, "no tutor, no comment: the grade is still a grade"
    assert result["next_lesson"]["title"] == "Pagar y dejar propina"
    # The attempt survived: the public catalog is the only place this test reads it back from.
    assert _catalog(api_client, LANGUAGE_INGLES)["units"][0]["lessons"][0]["status"] == (
        "completed"
    )
    assert all(
        entry["status"] == "pending"
        for unit in _catalog(api_client, LANGUAGE_FRANCES)["units"]
        for entry in unit["lessons"]
    ), "the attempt belongs to one language only"


def test_submitting_an_unknown_lesson_is_a_not_found(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/lessons/no-existe/submit",
        json={"answers": [{"exercise_id": "cualquiera", "answer": "hola"}]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "lesson_not_found"


def test_a_choice_is_graded_by_the_option_the_student_picks(api_client: TestClient) -> None:
    """ADR-021: the type only changes the control; the grading is the deterministic one."""
    lesson = _lesson_with(api_client, LANGUAGE_FRANCES, "Saludar y presentarse")
    detail = _detail(api_client, lesson["id"])
    choice = detail["exercises"][-1]
    assert choice["kind"] == "choice"
    correct_option, *wrong_options = choice["options"]
    written = {
        exercise["id"]: "zzz" for exercise in detail["exercises"] if exercise["kind"] == "writing"
    }

    missed = _submit(api_client, lesson["id"], {**written, choice["id"]: wrong_options[0]})

    mistake = next(item for item in missed["mistakes"] if item["exercise_id"] == choice["id"])
    assert mistake["expected"] == correct_option, "the right option is revealed after a miss"

    picked = _submit(api_client, lesson["id"], {**written, choice["id"]: correct_option})
    assert choice["id"] not in {item["exercise_id"] for item in picked["mistakes"]}

    # Typing rules still apply to the picked text: case and punctuation do not decide the answer.
    typed = _submit(api_client, lesson["id"], {**written, choice["id"]: correct_option.lower()})
    assert choice["id"] not in {item["exercise_id"] for item in typed["mistakes"]}
