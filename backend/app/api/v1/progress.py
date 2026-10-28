"""`/progress` endpoint (docs/api-contract.md §3 "El progreso"). Thin: validate, call, serialize.

The router knows nothing about how the counters are derived: the service composes them from the
stored activity and the profile (F6, ADR-018).
"""

from fastapi import APIRouter, Depends, Query

from app.api.v1.schemas import ProgressOut
from app.application.progress import ProgressService
from app.core.dependencies import get_progress_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut, summary="Progress of one language")
async def get_progress(
    language_id: str = Query(min_length=1, description="Language whose progress is shown"),
    tz: str = Query(
        default="UTC",
        description="IANA zone used to start the week on Monday 00:00 local time",
    ),
    service: ProgressService = Depends(get_progress_service),
) -> ProgressOut:
    return ProgressOut.from_view(await service.get_progress(language_id, tz=tz))
