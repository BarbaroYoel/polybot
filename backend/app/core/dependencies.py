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
from app.application.translation import TranslationService
from app.application.tutor import TutorService
from app.ports.llm import LlmPort


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


def get_llm(request: Request) -> LlmPort:
    """The tutor provider wired at startup (a Pi subprocess); tests override this dependency."""
    return request.app.state.llm


async def get_translation_service(
    session: AsyncSession = Depends(get_session),
    llm: LlmPort = Depends(get_llm),
) -> TranslationService:
    """The same provider as the tutor, asked for a translation instead of a turn (ADR-014)."""
    return TranslationService(
        conversations=SqlAlchemyConversationRepository(session),
        messages=SqlAlchemyMessageRepository(session),
        languages=SqlAlchemyLanguageRepository(session),
        llm=llm,
    )


async def get_tutor_service(
    session: AsyncSession = Depends(get_session),
    llm: LlmPort = Depends(get_llm),
) -> TutorService:
    return TutorService(
        conversations=SqlAlchemyConversationRepository(session),
        messages=SqlAlchemyMessageRepository(session),
        languages=SqlAlchemyLanguageRepository(session),
        llm=llm,
        # The stream outlives the request unit of work, so it commits as it goes (F3 S5).
        commit=session.commit,
        rollback=session.rollback,
    )
