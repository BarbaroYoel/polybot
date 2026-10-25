"""`/plans` endpoints (docs/api-contract.md §3 "Aprendizaje"). Thin: validate, call, serialize."""

from fastapi import APIRouter, Depends, Query

from app.api.v1.schemas import LanguagePlanOut, PlanAdjustIn, PlanCreateIn, PlanOut
from app.application.plans import PlanService
from app.core.dependencies import get_plan_service

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=LanguagePlanOut, summary="The plan of one language, if any")
async def get_plan(
    language_id: str = Query(min_length=1),
    service: PlanService = Depends(get_plan_service),
) -> LanguagePlanOut:
    return LanguagePlanOut.from_entity(language_id, await service.get_plan(language_id))


@router.post("", response_model=PlanOut, status_code=201, summary="Create the plan of a language")
async def create_plan(
    payload: PlanCreateIn,
    service: PlanService = Depends(get_plan_service),
) -> PlanOut:
    return PlanOut.from_entity(
        await service.create_plan(
            language_id=payload.language_id,
            goal=payload.goal,
            frequency=payload.frequency,
            daily_minutes=payload.daily_minutes,
        )
    )


@router.patch("/{plan_id}", response_model=PlanOut, summary="Adjust frequency and daily time")
async def adjust_plan(
    plan_id: str,
    payload: PlanAdjustIn | None = None,
    service: PlanService = Depends(get_plan_service),
) -> PlanOut:
    adjustment = payload or PlanAdjustIn()
    return PlanOut.from_entity(
        await service.adjust_plan(
            plan_id,
            frequency=adjustment.frequency,
            daily_minutes=adjustment.daily_minutes,
        )
    )
