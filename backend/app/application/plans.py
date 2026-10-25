"""Study plan use cases (docs/api-contract.md §3 "Aprendizaje", F5 S3, S4, S6).

The schedule is a projection of the catalog: one session per lesson, `frequency` of them per week,
in catalog order. It is generated once at creation and regenerated only when the user adjusts the
plan; nothing here recalculates on read. A session's state is never stored: it is read from the
lesson's real attempts every time the plan is served (S5).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.entities import (
    Lesson,
    LessonStatus,
    NewPlanSession,
    NewStudyPlan,
    PlanSession,
    PlanSessionState,
    StudyPlan,
)
from app.domain.errors import LanguageNotFound, PlanAlreadyExists, PlanNotFound
from app.ports.repositories import LanguageRepository, LessonRepository, StudyPlanRepository


@dataclass(frozen=True, slots=True)
class PlanSessionEntry:
    """One session as the plan shows it: the lesson it opens and the state of its attempts."""

    session: PlanSession
    lesson_title: str
    status: PlanSessionState


@dataclass(frozen=True, slots=True)
class PlanView:
    plan: StudyPlan
    weeks: int
    sessions: Sequence[PlanSessionEntry]

    @property
    def next_session(self) -> PlanSessionEntry | None:
        """What «Continuar plan» opens: the first session that is not done, in schedule order."""
        return next(
            (entry for entry in self.sessions if entry.status is not PlanSessionState.COMPLETED),
            None,
        )


def build_schedule(lessons: Sequence[Lesson], frequency: int) -> list[NewPlanSession]:
    """Spread the catalog over weeks, `frequency` sessions per week (F5 S3).

    Deterministic on purpose: the same catalog and the same frequency always produce the same
    schedule, which is what makes adjusting a plan reproducible.
    """
    return [
        NewPlanSession(
            lesson_id=lesson.id,
            week=index // frequency + 1,
            position=index % frequency,
        )
        for index, lesson in enumerate(lessons)
    ]


def session_state(status: LessonStatus | None) -> PlanSessionState:
    """A session is only as advanced as the attempts of its lesson (F5 S5).

    No attempt yet is `pending`; an attempt that left something wrong is `in_progress`; a perfect
    attempt is `completed`. The lesson repository already folds several attempts into one state.
    """
    return PlanSessionState.PENDING if status is None else PlanSessionState(status.value)


class PlanService:
    def __init__(
        self,
        *,
        plans: StudyPlanRepository,
        lessons: LessonRepository,
        languages: LanguageRepository,
    ) -> None:
        self._plans = plans
        self._lessons = lessons
        self._languages = languages

    async def get_plan(self, language_id: str) -> PlanView | None:
        """The plan of one language, or `None` when it has none: a missing plan is not an error."""
        await self._require_language(language_id)
        plan = await self._plans.get_plan(language_id)
        return None if plan is None else await self._view(plan)

    async def create_plan(
        self,
        *,
        language_id: str,
        goal: str,
        frequency: int,
        daily_minutes: int,
    ) -> PlanView:
        await self._require_language(language_id)
        if await self._plans.get_plan(language_id) is not None:
            # One plan per language: it is adjusted, not duplicated (S4).
            raise PlanAlreadyExists(language_id)

        plan = await self._plans.add_plan(
            NewStudyPlan(
                language_id=language_id,
                goal=goal,
                frequency=frequency,
                daily_minutes=daily_minutes,
            ),
            schedule=build_schedule(await self._lessons.list_lessons(language_id), frequency),
        )
        return await self._view(plan)

    async def adjust_plan(
        self,
        plan_id: str,
        *,
        frequency: int | None = None,
        daily_minutes: int | None = None,
    ) -> PlanView:
        """The user asked for the adjustment, so the schedule is recalculated right here (S4)."""
        plan = await self._plans.get_plan_by_id(plan_id)
        if plan is None:
            raise PlanNotFound(plan_id)
        if frequency is None and daily_minutes is None:
            # An empty body changes nothing: no recalculation the user did not ask for.
            return await self._view(plan)

        new_frequency = plan.frequency if frequency is None else frequency
        adjusted = await self._plans.adjust_plan(
            plan_id,
            frequency=new_frequency,
            daily_minutes=plan.daily_minutes if daily_minutes is None else daily_minutes,
            schedule=build_schedule(
                await self._lessons.list_lessons(plan.language_id), new_frequency
            ),
        )
        return await self._view(adjusted)

    async def _require_language(self, language_id: str) -> None:
        if await self._languages.get_language(language_id) is None:
            # An unknown language is a 404, never a plan created against nothing (S6).
            raise LanguageNotFound(language_id)

    async def _view(self, plan: StudyPlan) -> PlanView:
        lessons = await self._lessons.list_lessons(plan.language_id)
        titles = {lesson.id: lesson.title for lesson in lessons}
        statuses = await self._lessons.lesson_statuses(plan.language_id)
        sessions = [
            PlanSessionEntry(
                session=session,
                lesson_title=titles[session.lesson_id],
                status=session_state(statuses.get(session.lesson_id)),
            )
            for session in await self._plans.list_sessions(plan.id)
            # The foreign key cascades on delete, so a session always has its lesson; the guard
            # keeps a lesson of another language from ever being shown in this plan (S6).
            if session.lesson_id in titles
        ]
        return PlanView(
            plan=plan,
            weeks=len({entry.session.week for entry in sessions}),
            sessions=sessions,
        )
