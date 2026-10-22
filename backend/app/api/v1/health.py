"""Liveness endpoint (docs/api-contract.md §3 "Sistema", odd/tasks/f2-backend-skeleton.md S3)."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import Settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness")
async def health(request: Request) -> HealthResponse:
    """Answers without touching the database or any provider."""
    settings: Settings = request.app.state.settings
    return HealthResponse(status="ok", version=settings.app_version)
