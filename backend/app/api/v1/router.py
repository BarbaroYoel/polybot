"""The `/api/v1` surface. Routers stay thin: validate, call a use case, serialize."""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
