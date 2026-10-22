"""Request-scoped dependencies and the composition root.

This module is the only place that wires concrete adapters into the application services;
`api/` asks for a service, never for a SQLAlchemy repository.
"""

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.conversations import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.adapters.db.languages import SqlAlchemyLanguageRepository
from app.application.conversations import ConversationService
from app.application.languages import LanguageService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One transaction per request: committed when the handler succeeds, rolled back otherwise."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_language_service(
    session: AsyncSession = Depends(get_session),
) -> LanguageService:
    return LanguageService(SqlAlchemyLanguageRepository(session))


async def get_conversation_service(
    session: AsyncSession = Depends(get_session),
) -> ConversationService:
    return ConversationService(
        conversations=SqlAlchemyConversationRepository(session),
        messages=SqlAlchemyMessageRepository(session),
        languages=SqlAlchemyLanguageRepository(session),
    )
