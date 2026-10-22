"""Request-scoped dependencies and the composition root.

This module is the only place that wires concrete adapters into the application services;
`api/` asks for a service, never for a SQLAlchemy repository.
"""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


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
