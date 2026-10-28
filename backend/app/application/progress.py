"""Progress use case (docs/api-contract.md §3 "El progreso", F6 S1–S6).

The screen is a read-only projection: it composes the language profile, the lessons the user
already finished, three real activity signals, the most repeated mistakes and a mixed history.
Nothing is measured, estimated or written here (ADR-018); reading and listening are declared
unavailable instead of appearing as a zero. The level comes from the profile and is never changed
from this path (ADR-008).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.entities import (
    ActivityCount,
    CefrLevel,
    FrequentError,
    HistoryEntry,
    LanguageProfile,
    LessonStatus,
    SkillId,
    SkillProgress,
)
from app.domain.errors import InvalidTimezone, LanguageNotFound
from app.ports.repositories import LanguageRepository, LessonRepository, ProgressRepository

# The contract caps both lists; the repository does the limiting, not the serializer.
FREQUENT_ERRORS_LIMIT = 5
HISTORY_LIMIT = 10

# Always all five, in the order `desing.md` §6.5 lists them (F6 S2).
SKILL_ORDER: tuple[SkillId, ...] = (
    SkillId.CONVERSATION,
    SkillId.WRITING,
    SkillId.VOCABULARY,
    SkillId.READING,
    SkillId.LISTENING,
)


def week_start(tz: str, *, now: datetime | None = None) -> datetime:
    """The Monday 00:00 of the caller's timezone, as naive UTC for storage comparisons (F6 S1).

    The week starts on Monday. An unknown IANA zone is a domain failure, never a silent fallback to
    UTC: the caller asked for a window and gets either that window or an actionable error.
    `now` exists for tests; production uses the current UTC instant.
    """
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidTimezone(tz) from exc

    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    local = instant.astimezone(zone)
    monday = local.date() - timedelta(days=local.weekday())
    # `zoneinfo` resolves the offset of that local date, including a DST boundary, and the result
    # is stored the way every other date is: naive UTC.
    monday_local = datetime.combine(monday, time.min, tzinfo=zone)
    return monday_local.astimezone(UTC).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    """The summary of the active language: what it is and how much was practised (F6 S1).

    `level` is the stored level, not a measurement (S5); `weekly_conversations` counts distinct
    conversations since the local Monday of the request and `target` is the profile's goal.
    """

    level: CefrLevel
    lessons_completed: int
    lessons_total: int
    conversations: int
    weekly_conversations: int
    weekly_target: int


@dataclass(frozen=True, slots=True)
class ProgressView:
    """Everything `GET /progress` returns, already composed by language (F6 S1–S4, S6)."""

    language: LanguageProfile
    summary: ProgressSummary
    skills: Sequence[SkillProgress]
    frequent_errors: Sequence[FrequentError]
    history: Sequence[HistoryEntry]


class ProgressService:
    def __init__(
        self,
        *,
        progress: ProgressRepository,
        lessons: LessonRepository,
        languages: LanguageRepository,
    ) -> None:
        self._progress = progress
        self._lessons = lessons
        self._languages = languages

    async def get_progress(self, language_id: str, *, tz: str = "UTC") -> ProgressView:
        language = await self._languages.get_language(language_id)
        if language is None:
            # An unknown language is a 404, never an empty dashboard that hides the mistake (S6).
            raise LanguageNotFound(language_id)

        since = week_start(tz)
        lessons = await self._lessons.list_lessons(language_id)
        # Reuse the F5 derivation: a lesson is complete when an attempt left nothing wrong (S1).
        statuses = await self._lessons.lesson_statuses(language_id)
        completed = sum(
            1 for lesson in lessons if statuses.get(lesson.id) is LessonStatus.COMPLETED
        )

        conversations = await self._progress.conversation_activity(language_id)
        weekly_conversations = await self._progress.weekly_conversation_count(
            language_id, since=since
        )
        writing = await self._progress.writing_activity(language_id)
        vocabulary = await self._progress.vocabulary_activity(language_id)

        return ProgressView(
            language=language,
            summary=ProgressSummary(
                level=language.level,
                lessons_completed=completed,
                lessons_total=len(lessons),
                conversations=conversations.count,
                weekly_conversations=weekly_conversations,
                weekly_target=language.weekly_goal.conversations,
            ),
            skills=self._skills(
                conversation=conversations,
                writing=writing,
                vocabulary=vocabulary,
            ),
            frequent_errors=await self._progress.frequent_errors(
                language_id, limit=FREQUENT_ERRORS_LIMIT
            ),
            history=await self._progress.history(language_id, limit=HISTORY_LIMIT),
        )

    @staticmethod
    def _skills(
        *,
        conversation: ActivityCount,
        writing: ActivityCount,
        vocabulary: ActivityCount,
    ) -> list[SkillProgress]:
        """The five skills in contract order; the last two stay unavailable, not zero (F6 S2)."""
        available = {
            SkillId.CONVERSATION: conversation,
            SkillId.WRITING: writing,
            SkillId.VOCABULARY: vocabulary,
        }
        skills: list[SkillProgress] = []
        for skill_id in SKILL_ORDER:
            activity = available.get(skill_id)
            if activity is None:
                skills.append(SkillProgress(id=skill_id, available=False, count=None, last_at=None))
                continue
            skills.append(
                SkillProgress(
                    id=skill_id,
                    available=True,
                    count=activity.count,
                    last_at=activity.last_at,
                )
            )
        return skills
