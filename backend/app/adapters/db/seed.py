"""Example data for local development: the same languages and conversations the F1 shell shows.

`uv run python -m app.adapters.db.seed`. The seed is idempotent: if any language exists it does
nothing, so running it twice never duplicates history.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import ConversationRow, LanguageRow, MessageRow
from app.adapters.db.session import create_engine, create_session_factory
from app.core.config import Settings

logger = logging.getLogger(__name__)

LANGUAGE_INGLES = "7d1c5a20-9b3e-4f41-8d2a-1c0e5b6f7a01"
LANGUAGE_FRANCES = "7d1c5a20-9b3e-4f41-8d2a-1c0e5b6f7a02"
LANGUAGE_ALEMAN = "7d1c5a20-9b3e-4f41-8d2a-1c0e5b6f7a03"

CONVERSATION_EN_ROUTINE = "9a4b6c81-2d3e-4a5b-9c7d-0e1f2a3b4c01"
CONVERSATION_FR_CAFE = "9a4b6c81-2d3e-4a5b-9c7d-0e1f2a3b4c02"

_TUTOR_GREETING = (
    "¡Hola! Soy tu tutor de idiomas. Podemos conversar, practicar vocabulario, "
    "corregir tus frases o simular situaciones de la vida real.\n\n"
    "¿Qué te gustaría hacer hoy?"
)

_FRENCH_CAFE_MESSAGES: list[dict[str, Any]] = [
    {"id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c01", "author": "tutor", "content": _TUTOR_GREETING},
    {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c02",
        "author": "user",
        "content": "Me gustaría practicar una conversación en un café en francés.",
    },
    {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c03",
        "author": "tutor",
        "content": (
            "¡Perfecto! Vamos a practicar una conversación en un café. Te hablaré en francés "
            "y te ayudaré con correcciones y sugerencias.\n\n¿Estás listo? ☕"
        ),
    },
    {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c04",
        "author": "tutor",
        "content": "Bonjour ! Qu'est-ce que vous aimeriez prendre ?",
        "translation": "¡Buenos días! ¿Qué le gustaría tomar?",
    },
]

_ENGLISH_ROUTINE_MESSAGES: list[dict[str, Any]] = [
    {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c05",
        "author": "tutor",
        "content": "Hi! Ready to practise? Tell me about your day so far.",
    },
    {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c06",
        "author": "user",
        "content": "I woke up early and went for a run before work.",
    },
    {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c07",
        "author": "tutor",
        "content": (
            "Nice. Small fix: “I woke up early and went for a run before work” is correct "
            "— try adding why you ran."
        ),
    },
]

_LANGUAGES: list[dict[str, Any]] = [
    {
        "id": LANGUAGE_INGLES,
        "code": "en",
        "name": "Inglés",
        "level": "B1",
        "is_active": True,
        "created_at": datetime(2026, 10, 20, 9, 0, 0),
    },
    {
        "id": LANGUAGE_FRANCES,
        "code": "fr",
        "name": "Francés",
        "level": "A1",
        "is_active": False,
        "created_at": datetime(2026, 10, 20, 9, 5, 0),
    },
    {
        "id": LANGUAGE_ALEMAN,
        "code": "de",
        "name": "Alemán",
        "level": "B2",
        "is_active": False,
        "created_at": datetime(2026, 10, 20, 9, 10, 0),
    },
]


def _add_conversation(
    session: AsyncSession,
    *,
    conversation_id: str,
    language_id: str,
    title: str,
    messages: list[dict[str, Any]],
    started_at: datetime,
) -> ConversationRow:
    """Build one conversation and its messages. The caller flushes in dependency order."""
    timestamps = [started_at]
    message_rows: list[MessageRow] = []
    for index, message in enumerate(messages, start=1):
        created_at = datetime(
            started_at.year,
            started_at.month,
            started_at.day,
            started_at.hour,
            started_at.minute + index,
            0,
        )
        timestamps.append(created_at)
        message_rows.append(
            MessageRow(
                id=message["id"],
                conversation_id=conversation_id,
                author=message["author"],
                content=message["content"],
                translation=message.get("translation"),
                status="sent",
                created_at=created_at,
            )
        )

    conversation = ConversationRow(
        id=conversation_id,
        language_id=language_id,
        mode="free",
        title=title,
        message_count=len(messages),
        last_message_at=timestamps[-1],
        created_at=started_at,
    )
    session.add(conversation)
    session.add_all(message_rows)
    return conversation


async def seed_example_data(session: AsyncSession) -> dict[str, int]:
    """Insert the example languages, conversations and messages. Returns the inserted counts."""
    existing = await session.scalar(select(func.count()).select_from(LanguageRow))
    if existing:
        return {"languages": 0, "conversations": 0, "messages": 0}

    for language in _LANGUAGES:
        session.add(
            LanguageRow(
                explanation_language="es",
                archived=False,
                weekly_goal_conversations=7,
                weekly_goal_minutes=90,
                **language,
            )
        )

    # Without ORM relationships SQLAlchemy does not know the insert order between tables,
    # so the parents are flushed first: languages, then conversations, then messages.
    await session.flush()

    _add_conversation(
        session,
        conversation_id=CONVERSATION_FR_CAFE,
        language_id=LANGUAGE_FRANCES,
        title="En un café",
        messages=_FRENCH_CAFE_MESSAGES,
        started_at=datetime(2026, 10, 22, 10, 23, 0),
    )
    _add_conversation(
        session,
        conversation_id=CONVERSATION_EN_ROUTINE,
        language_id=LANGUAGE_INGLES,
        title="Rutina diaria",
        messages=_ENGLISH_ROUTINE_MESSAGES,
        started_at=datetime(2026, 10, 22, 9, 11, 0),
    )

    await session.flush()
    return {
        "languages": len(_LANGUAGES),
        "conversations": 2,
        "messages": len(_FRENCH_CAFE_MESSAGES) + len(_ENGLISH_ROUTINE_MESSAGES),
    }


async def main() -> None:
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session:
            summary = await seed_example_data(session)
            await session.commit()
    finally:
        await engine.dispose()

    if summary["languages"]:
        logger.info(
            "Seeded %(languages)d languages, %(conversations)d conversations "
            "and %(messages)d messages.",
            summary,
        )
    else:
        logger.info("The database already has languages; nothing was seeded.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
