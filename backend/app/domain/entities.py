"""Pure domain entities (docs/architecture.md §3: `domain/` imports no infrastructure)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CefrLevel(StrEnum):
    """Language level shown as a badge, never as a selector (ADR-008)."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ConversationMode(StrEnum):
    """Conversation modes of desing.md §7."""

    FREE = "free"
    GUIDED = "guided"
    ROLEPLAY = "roleplay"
    EXERCISE = "exercise"
    LIVE_VOICE = "live_voice"


class MessageAuthor(StrEnum):
    TUTOR = "tutor"
    USER = "user"


class MessageStatus(StrEnum):
    SENT = "sent"
    STREAMING = "streaming"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WeeklyGoal:
    conversations: int = 7
    minutes: int = 90


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    id: str
    code: str
    name: str
    level: CefrLevel
    explanation_language: str
    is_active: bool
    archived: bool
    weekly_goal: WeeklyGoal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Conversation:
    id: str
    language_id: str
    mode: ConversationMode
    title: str
    message_count: int
    last_message_at: datetime | None
    created_at: datetime

    @property
    def activity_at(self) -> datetime:
        """What the history is ordered by: the last message, or the creation when there is none."""
        return self.last_message_at or self.created_at


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    conversation_id: str
    author: MessageAuthor
    content: str
    translation: str | None
    status: MessageStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewLanguage:
    code: str
    name: str
    level: CefrLevel
    explanation_language: str = "es"
    weekly_goal: WeeklyGoal = WeeklyGoal()


@dataclass(frozen=True, slots=True)
class NewConversation:
    language_id: str
    mode: ConversationMode
    title: str


@dataclass(frozen=True, slots=True)
class NewMessage:
    conversation_id: str
    author: MessageAuthor
    content: str
    status: MessageStatus = MessageStatus.SENT
    translation: str | None = None
    idempotency_key: str | None = None


class LessonUnitKind(StrEnum):
    """The unit kinds of desing.md §6.2, in catalog order."""

    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    PRONUNCIATION = "pronunciation"
    LISTENING = "listening"
    SITUATIONAL = "situational"


class LessonStatus(StrEnum):
    """Derived from the stored attempts, never set by hand (F5 S5).

    `pending` means no attempt yet, `in_progress` an attempt with something still wrong and
    `completed` an attempt where every answer was right.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class LessonUnit:
    id: str
    language_id: str
    kind: LessonUnitKind
    title: str
    description: str
    position: int


@dataclass(frozen=True, slots=True)
class Lesson:
    id: str
    unit_id: str
    language_id: str
    title: str
    difficulty: CefrLevel
    estimated_minutes: int
    intro: str
    position: int


@dataclass(frozen=True, slots=True)
class LessonExercise:
    """One activity: write the phrase in the practised language (F5 S8).

    `accepted_answers` is ordered: the first one is what the API shows as the expected answer
    when the student misses, and all of them are accepted by the deterministic comparison.
    """

    id: str
    lesson_id: str
    position: int
    prompt: str
    accepted_answers: Sequence[str]
    explanation: str

    @property
    def expected(self) -> str:
        return self.accepted_answers[0]


@dataclass(frozen=True, slots=True)
class LessonAnswer:
    """One answer of one attempt, and whether the deterministic comparison accepted it."""

    exercise_id: str
    answer: str
    correct: bool


@dataclass(frozen=True, slots=True)
class LessonAttempt:
    """A finished practice of one lesson (F5 S2). Stored now so F6 can read it later (S7)."""

    id: str
    lesson_id: str
    language_id: str
    answers: Sequence[LessonAnswer]
    feedback: str | None
    created_at: datetime

    @property
    def correct(self) -> int:
        return sum(1 for answer in self.answers if answer.correct)

    @property
    def total(self) -> int:
        return len(self.answers)

    @property
    def completed(self) -> bool:
        """A lesson is done when nothing is left wrong: no invented score threshold (S5)."""
        return self.total > 0 and self.correct == self.total


@dataclass(frozen=True, slots=True)
class LessonTerm:
    """One key term of a lesson, returned as the «vocabulario nuevo» of its result (S2)."""

    term: str
    translation: str
    note: str | None


class PlanSessionState(StrEnum):
    """State of one session of a plan, derived from that lesson's real attempts (F5 S3, S5).

    The three values are the ones `desing.md` §6.3 shows («pendiente, en curso, completada») and
    match `LessonStatus`: a session is only as advanced as the lesson it opens.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class StudyPlan:
    """The plan the user asked for one language (F5 S3). The goal is fixed at creation (S4)."""

    id: str
    language_id: str
    goal: str
    frequency: int
    daily_minutes: int
    created_at: datetime
    adjusted_at: datetime | None


@dataclass(frozen=True, slots=True)
class NewStudyPlan:
    """A plan to create: what the user asked for, before its schedule is generated (S3)."""

    language_id: str
    goal: str
    frequency: int
    daily_minutes: int


@dataclass(frozen=True, slots=True)
class PlanSession:
    """One session of a plan's schedule: a lesson placed in a week and a position (F5 S3)."""

    id: str
    plan_id: str
    lesson_id: str
    week: int
    position: int


@dataclass(frozen=True, slots=True)
class NewPlanSession:
    """One session to write when the schedule is generated or regenerated (F5 S4)."""

    lesson_id: str
    week: int
    position: int
