"""Shared fixtures: an HTTP client over a fresh app, and a migrated temporary database."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.session import create_engine, create_session_factory
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A client over a freshly built app, with no database file behind it."""
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """A temporary SQLite database migrated with Alembic, so tests exercise the real schema."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'polybot-test.db'}"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


@pytest.fixture
def session_factory(database_url: str) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(database_url)
    yield create_session_factory(engine)
    asyncio.run(engine.dispose())
