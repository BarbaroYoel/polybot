"""Application factory.

docs/architecture.md §2: `main.py` creates the app, mounts routers and middleware.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.db.session import create_engine, create_session_factory
from app.api.v1.router import api_router
from app.core.config import Settings
from app.core.handlers import install_error_handlers
from app.core.middleware import RequestIdMiddleware

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Settings are read on every call so tests can vary the environment."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.engine.dispose()

    app = FastAPI(
        title="Polybot API",
        version=settings.app_version,
        debug=settings.app_debug,
        description="Language tutor backend. Contract: docs/api-contract.md.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = create_engine(settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    install_error_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)
    return app


app = create_app()
