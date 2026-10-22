"""SQLAlchemy adapters: the only code that speaks SQL."""

from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import LanguageRow
from app.core.dates import utc_now
from app.domain.entities import CefrLevel, LanguageProfile, NewLanguage, WeeklyGoal


def _to_entity(row: LanguageRow) -> LanguageProfile:
    return LanguageProfile(
        id=row.id,
        code=row.code,
        name=row.name,
        level=CefrLevel(row.level),
        explanation_language=row.explanation_language,
        is_active=row.is_active,
        archived=row.archived,
        weekly_goal=WeeklyGoal(
            conversations=row.weekly_goal_conversations,
            minutes=row.weekly_goal_minutes,
        ),
        created_at=row.created_at,
    )


class SqlAlchemyLanguageRepository:
    """`LanguageRepository` port over SQLAlchemy (docs/architecture.md §3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_languages(self) -> list[LanguageProfile]:
        rows = await self._session.scalars(
            select(LanguageRow)
            .where(LanguageRow.archived.is_(False))
            .order_by(LanguageRow.created_at, LanguageRow.id)
        )
        return [_to_entity(row) for row in rows]

    async def get_language(self, language_id: str) -> LanguageProfile | None:
        row = await self._session.get(LanguageRow, language_id)
        return _to_entity(row) if row else None

    async def get_language_by_code(self, code: str) -> LanguageProfile | None:
        row = await self._session.scalar(select(LanguageRow).where(LanguageRow.code == code))
        return _to_entity(row) if row else None

    async def add_language(self, draft: NewLanguage) -> LanguageProfile:
        row = LanguageRow(
            id=str(uuid4()),
            code=draft.code,
            name=draft.name,
            level=draft.level.value,
            explanation_language=draft.explanation_language,
            is_active=False,
            archived=False,
            weekly_goal_conversations=draft.weekly_goal.conversations,
            weekly_goal_minutes=draft.weekly_goal.minutes,
            created_at=utc_now(),
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entity(row)

    async def update_language(
        self,
        language_id: str,
        *,
        level: CefrLevel | None = None,
        weekly_goal: WeeklyGoal | None = None,
        is_active: bool | None = None,
    ) -> LanguageProfile:
        row = await self._session.get(LanguageRow, language_id)
        if row is None:
            raise LookupError(language_id)

        if level is not None:
            row.level = level.value
        if weekly_goal is not None:
            row.weekly_goal_conversations = weekly_goal.conversations
            row.weekly_goal_minutes = weekly_goal.minutes
        if is_active is not None:
            if is_active:
                # One active language at a time (docs/api-contract.md §3).
                await self._session.execute(
                    update(LanguageRow)
                    .where(LanguageRow.id != language_id, LanguageRow.is_active.is_(True))
                    .values(is_active=False)
                )
            row.is_active = is_active

        await self._session.flush()
        return _to_entity(row)

    async def archive_language(self, language_id: str) -> None:
        row = await self._session.get(LanguageRow, language_id)
        if row is None:
            raise LookupError(language_id)
        row.archived = True
        row.is_active = False
        await self._session.flush()
