"""Lesson use cases (docs/api-contract.md §3 "Aprendizaje", F5 S1, S2, S6, S8).

Grading happens here and needs no model: the catalogue carries the answers each exercise accepts
and `domain/grading.py` compares them. The tutor is asked only for the closing comment, and that
call is best-effort: a provider failure leaves the result intact with no comment.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.entities import (
    LanguageProfile,
    Lesson,
    LessonAnswer,
    LessonAttempt,
    LessonExercise,
    LessonStatus,
    LessonTerm,
    LessonUnit,
)
from app.domain.errors import (
    LanguageNotFound,
    LessonNotFound,
    LlmTimeout,
    LlmUnavailable,
    MissingLessonAnswers,
)
from app.domain.grading import is_correct
from app.ports.llm import LessonReviewItem, LessonReviewRequest, LlmPort, TutorContext
from app.ports.repositories import (
    LanguageRepository,
    LessonAttemptRepository,
    LessonRepository,
)


@dataclass(frozen=True, slots=True)
class CatalogLesson:
    lesson: Lesson
    status: LessonStatus


@dataclass(frozen=True, slots=True)
class CatalogUnit:
    unit: LessonUnit
    lessons: Sequence[CatalogLesson]


@dataclass(frozen=True, slots=True)
class LessonCatalog:
    language: LanguageProfile
    units: Sequence[CatalogUnit]
    next_lesson: CatalogLesson | None


@dataclass(frozen=True, slots=True)
class LessonDetail:
    lesson: Lesson
    unit: LessonUnit
    exercises: Sequence[LessonExercise]


@dataclass(frozen=True, slots=True)
class LessonMistake:
    """One wrong answer, with what was expected and why (F5 S2, «errores relevantes»)."""

    exercise_id: str
    prompt: str
    answer: str
    expected: str
    explanation: str


@dataclass(frozen=True, slots=True)
class LessonResult:
    lesson: Lesson
    attempt: LessonAttempt
    mistakes: Sequence[LessonMistake]
    terms: Sequence[LessonTerm]
    next_lesson: CatalogLesson | None


class LessonService:
    def __init__(
        self,
        *,
        lessons: LessonRepository,
        attempts: LessonAttemptRepository,
        languages: LanguageRepository,
        llm: LlmPort,
    ) -> None:
        self._lessons = lessons
        self._attempts = attempts
        self._languages = languages
        self._llm = llm

    async def catalog(self, language_id: str) -> LessonCatalog:
        language = await self._languages.get_language(language_id)
        if language is None:
            raise LanguageNotFound(language_id)

        units = await self._lessons.list_units(language_id)
        lessons = await self._lessons.list_lessons(language_id)
        statuses = await self._lessons.lesson_statuses(language_id)

        grouped: dict[str, list[CatalogLesson]] = {}
        for lesson in lessons:
            grouped.setdefault(lesson.unit_id, []).append(
                CatalogLesson(
                    lesson=lesson,
                    status=statuses.get(lesson.id, LessonStatus.PENDING),
                )
            )
        catalog_units = [CatalogUnit(unit=unit, lessons=grouped.get(unit.id, [])) for unit in units]

        # «Continuar aprendiendo» is the first lesson that is not finished, in catalog order (S1).
        next_lesson = next(
            (
                entry
                for unit in catalog_units
                for entry in unit.lessons
                if entry.status is not LessonStatus.COMPLETED
            ),
            None,
        )
        return LessonCatalog(language=language, units=catalog_units, next_lesson=next_lesson)

    async def detail(self, lesson_id: str, language_id: str | None = None) -> LessonDetail:
        lesson = await self._get_lesson(lesson_id, language_id)
        unit = await self._lessons.get_unit(lesson.unit_id)
        if unit is None:
            raise LessonNotFound(lesson_id)
        return LessonDetail(
            lesson=lesson,
            unit=unit,
            exercises=await self._lessons.list_exercises(lesson_id),
        )

    async def submit(
        self,
        lesson_id: str,
        answers: Mapping[str, str],
        language_id: str | None = None,
    ) -> LessonResult:
        detail = await self.detail(lesson_id, language_id)
        graded = self._grade(detail, answers)
        mistakes = self._mistakes(detail, graded)
        comment = await self._comment(detail, graded)

        attempt = await self._attempts.add_attempt(
            lesson_id=detail.lesson.id,
            language_id=detail.lesson.language_id,
            answers=graded,
            feedback=comment,
        )
        # After storing the attempt, so «próxima recomendación» already reflects this result (S2).
        catalog = await self.catalog(detail.lesson.language_id)
        return LessonResult(
            lesson=detail.lesson,
            attempt=attempt,
            mistakes=mistakes,
            terms=await self._lessons.list_terms(lesson_id),
            next_lesson=catalog.next_lesson,
        )

    async def _get_lesson(self, lesson_id: str, language_id: str | None) -> Lesson:
        lesson = await self._lessons.get_lesson(lesson_id)
        if lesson is None or (language_id is not None and lesson.language_id != language_id):
            # A lesson of another language is a 404, never a leak across languages (S6).
            raise LessonNotFound(lesson_id)
        return lesson

    @staticmethod
    def _grade(detail: LessonDetail, answers: Mapping[str, str]) -> list[LessonAnswer]:
        if not detail.exercises:
            raise LessonNotFound(detail.lesson.id)

        graded: list[LessonAnswer] = []
        for exercise in detail.exercises:
            answer = (answers.get(exercise.id) or "").strip()
            if not answer:
                # A submit answers every exercise: a half-filled one is not a result (S7).
                raise MissingLessonAnswers(exercise.id)
            graded.append(
                LessonAnswer(
                    exercise_id=exercise.id,
                    answer=answer,
                    correct=is_correct(answer, exercise.accepted_answers),
                )
            )
        return graded

    @staticmethod
    def _mistakes(detail: LessonDetail, graded: Sequence[LessonAnswer]) -> list[LessonMistake]:
        by_id = {exercise.id: exercise for exercise in detail.exercises}
        return [
            LessonMistake(
                exercise_id=answer.exercise_id,
                prompt=by_id[answer.exercise_id].prompt,
                answer=answer.answer,
                expected=by_id[answer.exercise_id].expected,
                explanation=by_id[answer.exercise_id].explanation,
            )
            for answer in graded
            if not answer.correct
        ]

    async def _comment(self, detail: LessonDetail, graded: Sequence[LessonAnswer]) -> str | None:
        """The tutor's closing comment: best-effort, so a failure never loses the result."""
        language = await self._languages.get_language(detail.lesson.language_id)
        if language is None:
            return None

        by_id = {exercise.id: exercise for exercise in detail.exercises}
        request = LessonReviewRequest(
            context=TutorContext(
                language_name=language.name,
                language_code=language.code,
                level=language.level,
                explanation_language=language.explanation_language,
            ),
            lesson_title=detail.lesson.title,
            items=[
                LessonReviewItem(
                    prompt=by_id[answer.exercise_id].prompt,
                    answer=answer.answer,
                    expected=by_id[answer.exercise_id].expected,
                    correct=answer.correct,
                )
                for answer in graded
            ],
        )
        try:
            return await self._llm.review_lesson(request)
        except (LlmUnavailable, LlmTimeout):
            return None
