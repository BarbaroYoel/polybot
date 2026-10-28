"""The `/api/v1` surface. Routers stay thin: validate, call a use case, serialize."""

from fastapi import APIRouter

from app.api.v1 import (
    conversations,
    health,
    languages,
    lessons,
    plans,
    progress,
    translation,
    voice,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(languages.router)
api_router.include_router(conversations.router)
api_router.include_router(lessons.router)
api_router.include_router(plans.router)
api_router.include_router(progress.router)
api_router.include_router(translation.router)
api_router.include_router(voice.router)
