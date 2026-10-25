"""`/lessons` endpoints (docs/api-contract.md §3 "Aprendizaje"). Thin: validate, call, serialize."""

from fastapi import APIRouter, Depends, Query

from app.api.v1.schemas import (
    LessonCatalogOut,
    LessonDetailOut,
    LessonResultOut,
    LessonSubmitIn,
)
from app.application.lessons import LessonService
from app.core.dependencies import get_lesson_service

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("", response_model=LessonCatalogOut, summary="Catalog of one language")
async def get_catalog(
    language_id: str = Query(min_length=1),
    service: LessonService = Depends(get_lesson_service),
) -> LessonCatalogOut:
    return LessonCatalogOut.from_entity(await service.catalog(language_id))


@router.get("/{lesson_id}", response_model=LessonDetailOut, summary="One lesson with its exercises")
async def get_lesson(
    lesson_id: str,
    language_id: str | None = Query(default=None, min_length=1),
    service: LessonService = Depends(get_lesson_service),
) -> LessonDetailOut:
    return LessonDetailOut.from_entity(await service.detail(lesson_id, language_id))


@router.post(
    "/{lesson_id}/submit",
    response_model=LessonResultOut,
    summary="Grade a finished lesson and store the attempt",
)
async def submit_lesson(
    lesson_id: str,
    payload: LessonSubmitIn,
    service: LessonService = Depends(get_lesson_service),
) -> LessonResultOut:
    answers = {answer.exercise_id: answer.answer for answer in payload.answers}
    return LessonResultOut.from_entity(await service.submit(lesson_id, answers))
