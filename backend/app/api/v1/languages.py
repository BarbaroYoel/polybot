"""`/languages` endpoints (docs/api-contract.md §3 "Idiomas"). Thin: validate, call, serialize."""

from fastapi import APIRouter, Depends

from app.api.v1.schemas import LanguageCreate, LanguageOut, LanguageUpdate
from app.application.languages import LanguageService
from app.core.dependencies import get_language_service
from app.domain.entities import WeeklyGoal

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("", response_model=list[LanguageOut], summary="List the non-archived languages")
async def list_languages(
    service: LanguageService = Depends(get_language_service),
) -> list[LanguageOut]:
    return [LanguageOut.from_entity(language) for language in await service.list_languages()]


@router.post("", response_model=LanguageOut, status_code=201, summary="Add a language")
async def create_language(
    payload: LanguageCreate,
    service: LanguageService = Depends(get_language_service),
) -> LanguageOut:
    language = await service.add_language(
        code=payload.code,
        name=payload.name,
        level=payload.level,
        explanation_language=payload.explanation_language,
        weekly_goal=WeeklyGoal(
            conversations=payload.weekly_goal.conversations,
            minutes=payload.weekly_goal.minutes,
        ),
    )
    return LanguageOut.from_entity(language)


@router.patch("/{language_id}", response_model=LanguageOut, summary="Change level, goal or active")
async def update_language(
    language_id: str,
    payload: LanguageUpdate,
    service: LanguageService = Depends(get_language_service),
) -> LanguageOut:
    weekly_goal = (
        WeeklyGoal(
            conversations=payload.weekly_goal.conversations,
            minutes=payload.weekly_goal.minutes,
        )
        if payload.weekly_goal is not None
        else None
    )
    language = await service.update_language(
        language_id,
        level=payload.level,
        weekly_goal=weekly_goal,
        is_active=payload.is_active,
    )
    return LanguageOut.from_entity(language)


@router.delete("/{language_id}", status_code=204, summary="Archive a language (soft delete)")
async def archive_language(
    language_id: str,
    service: LanguageService = Depends(get_language_service),
) -> None:
    await service.archive_language(language_id)
