"""Request-scoped dependencies and the composition root.

This module is the only place that wires concrete adapters into the application services;
`api/` asks for a service, never for a SQLAlchemy repository.
"""

from collections.abc import AsyncIterator

from fastapi import Depends, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.conversations import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.adapters.db.languages import SqlAlchemyLanguageRepository
from app.adapters.db.lessons import (
    SqlAlchemyLessonAttemptRepository,
    SqlAlchemyLessonRepository,
)
from app.adapters.db.plans import SqlAlchemyStudyPlanRepository
from app.adapters.db.progress import SqlAlchemyProgressRepository
from app.application.blocks import BlockService
from app.application.conversations import ConversationService
from app.application.interpreter import InterpreterService
from app.application.languages import LanguageService
from app.application.lessons import LessonService
from app.application.plans import PlanService
from app.application.progress import ProgressService
from app.application.translation import TranslationService
from app.application.tutor import TutorService
from app.application.voice import VoiceService
from app.ports.llm import LlmPort
from app.ports.stt import SttPort
from app.ports.tts import TtsPort


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


def get_stt(request: Request) -> SttPort:
    """The speech-to-text engine wired at startup (Whistle, F4 S1); tests override this."""
    return request.app.state.stt


def get_tts(request: Request) -> TtsPort:
    """The speech engine wired at startup (Piper, F4 S4); tests override this."""
    return request.app.state.tts


async def get_voice_service(
    stt: SttPort = Depends(get_stt),
    tts: TtsPort = Depends(get_tts),
) -> VoiceService:
    """Voice needs no database: the audio is transcribed or synthesized and dropped (S7)."""
    return VoiceService(stt=stt, tts=tts)


def get_interpreter_service(
    stt: SttPort = Depends(get_stt),
    llm: LlmPort = Depends(get_llm),
) -> InterpreterService:
    """The live interpreter shares the STT and LLM ports; the session itself is ephemeral (P2)."""
    return InterpreterService(stt=stt, llm=llm)


def get_ws_stt(websocket: WebSocket) -> SttPort:
    """The STT wired at startup, read from a WebSocket (the HTTP `Request` is not available)."""
    return websocket.app.state.stt


def get_ws_llm(websocket: WebSocket) -> LlmPort:
    """The LLM wired at startup, read from a WebSocket."""
    return websocket.app.state.llm


def get_ws_interpreter_service(
    stt: SttPort = Depends(get_ws_stt),
    llm: LlmPort = Depends(get_ws_llm),
) -> InterpreterService:
    return InterpreterService(stt=stt, llm=llm)


async def get_block_service(
    session: AsyncSession = Depends(get_session),
) -> BlockService:
    """Answering a drill needs the stored block, not the model: grading is deterministic."""
    return BlockService(
        conversations=SqlAlchemyConversationRepository(session),
        messages=SqlAlchemyMessageRepository(session),
    )


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


async def get_lesson_service(
    session: AsyncSession = Depends(get_session),
    llm: LlmPort = Depends(get_llm),
) -> LessonService:
    """Grading is deterministic; the provider only writes the closing comment (F5 S8)."""
    return LessonService(
        lessons=SqlAlchemyLessonRepository(session),
        attempts=SqlAlchemyLessonAttemptRepository(session),
        languages=SqlAlchemyLanguageRepository(session),
        llm=llm,
    )


async def get_plan_service(
    session: AsyncSession = Depends(get_session),
) -> PlanService:
    """Plans need no model: the schedule follows the catalog and the real attempts (F5 S3, S4)."""
    return PlanService(
        plans=SqlAlchemyStudyPlanRepository(session),
        lessons=SqlAlchemyLessonRepository(session),
        languages=SqlAlchemyLanguageRepository(session),
    )


async def get_progress_service(
    session: AsyncSession = Depends(get_session),
) -> ProgressService:
    """Progress needs no model: it reads conversations, attempts, corrections and vocabulary."""
    return ProgressService(
        progress=SqlAlchemyProgressRepository(session),
        lessons=SqlAlchemyLessonRepository(session),
        languages=SqlAlchemyLanguageRepository(session),
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
