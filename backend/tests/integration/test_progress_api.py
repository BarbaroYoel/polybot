"""`/progress` against the contract (F6 S1–S6).

Progress is a read-only view: every number comes from stored conversations, lesson attempts,
corrections or vocabulary, filtered by `language_id`. The tests create that activity through the
public API when the timestamp does not matter, and write rows directly when a specific date is the
point (the weekly boundary and the mixed history), so no assertion depends on wall-clock luck.
"""

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.models import (
    ConversationRow,
    LessonAttemptAnswerRow,
    LessonAttemptRow,
    MessageCorrectionRow,
    MessageFeedbackRow,
    MessageRow,
)
from app.adapters.db.seed import (
    CONVERSATION_FR_CAFE,
    LANGUAGE_ALEMAN,
    LANGUAGE_FRANCES,
    LANGUAGE_INGLES,
)
from app.application.progress import week_start
from app.core.dates import utc_now
from app.ports.llm import TurnFeedback, VocabularyDraft
from tests.fakes.llm import FakeLlm

SKILLS = ["conversation", "writing", "vocabulary", "reading", "listening"]


def _progress(client: TestClient, language_id: str, *, tz: str | None = None) -> dict[str, Any]:
    params = {"language_id": language_id}
    if tz is not None:
        params["tz"] = tz
    response = client.get("/api/v1/progress", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _skill(progress: dict[str, Any], skill_id: str) -> dict[str, Any]:
    return next(skill for skill in progress["skills"] if skill["id"] == skill_id)


def _lesson_ids(client: TestClient, language_id: str) -> list[str]:
    response = client.get("/api/v1/lessons", params={"language_id": language_id})
    assert response.status_code == 200, response.text
    return [lesson["id"] for unit in response.json()["units"] for lesson in unit["lessons"]]


def _detail(client: TestClient, lesson_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/lessons/{lesson_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _submit(client: TestClient, lesson_id: str, answers: Mapping[str, str]) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/lessons/{lesson_id}/submit",
        json={"answers": [{"exercise_id": key, "answer": value} for key, value in answers.items()]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _attend(client: TestClient, lesson_id: str, *, perfect: bool) -> None:
    """Practise one lesson with every answer wrong, or with every expected answer (S1)."""
    exercises = _detail(client, lesson_id)["exercises"]
    answers = {exercise["id"]: "zzz" for exercise in exercises}
    if not perfect:
        _submit(client, lesson_id, answers)
        return

    # The expected answers are part of the deterministic grade, never of the exercise detail.
    result = _submit(client, lesson_id, answers)
    expected = {mistake["exercise_id"]: mistake["expected"] for mistake in result["mistakes"]}
    _submit(client, lesson_id, expected)


async def _add_conversation(
    session: AsyncSession,
    *,
    language_id: str,
    title: str,
    messages: Sequence[datetime],
) -> str:
    """Store one conversation with one message per timestamp, exactly as a real turn would."""
    conversation_id = str(uuid4())
    session.add(
        ConversationRow(
            id=conversation_id,
            language_id=language_id,
            mode="free",
            title=title,
            message_count=len(messages),
            last_message_at=max(messages),
            created_at=min(messages),
        )
    )
    await session.flush()
    session.add_all(
        MessageRow(
            id=str(uuid4()),
            conversation_id=conversation_id,
            author="user",
            content=f"{title} #{position}",
            translation=None,
            status="sent",
            idempotency_key=None,
            created_at=created_at,
        )
        for position, created_at in enumerate(messages)
    )
    await session.flush()
    return conversation_id


async def _add_attempt(
    session: AsyncSession,
    *,
    language_id: str,
    lesson_id: str,
    answers: Mapping[str, bool],
    at: datetime,
) -> str:
    """Store one attempt whose answers are flagged right or wrong, with a chosen timestamp."""
    attempt_id = str(uuid4())
    session.add(
        LessonAttemptRow(
            id=attempt_id,
            lesson_id=lesson_id,
            language_id=language_id,
            feedback=None,
            created_at=at,
        )
    )
    await session.flush()
    session.add_all(
        LessonAttemptAnswerRow(
            id=str(uuid4()),
            attempt_id=attempt_id,
            exercise_id=exercise_id,
            answer="ok" if correct else "zzz",
            correct=correct,
        )
        for exercise_id, correct in answers.items()
    )
    await session.flush()
    return attempt_id


async def _add_correction(
    session: AsyncSession,
    *,
    language_id: str,
    original: str,
    corrected: str,
    at: datetime,
) -> None:
    """Store one closing turn with a single correction, dated on purpose."""
    conversation_id = str(uuid4())
    message_id = str(uuid4())
    feedback_id = str(uuid4())
    session.add(
        ConversationRow(
            id=conversation_id,
            language_id=language_id,
            mode="free",
            title="Corrección",
            message_count=1,
            last_message_at=at,
            created_at=at,
        )
    )
    await session.flush()
    session.add(
        MessageRow(
            id=message_id,
            conversation_id=conversation_id,
            author="user",
            content=original,
            translation=None,
            status="sent",
            idempotency_key=None,
            created_at=at,
        )
    )
    await session.flush()
    session.add(MessageFeedbackRow(id=feedback_id, message_id=message_id, created_at=at))
    await session.flush()
    session.add(
        MessageCorrectionRow(
            id=str(uuid4()),
            feedback_id=feedback_id,
            position=0,
            original=original,
            corrected=corrected,
            explanation="",
        )
    )
    await session.flush()


def test_an_unknown_language_is_a_not_found(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/progress", params={"language_id": "no-existe"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "language_not_found"


def test_a_language_without_activity_returns_zeros_and_the_five_skills(
    api_client: TestClient,
) -> None:
    lessons = _lesson_ids(api_client, LANGUAGE_ALEMAN)
    # The target is the profile's own goal, not a constant of the endpoint.
    response = api_client.patch(
        f"/api/v1/languages/{LANGUAGE_ALEMAN}",
        json={"weekly_goal": {"conversations": 3}},
    )
    assert response.status_code == 200, response.text

    progress = _progress(api_client, LANGUAGE_ALEMAN)

    assert progress["language"] == {
        "id": LANGUAGE_ALEMAN,
        "code": "de",
        "name": "Alemán",
        "level": "B2",
    }
    assert progress["summary"] == {
        "level": "B2",
        "lessons_completed": 0,
        "lessons_total": len(lessons),
        "conversations": 0,
        "weekly_goal": {"conversations": 0, "target": 3},
    }
    assert [skill["id"] for skill in progress["skills"]] == SKILLS
    assert [skill["available"] for skill in progress["skills"]] == [
        True,
        True,
        True,
        False,
        False,
    ]
    assert [(skill["count"], skill["last_at"]) for skill in progress["skills"][:3]] == [
        (0, None),
        (0, None),
        (0, None),
    ]
    # Reading and listening are unknown, not zero: the UI must not show them as measured (S2).
    assert [(skill["count"], skill["last_at"]) for skill in progress["skills"][3:]] == [
        (None, None),
        (None, None),
    ]
    assert progress["frequent_errors"] == []
    assert progress["history"] == []


def test_lessons_completed_counts_only_lessons_with_an_approved_attempt(
    api_client: TestClient,
) -> None:
    lessons = _lesson_ids(api_client, LANGUAGE_FRANCES)
    _attend(api_client, lessons[0], perfect=True)
    _attend(api_client, lessons[1], perfect=False)

    summary = _progress(api_client, LANGUAGE_FRANCES)["summary"]

    assert summary["lessons_completed"] == 1
    assert summary["lessons_total"] == len(lessons)


def test_an_empty_conversation_is_not_a_practice(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/conversations",
        json={"language_id": LANGUAGE_ALEMAN, "title": "Sin mensajes"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["message_count"] == 0

    progress = _progress(api_client, LANGUAGE_ALEMAN)

    assert progress["summary"]["conversations"] == 0
    assert _skill(progress, "conversation")["count"] == 0
    assert progress["history"] == []


def test_the_weekly_goal_counts_from_monday_in_the_requested_timezone(
    api_client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Kiritimati is UTC+14, so its local Monday 00:00 falls on a Sunday in UTC.
    start = week_start("Pacific/Kiritimati")
    assert start.weekday() == 6, "the local Monday starts on a UTC Sunday"

    async def seed() -> None:
        async with session_factory() as session:
            await _add_conversation(
                session,
                language_id=LANGUAGE_ALEMAN,
                title="Semana anterior",
                messages=[start - timedelta(hours=1)],
            )
            await _add_conversation(
                session,
                language_id=LANGUAGE_ALEMAN,
                title="Lunes local",
                messages=[start + timedelta(hours=1)],
            )
            await session.commit()

    asyncio.run(seed())

    local = _progress(api_client, LANGUAGE_ALEMAN, tz="Pacific/Kiritimati")
    utc = _progress(api_client, LANGUAGE_ALEMAN, tz="UTC")

    # Both conversations exist; only the one after the local Monday counts for the goal.
    assert local["summary"]["conversations"] == 2
    assert local["summary"]["weekly_goal"] == {"conversations": 1, "target": 7}
    # The same Sunday belongs to the previous UTC week except when the UTC clock itself is already
    # on Sunday, so the expected UTC count is derived from the same boundary instead of hardcoded.
    utc_start = week_start("UTC")
    inserted = (start - timedelta(hours=1), start + timedelta(hours=1))
    expected_utc = sum(1 for at in inserted if at >= utc_start)
    assert utc["summary"]["conversations"] == 2
    assert utc["summary"]["weekly_goal"]["conversations"] == expected_utc


def test_writing_counts_the_exercise_answers_of_the_language(api_client: TestClient) -> None:
    lesson_id = _lesson_ids(api_client, LANGUAGE_FRANCES)[0]
    exercises = _detail(api_client, lesson_id)["exercises"]
    _submit(api_client, lesson_id, {exercise["id"]: "zzz" for exercise in exercises})

    progress = _progress(api_client, LANGUAGE_FRANCES)

    writing = _skill(progress, "writing")
    assert writing["available"] is True
    assert writing["count"] == len(exercises)
    assert writing["last_at"] is not None
    assert _skill(_progress(api_client, LANGUAGE_ALEMAN), "writing")["count"] == 0


def test_vocabulary_counts_the_terms_suggested_in_the_language(
    api_client: TestClient, fake_llm: FakeLlm
) -> None:
    fake_llm.feedback = TurnFeedback(
        corrections=(),
        vocabulary=(
            VocabularyDraft(term="un café", translation="un café", note="masculino"),
            VocabularyDraft(term="l'addition", translation="la cuenta", note=None),
        ),
    )
    message = api_client.post(
        f"/api/v1/conversations/{CONVERSATION_FR_CAFE}/messages",
        json={"content": "Je voudrais un café"},
    )
    assert message.status_code == 201, message.text
    stream = api_client.get(
        f"/api/v1/conversations/{CONVERSATION_FR_CAFE}/stream",
        params={"message_id": message.json()["id"]},
    )
    assert stream.status_code == 200, stream.text

    vocabulary = _skill(_progress(api_client, LANGUAGE_FRANCES), "vocabulary")

    assert vocabulary["available"] is True
    assert vocabulary["count"] == 2
    assert vocabulary["last_at"] is not None
    assert _skill(_progress(api_client, LANGUAGE_ALEMAN), "vocabulary")["count"] == 0


def test_frequent_errors_are_grouped_ordered_and_capped_at_five(
    api_client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    lessons = _lesson_ids(api_client, LANGUAGE_FRANCES)
    first, second = lessons[0], lessons[1]
    first_answers = {exercise["id"]: "zzz" for exercise in _detail(api_client, first)["exercises"]}
    expected = {
        mistake["exercise_id"]: mistake["expected"]
        for mistake in _submit(api_client, first, first_answers)["mistakes"]
    }
    _submit(api_client, first, first_answers)  # the same pairs now happen twice
    second_answers = {
        exercise["id"]: "zzz" for exercise in _detail(api_client, second)["exercises"]
    }
    _submit(api_client, second, second_answers)

    async def seed() -> None:
        async with session_factory() as session:
            await _add_correction(
                session,
                language_id=LANGUAGE_FRANCES,
                original="je suis allé",
                corrected="je suis allée",
                at=utc_now(),
            )
            await session.commit()

    asyncio.run(seed())

    errors = _progress(api_client, LANGUAGE_FRANCES)["frequent_errors"]

    assert len(errors) == 5, "the contract caps the list at five"
    assert [error["count"] for error in errors] == [2, 2, 2, 2, 1]
    # A lesson error carries its exercise prompt and the first accepted answer as expected.
    assert all(error["kind"] == "lesson" for error in errors[:4])
    assert all(error["prompt"] for error in errors[:4])
    assert {error["expected"] for error in errors[:4]} == set(expected.values())
    # The newest one-count error is the tutor correction, which has no prompt.
    assert errors[4]["kind"] == "correction"
    assert errors[4]["prompt"] is None
    assert errors[4]["original"] == "je suis allé"
    assert errors[4]["expected"] == "je suis allée"
    assert all(error["last_at"] for error in errors)


def test_history_mixes_lessons_and_conversations_newest_first_and_capped_at_ten(
    api_client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # German has no seeded conversation, so the twelve rows below are the whole history.
    lessons = _lesson_ids(api_client, LANGUAGE_ALEMAN)
    lesson_id = lessons[0]
    exercise_ids = [exercise["id"] for exercise in _detail(api_client, lesson_id)["exercises"]]
    base = datetime(2026, 9, 1, 9, 0)

    async def seed() -> tuple[list[str], list[str]]:
        async with session_factory() as session:
            attempts = [
                await _add_attempt(
                    session,
                    language_id=LANGUAGE_ALEMAN,
                    lesson_id=lesson_id,
                    answers={
                        exercise_id: index < correct
                        for index, exercise_id in enumerate(exercise_ids)
                    },
                    at=base + timedelta(hours=hour),
                )
                for correct, hour in zip((3, 2, 1, 0, 2, 1), (1, 3, 5, 7, 9, 11), strict=True)
            ]
            conversations = [
                await _add_conversation(
                    session,
                    language_id=LANGUAGE_ALEMAN,
                    title=f"Conversación {index}",
                    messages=[
                        base + timedelta(hours=hour, minutes=-5),
                        base + timedelta(hours=hour),
                    ],
                )
                for index, hour in enumerate((0, 2, 4, 6, 8, 10))
            ]
            await session.commit()
            return attempts, conversations

    attempts, conversations = asyncio.run(seed())
    history = _progress(api_client, LANGUAGE_ALEMAN)["history"]

    assert len(history) == 10, "the contract caps the history at ten"
    # Interleaved by time: 11h attempt, 10h conversation, 9h attempt, ... down to the 2h one.
    assert [entry["kind"] for entry in history] == [
        "lesson",
        "conversation",
        "lesson",
        "conversation",
        "lesson",
        "conversation",
        "lesson",
        "conversation",
        "lesson",
        "conversation",
    ]
    assert history[0]["id"] == attempts[-1]
    assert history[1]["id"] == conversations[-1]
    assert [entry["at"] for entry in history] == sorted(
        (entry["at"] for entry in history), reverse=True
    )

    for entry in history:
        if entry["kind"] == "lesson":
            assert entry["total"] == len(exercise_ids)
            assert entry["message_count"] is None
            assert entry["correct"] is not None
        else:
            assert entry["message_count"] == 2
            assert entry["correct"] is None and entry["total"] is None


def test_progress_never_mixes_another_language_attempt_or_conversation(
    api_client: TestClient,
) -> None:
    _attend(api_client, _lesson_ids(api_client, LANGUAGE_FRANCES)[0], perfect=True)

    french = _progress(api_client, LANGUAGE_FRANCES)
    german = _progress(api_client, LANGUAGE_ALEMAN)
    english = _progress(api_client, LANGUAGE_INGLES)

    assert french["summary"]["lessons_completed"] == 1
    assert french["summary"]["conversations"] == 1, "only the seeded French conversation"
    # The French attempt and conversation do not appear in the other languages.
    assert german["summary"]["lessons_completed"] == 0
    assert german["summary"]["conversations"] == 0
    assert german["history"] == []
    assert english["summary"]["lessons_completed"] == 0
    assert english["summary"]["conversations"] == 1, "only the seeded English conversation"
    assert all(entry["kind"] == "conversation" for entry in english["history"]), (
        "no French attempt leaked into English"
    )


def test_an_invalid_timezone_is_a_bad_request(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/progress",
        params={"language_id": LANGUAGE_FRANCES, "tz": "No/Existe"},
    )

    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == "invalid_timezone"
    assert "IANA" in error["message"], "the message must say how to fix it"
