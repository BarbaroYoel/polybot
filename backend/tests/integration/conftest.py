"""Shared fixtures: an HTTP client over a fresh app, and a migrated temporary database."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.seed import seed_example_data
from app.adapters.db.session import create_engine, create_session_factory
from app.core.config import Settings
from app.core.dependencies import get_llm, get_stt, get_tts
from app.main import create_app
from tests.fakes.llm import FakeLlm
from tests.fakes.stt import FakeStt
from tests.fakes.tts import FakeTts

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


@pytest.fixture
def fake_llm() -> FakeLlm:
    """The `LlmPort` double the app uses: tests tune its deltas or make it fail."""
    return FakeLlm()


@pytest.fixture
def fake_stt() -> FakeStt:
    """The `SttPort` double the app uses: no engine, no audio leaving the request."""
    return FakeStt()


@pytest.fixture
def fake_tts() -> FakeTts:
    """The `TtsPort` double the app uses: the suite never runs the Piper binary."""
    return FakeTts()


@pytest.fixture
def api_client(
    database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    fake_llm: FakeLlm,
    fake_stt: FakeStt,
    fake_tts: FakeTts,
) -> Iterator[TestClient]:
    """A client whose app talks to the seeded temporary database and a fake tutor."""

    async def seed() -> None:
        async with session_factory() as session:
            await seed_example_data(session)
            await session.commit()

    asyncio.run(seed())
    app = create_app(Settings(database_url=database_url))
    # Production launches a Pi subprocess per turn; the suite never does (F3 S2).
    app.dependency_overrides[get_llm] = lambda: fake_llm
    app.dependency_overrides[get_tts] = lambda: fake_tts
    # Production loads Whistle on this machine's CPU; the suite never does (F4 S1).
    app.dependency_overrides[get_stt] = lambda: fake_stt
    with TestClient(app) as test_client:
        yield test_client
