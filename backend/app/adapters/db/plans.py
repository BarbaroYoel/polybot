"""SQLAlchemy adapter for study plans and their schedule (F5 S3, S4, S6)."""

from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import PlanSessionRow, StudyPlanRow
from app.core.dates import utc_now
from app.domain.entities import NewPlanSession, NewStudyPlan, PlanSession, StudyPlan


def _to_plan(row: StudyPlanRow) -> StudyPlan:
    return StudyPlan(
        id=row.id,
        language_id=row.language_id,
        goal=row.goal,
        frequency=row.frequency,
        daily_minutes=row.daily_minutes,
        created_at=row.created_at,
        adjusted_at=row.adjusted_at,
    )


def _to_session(row: PlanSessionRow) -> PlanSession:
    return PlanSession(
        id=row.id,
        plan_id=row.plan_id,
        lesson_id=row.lesson_id,
        week=row.week,
        position=row.position,
    )


class SqlAlchemyStudyPlanRepository:
    """`StudyPlanRepository` port over SQLAlchemy (docs/architecture.md §3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_plan(self, language_id: str) -> StudyPlan | None:
        row = await self._session.scalar(
            select(StudyPlanRow).where(StudyPlanRow.language_id == language_id)
        )
        return _to_plan(row) if row else None

    async def get_plan_by_id(self, plan_id: str) -> StudyPlan | None:
        row = await self._session.get(StudyPlanRow, plan_id)
        return _to_plan(row) if row else None

    async def add_plan(self, draft: NewStudyPlan, schedule: Sequence[NewPlanSession]) -> StudyPlan:
        row = StudyPlanRow(
            id=str(uuid4()),
            language_id=draft.language_id,
            goal=draft.goal,
            frequency=draft.frequency,
            daily_minutes=draft.daily_minutes,
            created_at=utc_now(),
            adjusted_at=None,
        )
        self._session.add(row)
        # Without ORM relationships the plan must exist before its sessions reference it.
        await self._session.flush()
        await self._write_sessions(row.id, schedule)
        return _to_plan(row)

    async def adjust_plan(
        self,
        plan_id: str,
        *,
        frequency: int,
        daily_minutes: int,
        schedule: Sequence[NewPlanSession],
    ) -> StudyPlan:
        row = await self._session.get(StudyPlanRow, plan_id)
        if row is None:
            raise LookupError(plan_id)

        # The goal is not adjustable: it is what the user asked for when the plan was created.
        row.frequency = frequency
        row.daily_minutes = daily_minutes
        row.adjusted_at = utc_now()
        await self._session.flush()
        await self._write_sessions(plan_id, schedule)
        return _to_plan(row)

    async def list_sessions(self, plan_id: str) -> list[PlanSession]:
        rows = await self._session.scalars(
            select(PlanSessionRow)
            .where(PlanSessionRow.plan_id == plan_id)
            .order_by(PlanSessionRow.week, PlanSessionRow.position, PlanSessionRow.id)
        )
        return [_to_session(row) for row in rows]

    async def _write_sessions(self, plan_id: str, schedule: Sequence[NewPlanSession]) -> None:
        """Replace the plan's whole schedule: the old sessions go, the new ones arrive.

        Both statements run inside the request's transaction, so no reader sees a plan with half
        a schedule or a schedule without its plan (F5 S4).
        """
        await self._session.execute(delete(PlanSessionRow).where(PlanSessionRow.plan_id == plan_id))
        for draft in schedule:
            self._session.add(
                PlanSessionRow(
                    id=str(uuid4()),
                    plan_id=plan_id,
                    lesson_id=draft.lesson_id,
                    week=draft.week,
                    position=draft.position,
                )
            )
        await self._session.flush()
