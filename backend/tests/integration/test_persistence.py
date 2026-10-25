"""Persistence rules: the schema, the seed and the per-language isolation (S6-S8)."""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.conversations import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.adapters.db.languages import SqlAlchemyLanguageRepository
from app.adapters.db.models import LanguageRow, MessageRow
from app.adapters.db.seed import (
    CONVERSATION_EN_ROUTINE,
    CONVERSATION_FR_CAFE,
    LANGUAGE_ALEMAN,
    LANGUAGE_FRANCES,
    LANGUAGE_INGLES,
    seed_example_data,
)
from app.adapters.db.session import create_engine
from app.domain.entities import (
    CefrLevel,
    ConversationMode,
    NewConversation,
    NewLanguage,
)


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    async with session_factory() as session:
        summary = await seed_example_data(session)
        await session.commit()
    return summary


def test_migration_creates_the_language_conversation_and_message_tables(database_url: str) -> None:
    async def tables() -> set[str]:
        engine = create_engine(database_url)
        try:
            async with engine.connect() as connection:
                return set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
        finally:
            await engine.dispose()

    expected = {
        "languages",
        "conversations",
        "messages",
        "lesson_units",
        "lessons",
        "lesson_exercises",
        "lesson_vocabulary",
        "lesson_attempts",
    }
    assert expected <= asyncio.run(tables())


def test_seed_inserts_the_example_data_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> tuple[dict[str, int], dict[str, int], set[str]]:
        first = await _seed(session_factory)
        second = await _seed(session_factory)
        async with session_factory() as session:
            active = set(
                await session.scalars(
                    select(LanguageRow.code).where(LanguageRow.is_active.is_(True))
                )
            )
        return first, second, active

    first, second, active = asyncio.run(scenario())

    assert first == {
        "languages": 3,
        "conversations": 2,
        "messages": 7,
        "lessons": 12,
        "exercises": 36,
        "terms": 24,
    }
    assert second == {
        "languages": 0,
        "conversations": 0,
        "messages": 0,
        "lessons": 0,
        "exercises": 0,
        "terms": 0,
    }
    assert active == {"en"}, "exactly one language is active (docs/api-contract.md §3)"


def test_listing_languages_skips_archived_ones(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> tuple[list[str], set[str]]:
        await _seed(session_factory)
        async with session_factory() as session:
            repository = SqlAlchemyLanguageRepository(session)
            await repository.archive_language(LANGUAGE_FRANCES)
            await session.commit()
            listed = [language.code for language in await repository.list_languages()]
            archived = await repository.get_language(LANGUAGE_FRANCES)
        return listed, {archived.code, str(archived.archived), str(archived.is_active)}  # type: ignore[union-attr]

    listed, archived = asyncio.run(scenario())

    assert listed == ["en", "de"]
    assert archived == {"fr", "True", "False"}, "archiving is soft and clears the active flag"


def test_a_duplicate_language_code_is_rejected_by_the_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        await _seed(session_factory)
        async with session_factory() as session:
            repository = SqlAlchemyLanguageRepository(session)
            with pytest.raises(IntegrityError):
                await repository.add_language(
                    NewLanguage(code="fr", name="Francés", level=CefrLevel.B1)
                )
            await session.rollback()

    asyncio.run(scenario())


def test_conversations_of_one_language_never_include_another(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> tuple[list[str], list[str]]:
        await _seed(session_factory)
        async with session_factory() as session:
            repository = SqlAlchemyConversationRepository(session)
            english = [
                row.id for row in await repository.list_conversations(LANGUAGE_INGLES, limit=20)
            ]
            german = [
                row.id for row in await repository.list_conversations(LANGUAGE_ALEMAN, limit=20)
            ]
        return english, german

    english, german = asyncio.run(scenario())

    assert english == [CONVERSATION_EN_ROUTINE]
    assert german == []


def test_history_is_ordered_by_last_activity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> list[str]:
        await _seed(session_factory)
        async with session_factory() as session:
            repository = SqlAlchemyConversationRepository(session)
            created = await repository.add_conversation(
                NewConversation(
                    language_id=LANGUAGE_FRANCES, mode=ConversationMode.GUIDED, title="Nueva"
                )
            )
            await session.commit()
            listed = [
                row.id for row in await repository.list_conversations(LANGUAGE_FRANCES, limit=20)
            ]
        return listed, created.id  # type: ignore[return-value]

    listed, created_id = asyncio.run(scenario())  # type: ignore[misc]

    assert listed[0] == created_id, "the most recent activity comes first"
    assert CONVERSATION_FR_CAFE in listed


def test_a_conversation_reports_its_message_count_and_last_message_at(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario():
        await _seed(session_factory)
        async with session_factory() as session:
            return await SqlAlchemyConversationRepository(session).get_conversation(
                CONVERSATION_FR_CAFE
            )

    conversation = asyncio.run(scenario())

    assert conversation is not None
    assert conversation.message_count == 4
    assert conversation.last_message_at == datetime(2026, 10, 22, 10, 27)
    assert conversation.activity_at == conversation.last_message_at


def test_message_pages_cover_the_whole_thread_in_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> list[list[str]]:
        await _seed(session_factory)
        pages: list[list[str]] = []
        async with session_factory() as session:
            repository = SqlAlchemyMessageRepository(session)
            after = None
            while True:
                page = await repository.list_messages(CONVERSATION_FR_CAFE, limit=2, after=after)
                if not page:
                    return pages
                pages.append([message.content for message in page])
                after = (page[-1].created_at, page[-1].id)

    pages = asyncio.run(scenario())

    assert [len(page) for page in pages] == [2, 2]
    assert pages[0][0].startswith("¡Hola!"), "the thread reads oldest first"
    assert pages[1][-1] == "Bonjour ! Qu'est-ce que vous aimeriez prendre ?"


def test_deleting_a_conversation_removes_its_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> int:
        await _seed(session_factory)
        async with session_factory() as session:
            await SqlAlchemyConversationRepository(session).delete_conversation(
                CONVERSATION_FR_CAFE
            )
            await session.commit()
            return await session.scalar(
                select(func.count())
                .select_from(MessageRow)
                .where(MessageRow.conversation_id == CONVERSATION_FR_CAFE)
            )

    assert asyncio.run(scenario()) == 0
