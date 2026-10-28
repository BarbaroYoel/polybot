"""Read-only SQLAlchemy aggregates for Progreso (F6 S1–S4, S9; ADR-018).

Nothing here writes: the screen is derived from conversations, attempts, corrections and
vocabulary that earlier phases already stored. Every query filters by `language_id`, follows the
existing indexes and folds the aggregation in SQL instead of walking rows one by one (no N+1).
"""

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    ConversationRow,
    LessonAttemptAnswerRow,
    LessonAttemptRow,
    LessonExerciseAnswerRow,
    LessonExerciseRow,
    LessonRow,
    MessageCorrectionRow,
    MessageFeedbackRow,
    MessageRow,
    VocabularyItemRow,
)
from app.domain.entities import (
    ActivityCount,
    FrequentError,
    FrequentErrorKind,
    HistoryEntry,
    HistoryKind,
)


class SqlAlchemyProgressRepository:
    """`ProgressRepository` port over SQLAlchemy (F6 S3, S6; docs/architecture.md §3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def conversation_activity(self, language_id: str) -> ActivityCount:
        count, last_at = (
            await self._session.execute(
                select(
                    func.count(func.distinct(ConversationRow.id)),
                    func.max(MessageRow.created_at),
                )
                .select_from(ConversationRow)
                .join(MessageRow, MessageRow.conversation_id == ConversationRow.id)
                .where(ConversationRow.language_id == language_id)
            )
        ).one()
        # The join only keeps conversations with messages: an empty one is not a practice (S1).
        return ActivityCount(count=count or 0, last_at=last_at)

    async def weekly_conversation_count(self, language_id: str, *, since: datetime) -> int:
        count = await self._session.scalar(
            select(func.count(func.distinct(ConversationRow.id)))
            .select_from(ConversationRow)
            .join(MessageRow, MessageRow.conversation_id == ConversationRow.id)
            .where(
                ConversationRow.language_id == language_id,
                MessageRow.created_at >= since,
            )
        )
        return count or 0

    async def writing_activity(self, language_id: str) -> ActivityCount:
        count, last_at = (
            await self._session.execute(
                select(
                    func.count(LessonAttemptAnswerRow.id),
                    func.max(LessonAttemptRow.created_at),
                )
                .select_from(LessonAttemptAnswerRow)
                .join(
                    LessonAttemptRow,
                    LessonAttemptRow.id == LessonAttemptAnswerRow.attempt_id,
                )
                .where(LessonAttemptRow.language_id == language_id)
            )
        ).one()
        return ActivityCount(count=count or 0, last_at=last_at)

    async def vocabulary_activity(self, language_id: str) -> ActivityCount:
        count, last_at = (
            await self._session.execute(
                select(
                    func.count(VocabularyItemRow.id),
                    func.max(VocabularyItemRow.created_at),
                ).where(VocabularyItemRow.language_id == language_id)
            )
        ).one()
        return ActivityCount(count=count or 0, last_at=last_at)

    async def frequent_errors(self, language_id: str, *, limit: int) -> list[FrequentError]:
        corrections = (
            await self._session.execute(
                select(
                    MessageCorrectionRow.original,
                    MessageCorrectionRow.corrected,
                    func.count(MessageCorrectionRow.id),
                    func.max(MessageFeedbackRow.created_at),
                )
                .select_from(MessageCorrectionRow)
                .join(
                    MessageFeedbackRow,
                    MessageFeedbackRow.id == MessageCorrectionRow.feedback_id,
                )
                .join(MessageRow, MessageRow.id == MessageFeedbackRow.message_id)
                .join(ConversationRow, ConversationRow.id == MessageRow.conversation_id)
                .where(ConversationRow.language_id == language_id)
                .group_by(MessageCorrectionRow.original, MessageCorrectionRow.corrected)
                .order_by(
                    func.count(MessageCorrectionRow.id).desc(),
                    func.max(MessageFeedbackRow.created_at).desc(),
                )
                .limit(limit)
            )
        ).all()

        # The first accepted answer of the exercise is the expected one (F5 S8); no model is asked.
        first_answers = (
            select(
                LessonExerciseAnswerRow.exercise_id.label("exercise_id"),
                LessonExerciseAnswerRow.answer.label("expected"),
            )
            .where(LessonExerciseAnswerRow.position == 0)
            .subquery()
        )
        lesson_answers = (
            await self._session.execute(
                select(
                    LessonExerciseRow.prompt,
                    LessonAttemptAnswerRow.answer,
                    first_answers.c.expected,
                    func.count(LessonAttemptAnswerRow.id),
                    func.max(LessonAttemptRow.created_at),
                )
                .select_from(LessonAttemptAnswerRow)
                .join(
                    LessonAttemptRow,
                    LessonAttemptRow.id == LessonAttemptAnswerRow.attempt_id,
                )
                .join(
                    LessonExerciseRow,
                    LessonExerciseRow.id == LessonAttemptAnswerRow.exercise_id,
                )
                .join(first_answers, first_answers.c.exercise_id == LessonExerciseRow.id)
                .where(
                    LessonAttemptRow.language_id == language_id,
                    LessonAttemptAnswerRow.correct.is_(False),
                )
                .group_by(
                    LessonExerciseRow.prompt,
                    LessonAttemptAnswerRow.answer,
                    first_answers.c.expected,
                )
                .order_by(
                    func.count(LessonAttemptAnswerRow.id).desc(),
                    func.max(LessonAttemptRow.created_at).desc(),
                )
                .limit(limit)
            )
        ).all()

        errors = [
            FrequentError(
                kind=FrequentErrorKind.CORRECTION,
                prompt=None,
                original=original,
                expected=corrected,
                count=count,
                last_at=last_at,
            )
            for original, corrected, count, last_at in corrections
        ]
        errors.extend(
            FrequentError(
                kind=FrequentErrorKind.LESSON,
                prompt=prompt,
                original=answer,
                expected=expected,
                count=count,
                last_at=last_at,
            )
            for prompt, answer, expected, count, last_at in lesson_answers
        )

        # Both sources compete for the same top five: count first, newest occurrence second.
        # The first sort is a stable tiebreaker so the response is deterministic.
        errors.sort(key=lambda error: (error.kind.value, error.original, error.expected))
        errors.sort(key=lambda error: (error.count, error.last_at), reverse=True)
        return errors[:limit]

    async def history(self, language_id: str, *, limit: int) -> list[HistoryEntry]:
        attempts = (
            await self._session.execute(
                select(
                    LessonAttemptRow.id,
                    LessonRow.title,
                    LessonAttemptRow.created_at,
                    func.coalesce(
                        func.sum(case((LessonAttemptAnswerRow.correct.is_(True), 1), else_=0)),
                        0,
                    ),
                    func.count(LessonAttemptAnswerRow.id),
                )
                .select_from(LessonAttemptRow)
                .join(LessonRow, LessonRow.id == LessonAttemptRow.lesson_id)
                .outerjoin(
                    LessonAttemptAnswerRow,
                    LessonAttemptAnswerRow.attempt_id == LessonAttemptRow.id,
                )
                .where(LessonAttemptRow.language_id == language_id)
                .group_by(LessonAttemptRow.id, LessonRow.title, LessonAttemptRow.created_at)
                .order_by(LessonAttemptRow.created_at.desc(), LessonAttemptRow.id.desc())
                .limit(limit)
            )
        ).all()

        conversations = (
            await self._session.execute(
                select(
                    ConversationRow.id,
                    ConversationRow.title,
                    func.max(MessageRow.created_at),
                    func.count(MessageRow.id),
                )
                .select_from(ConversationRow)
                .join(MessageRow, MessageRow.conversation_id == ConversationRow.id)
                .where(ConversationRow.language_id == language_id)
                .group_by(ConversationRow.id, ConversationRow.title)
                .order_by(
                    func.max(MessageRow.created_at).desc(),
                    ConversationRow.id.desc(),
                )
                .limit(limit)
            )
        ).all()

        entries = [
            HistoryEntry(
                kind=HistoryKind.LESSON,
                id=attempt_id,
                title=title,
                at=at,
                correct=int(correct),
                total=int(total),
                message_count=None,
            )
            for attempt_id, title, at, correct, total in attempts
        ]
        entries.extend(
            HistoryEntry(
                kind=HistoryKind.CONVERSATION,
                id=conversation_id,
                title=title,
                at=at,
                correct=None,
                total=None,
                message_count=int(message_count),
            )
            for conversation_id, title, at, message_count in conversations
        )

        # One queue: the newest practice or lesson, whichever happened last (S4).
        entries.sort(key=lambda entry: (entry.at, entry.id), reverse=True)
        return entries[:limit]
