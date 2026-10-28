"""SQLAlchemy adapter for the lesson catalog and its attempts (F5 S1, S2, S6, ADR-021)."""

import json
from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    LessonAttemptAnswerRow,
    LessonAttemptRow,
    LessonExerciseAnswerRow,
    LessonExerciseRow,
    LessonRow,
    LessonUnitRow,
    LessonVocabularyRow,
)
from app.core.dates import utc_now
from app.domain.entities import (
    CefrLevel,
    ExerciseKind,
    Lesson,
    LessonAnswer,
    LessonAttempt,
    LessonExercise,
    LessonStatus,
    LessonTerm,
    LessonUnit,
    LessonUnitKind,
)


def _stored_options(raw: str | None) -> tuple[str, ...]:
    """Options of a choice exercise, tolerant to a row this version cannot read (ADR-021)."""
    if not raw:
        return ()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _to_unit(row: LessonUnitRow) -> LessonUnit:
    return LessonUnit(
        id=row.id,
        language_id=row.language_id,
        kind=LessonUnitKind(row.kind),
        title=row.title,
        description=row.description,
        position=row.position,
    )


def _to_lesson(row: LessonRow) -> Lesson:
    return Lesson(
        id=row.id,
        unit_id=row.unit_id,
        language_id=row.language_id,
        title=row.title,
        difficulty=CefrLevel(row.difficulty),
        estimated_minutes=row.estimated_minutes,
        intro=row.intro,
        position=row.position,
    )


class SqlAlchemyLessonRepository:
    """`LessonRepository` port over SQLAlchemy (docs/architecture.md §3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_units(self, language_id: str) -> list[LessonUnit]:
        rows = await self._session.scalars(
            select(LessonUnitRow)
            .where(LessonUnitRow.language_id == language_id)
            .order_by(LessonUnitRow.position, LessonUnitRow.id)
        )
        return [_to_unit(row) for row in rows]

    async def list_lessons(self, language_id: str) -> list[Lesson]:
        rows = await self._session.scalars(
            select(LessonRow)
            .join(LessonUnitRow, LessonUnitRow.id == LessonRow.unit_id)
            .where(LessonRow.language_id == language_id)
            .order_by(LessonUnitRow.position, LessonRow.position, LessonRow.id)
        )
        return [_to_lesson(row) for row in rows]

    async def get_lesson(self, lesson_id: str) -> Lesson | None:
        row = await self._session.get(LessonRow, lesson_id)
        return _to_lesson(row) if row else None

    async def get_unit(self, unit_id: str) -> LessonUnit | None:
        row = await self._session.get(LessonUnitRow, unit_id)
        return _to_unit(row) if row else None

    async def list_exercises(self, lesson_id: str) -> list[LessonExercise]:
        exercises = list(
            await self._session.scalars(
                select(LessonExerciseRow)
                .where(LessonExerciseRow.lesson_id == lesson_id)
                .order_by(LessonExerciseRow.position, LessonExerciseRow.id)
            )
        )
        if not exercises:
            return []

        answers: dict[str, list[str]] = {}
        answer_rows = await self._session.scalars(
            select(LessonExerciseAnswerRow)
            .where(LessonExerciseAnswerRow.exercise_id.in_([exercise.id for exercise in exercises]))
            .order_by(LessonExerciseAnswerRow.position, LessonExerciseAnswerRow.id)
        )
        for answer in answer_rows:
            answers.setdefault(answer.exercise_id, []).append(answer.answer)

        return [
            LessonExercise(
                id=exercise.id,
                lesson_id=exercise.lesson_id,
                position=exercise.position,
                prompt=exercise.prompt,
                accepted_answers=answers.get(exercise.id, []),
                explanation=exercise.explanation,
                kind=ExerciseKind(exercise.kind),
                options=_stored_options(exercise.options_json),
            )
            for exercise in exercises
        ]

    async def list_terms(self, lesson_id: str) -> list[LessonTerm]:
        rows = await self._session.scalars(
            select(LessonVocabularyRow)
            .where(LessonVocabularyRow.lesson_id == lesson_id)
            .order_by(LessonVocabularyRow.position, LessonVocabularyRow.id)
        )
        return [
            LessonTerm(term=row.term, translation=row.translation, note=row.note) for row in rows
        ]

    async def lesson_statuses(self, language_id: str) -> dict[str, LessonStatus]:
        attempts = (
            await self._session.execute(
                select(LessonAttemptRow.id, LessonAttemptRow.lesson_id)
                .where(LessonAttemptRow.language_id == language_id)
                .order_by(LessonAttemptRow.created_at, LessonAttemptRow.id)
            )
        ).all()
        if not attempts:
            return {}

        outcomes: dict[str, list[bool]] = {}
        answer_rows = await self._session.execute(
            select(LessonAttemptAnswerRow.attempt_id, LessonAttemptAnswerRow.correct).where(
                LessonAttemptAnswerRow.attempt_id.in_([attempt_id for attempt_id, _ in attempts])
            )
        )
        for attempt_id, correct in answer_rows:
            outcomes.setdefault(attempt_id, []).append(correct)

        # Attempts arrive oldest first: a finished one is never downgraded by a later miss.
        statuses: dict[str, LessonStatus] = {}
        for attempt_id, lesson_id in attempts:
            answers = outcomes.get(attempt_id, [])
            if answers and all(answers):
                statuses[lesson_id] = LessonStatus.COMPLETED
            elif statuses.get(lesson_id) is not LessonStatus.COMPLETED:
                statuses[lesson_id] = LessonStatus.IN_PROGRESS
        return statuses


class SqlAlchemyLessonAttemptRepository:
    """`LessonAttemptRepository` port: the written result of one practice (F5 S2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_attempt(
        self,
        *,
        lesson_id: str,
        language_id: str,
        answers: Sequence[LessonAnswer],
        feedback: str | None,
    ) -> LessonAttempt:
        created_at = utc_now()
        row = LessonAttemptRow(
            id=str(uuid4()),
            lesson_id=lesson_id,
            language_id=language_id,
            feedback=feedback,
            created_at=created_at,
        )
        self._session.add(row)
        # Without ORM relationships the attempt must exist before its answers reference it.
        await self._session.flush()
        for answer in answers:
            self._session.add(
                LessonAttemptAnswerRow(
                    id=str(uuid4()),
                    attempt_id=row.id,
                    exercise_id=answer.exercise_id,
                    answer=answer.answer,
                    correct=answer.correct,
                )
            )
        await self._session.flush()
        return LessonAttempt(
            id=row.id,
            lesson_id=lesson_id,
            language_id=language_id,
            answers=list(answers),
            feedback=feedback,
            created_at=created_at,
        )
