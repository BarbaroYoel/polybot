"""Request and response models. They mirror docs/api-contract.md §2 field by field."""

from collections.abc import Iterable, Mapping
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.application.lessons import (
    CatalogLesson,
    CatalogUnit,
    LessonCatalog,
    LessonDetail,
    LessonResult,
)
from app.application.pagination import Page
from app.application.plans import PlanSessionEntry, PlanView
from app.application.progress import ProgressSummary, ProgressView
from app.core.dates import to_iso
from app.domain.blocks import BlockKind, DrillAnswer, TurnBlock
from app.domain.entities import (
    CefrLevel,
    Conversation,
    ConversationMode,
    ExerciseKind,
    FrequentError,
    FrequentErrorKind,
    HistoryEntry,
    HistoryKind,
    LanguageProfile,
    LessonStatus,
    LessonTerm,
    LessonUnitKind,
    Message,
    MessageAuthor,
    MessageStatus,
    PlanSessionState,
    SkillId,
    SkillProgress,
)
from app.domain.feedback import MessageFeedback
from app.ports.llm import TurnFeedback


class WeeklyGoal(BaseModel):
    conversations: int = Field(default=7, ge=1, le=100)
    minutes: int = Field(default=90, ge=0, le=10_000)


class LanguageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
    name: str = Field(min_length=1, max_length=80)
    level: CefrLevel
    explanation_language: str = Field(default="es", min_length=2, max_length=8)
    weekly_goal: WeeklyGoal = Field(default_factory=WeeklyGoal)


class LanguageUpdate(BaseModel):
    level: CefrLevel | None = None
    weekly_goal: WeeklyGoal | None = None
    is_active: bool | None = None


class LanguageOut(BaseModel):
    id: str
    code: str
    name: str
    level: CefrLevel
    explanation_language: str
    is_active: bool
    archived: bool
    weekly_goal: WeeklyGoal
    created_at: str

    @classmethod
    def from_entity(cls, language: LanguageProfile) -> "LanguageOut":
        return cls(
            id=language.id,
            code=language.code,
            name=language.name,
            level=language.level,
            explanation_language=language.explanation_language,
            is_active=language.is_active,
            archived=language.archived,
            weekly_goal=WeeklyGoal(
                conversations=language.weekly_goal.conversations,
                minutes=language.weekly_goal.minutes,
            ),
            created_at=to_iso(language.created_at),
        )


class ConversationCreate(BaseModel):
    language_id: str = Field(min_length=1)
    mode: ConversationMode = ConversationMode.FREE
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


# Contract §5 will list the message limit; a Portuguese/Spanish turn fits comfortably in 4000 chars.
MessageContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]


class MessageCreate(BaseModel):
    content: MessageContent


# Contract §5: the text of a translation is bounded like a message; a selection is shorter.
TranslationText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
# ISO 639-1 (`fr`) or a regional variant (`pt-BR`).
LanguageCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=8)]


class TranslateRequest(BaseModel):
    """The stateless translation: a message or a fragment, with the direction the UI decided."""

    text: TranslationText
    source: LanguageCode | None = None
    target: LanguageCode


class TranslateOut(BaseModel):
    translation: str
    # The source used, or `null` when the caller did not send one and the provider detected it.
    detected_source: str | None


class CorrectionOut(BaseModel):
    """One correction card of a closing turn (F3 S7)."""

    original: str
    corrected: str
    explanation: str


class VocabularyOut(BaseModel):
    """One suggested term of the closing turn."""

    term: str
    translation: str
    note: str | None


class _CorrectionLike(Protocol):
    original: str
    corrected: str
    explanation: str


class _VocabularyLike(Protocol):
    term: str
    translation: str
    note: str | None


def _corrections(items: Iterable[_CorrectionLike]) -> list[CorrectionOut]:
    return [
        CorrectionOut(
            original=item.original, corrected=item.corrected, explanation=item.explanation
        )
        for item in items
    ]


def _vocabulary(items: Iterable[_VocabularyLike]) -> list[VocabularyOut]:
    return [
        VocabularyOut(term=item.term, translation=item.translation, note=item.note)
        for item in items
    ]


class MessageFeedbackOut(BaseModel):
    """`Message.feedback`: `null` for tutor messages and for user messages with no closing turn."""

    corrections: list[CorrectionOut]
    vocabulary: list[VocabularyOut]

    @classmethod
    def from_entity(cls, feedback: MessageFeedback) -> "MessageFeedbackOut":
        return cls(
            corrections=_corrections(feedback.corrections),
            vocabulary=_vocabulary(feedback.vocabulary),
        )

    @classmethod
    def from_turn_feedback(cls, feedback: TurnFeedback) -> "MessageFeedbackOut":
        """The closing events are emitted before the rows are read back, from the same drafts."""
        return cls(
            corrections=_corrections(feedback.corrections),
            vocabulary=_vocabulary(feedback.vocabulary),
        )


class PhraseBlockOut(BaseModel):
    """A sentence worth hearing again: the client synthesizes it with `/voice/speech` (ADR-020)."""

    id: str
    kind: Literal["phrase"]
    text: str


class DrillBlockOut(BaseModel):
    """One question for the student.

    `accepted_answers` and `explanation` are absent on purpose: the first would let a browser solve
    the exercise by reading the payload, the second usually gives the answer away (ADR-020).
    """

    id: str
    kind: Literal["drill"]
    prompt: str


BlockOut = Annotated[PhraseBlockOut | DrillBlockOut, Field(discriminator="kind")]


def blocks_out(blocks: Iterable[TurnBlock]) -> list[BlockOut]:
    """The public view of the stored blocks: no private field crosses this line."""
    return [
        PhraseBlockOut.model_validate(block.public())
        if block.kind is BlockKind.PHRASE
        else DrillBlockOut.model_validate(block.public())
        for block in blocks
    ]


class DrillAnswerRequest(BaseModel):
    """What the student typed for one drill; the API grades it, the client never sees the answer."""

    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class DrillAnswerOut(BaseModel):
    """The verdict of one drill. `expected` is only revealed after a miss (ADR-020)."""

    correct: bool
    expected: str | None
    explanation: str

    @classmethod
    def from_entity(cls, answer: DrillAnswer) -> "DrillAnswerOut":
        return cls(
            correct=answer.correct,
            expected=answer.expected,
            explanation=answer.explanation,
        )


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    author: MessageAuthor
    content: str
    translation: str | None
    status: MessageStatus
    feedback: MessageFeedbackOut | None = None
    blocks: list[BlockOut] = []
    created_at: str

    @classmethod
    def from_entity(cls, message: Message, feedback: MessageFeedback | None = None) -> "MessageOut":
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            author=message.author,
            content=message.content,
            translation=message.translation,
            status=message.status,
            feedback=MessageFeedbackOut.from_entity(feedback) if feedback is not None else None,
            blocks=blocks_out(message.blocks),
            created_at=to_iso(message.created_at),
        )


class ConversationOut(BaseModel):
    id: str
    language_id: str
    mode: ConversationMode
    title: str
    message_count: int
    last_message_at: str | None
    created_at: str

    @classmethod
    def from_entity(cls, conversation: Conversation) -> "ConversationOut":
        return cls(
            id=conversation.id,
            language_id=conversation.language_id,
            mode=conversation.mode,
            title=conversation.title,
            message_count=conversation.message_count,
            last_message_at=(
                to_iso(conversation.last_message_at) if conversation.last_message_at else None
            ),
            created_at=to_iso(conversation.created_at),
        )


class ConversationPage(BaseModel):
    items: list[ConversationOut]
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: Page[Conversation]) -> "ConversationPage":
        return cls(
            items=[ConversationOut.from_entity(row) for row in page.items],
            next_cursor=page.next_cursor,
        )


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: Page[Message],
        feedback: Mapping[str, MessageFeedback] | None = None,
    ) -> "MessagePage":
        """`feedback` arrives already fetched for the page: the schema never queries (no N+1)."""
        attached = feedback or {}
        return cls(
            items=[MessageOut.from_entity(row, attached.get(row.id)) for row in page.items],
            next_cursor=page.next_cursor,
        )


class ConversationDetailOut(ConversationOut):
    messages: MessagePage


class LessonSummaryOut(BaseModel):
    """One lesson as the catalog lists it: what it is, and the state its attempts give it (S1)."""

    id: str
    unit_id: str
    title: str
    difficulty: CefrLevel
    estimated_minutes: int
    position: int
    status: LessonStatus

    @classmethod
    def from_entry(cls, entry: CatalogLesson) -> "LessonSummaryOut":
        return cls(
            id=entry.lesson.id,
            unit_id=entry.lesson.unit_id,
            title=entry.lesson.title,
            difficulty=entry.lesson.difficulty,
            estimated_minutes=entry.lesson.estimated_minutes,
            position=entry.lesson.position,
            status=entry.status,
        )


class LessonUnitOut(BaseModel):
    id: str
    kind: LessonUnitKind
    title: str
    description: str
    position: int
    lessons: list[LessonSummaryOut]

    @classmethod
    def from_entry(cls, entry: CatalogUnit) -> "LessonUnitOut":
        return cls(
            id=entry.unit.id,
            kind=entry.unit.kind,
            title=entry.unit.title,
            description=entry.unit.description,
            position=entry.unit.position,
            lessons=[LessonSummaryOut.from_entry(lesson) for lesson in entry.lessons],
        )


class LessonCatalogOut(BaseModel):
    language_id: str
    language_name: str
    level: CefrLevel
    next_lesson: LessonSummaryOut | None
    units: list[LessonUnitOut]

    @classmethod
    def from_entity(cls, catalog: LessonCatalog) -> "LessonCatalogOut":
        return cls(
            language_id=catalog.language.id,
            language_name=catalog.language.name,
            level=catalog.language.level,
            next_lesson=(
                LessonSummaryOut.from_entry(catalog.next_lesson)
                if catalog.next_lesson is not None
                else None
            ),
            units=[LessonUnitOut.from_entry(unit) for unit in catalog.units],
        )


class LessonExerciseOut(BaseModel):
    """One exercise as the student sees it: the prompt and, for a choice, its options (ADR-021).

    The accepted answers never travel: on a `choice` the options include the right one, and the
    grading happens on the server.
    """

    id: str
    position: int
    prompt: str
    kind: ExerciseKind
    options: list[str]


class LessonDetailOut(BaseModel):
    id: str
    language_id: str
    unit_id: str
    unit_title: str
    unit_kind: LessonUnitKind
    title: str
    difficulty: CefrLevel
    estimated_minutes: int
    intro: str
    exercises: list[LessonExerciseOut]

    @classmethod
    def from_entity(cls, detail: LessonDetail) -> "LessonDetailOut":
        return cls(
            id=detail.lesson.id,
            language_id=detail.lesson.language_id,
            unit_id=detail.unit.id,
            unit_title=detail.unit.title,
            unit_kind=detail.unit.kind,
            title=detail.lesson.title,
            difficulty=detail.lesson.difficulty,
            estimated_minutes=detail.lesson.estimated_minutes,
            intro=detail.lesson.intro,
            exercises=[
                LessonExerciseOut(
                    id=exercise.id,
                    position=exercise.position,
                    prompt=exercise.prompt,
                    kind=exercise.kind,
                    options=list(exercise.options),
                )
                for exercise in detail.exercises
            ],
        )


class LessonAnswerIn(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=64)
    answer: str = Field(min_length=1, max_length=400)


class LessonSubmitIn(BaseModel):
    answers: list[LessonAnswerIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _one_answer_per_exercise(self) -> "LessonSubmitIn":
        ids = [answer.exercise_id for answer in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("cada ejercicio se responde una sola vez")
        return self


class LessonMistakeOut(BaseModel):
    exercise_id: str
    prompt: str
    answer: str
    expected: str
    explanation: str


class LessonTermOut(BaseModel):
    term: str
    translation: str
    note: str | None

    @classmethod
    def from_entity(cls, term: LessonTerm) -> "LessonTermOut":
        return cls(term=term.term, translation=term.translation, note=term.note)


class LessonResultOut(BaseModel):
    attempt_id: str
    lesson_id: str
    correct: int
    total: int
    completed: bool
    mistakes: list[LessonMistakeOut]
    vocabulary: list[LessonTermOut]
    feedback: str | None
    next_lesson: LessonSummaryOut | None

    @classmethod
    def from_entity(cls, result: LessonResult) -> "LessonResultOut":
        return cls(
            attempt_id=result.attempt.id,
            lesson_id=result.lesson.id,
            correct=result.attempt.correct,
            total=result.attempt.total,
            completed=result.attempt.completed,
            mistakes=[
                LessonMistakeOut(
                    exercise_id=mistake.exercise_id,
                    prompt=mistake.prompt,
                    answer=mistake.answer,
                    expected=mistake.expected,
                    explanation=mistake.explanation,
                )
                for mistake in result.mistakes
            ],
            vocabulary=[LessonTermOut.from_entity(term) for term in result.terms],
            feedback=result.attempt.feedback,
            next_lesson=(
                LessonSummaryOut.from_entry(result.next_lesson)
                if result.next_lesson is not None
                else None
            ),
        )


# Contract §3: the goal is what the user asked for, trimmed and bounded; it is not adjustable.
PlanGoal = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class PlanCreateIn(BaseModel):
    """What the user asks for when the plan is created (F5 S3)."""

    language_id: str = Field(min_length=1)
    goal: PlanGoal
    # Sessions per week, and the minutes the user can give each day.
    frequency: int = Field(ge=1, le=7)
    daily_minutes: int = Field(ge=5, le=120)


class PlanAdjustIn(BaseModel):
    """The only two things the user can change: the goal stays as it was asked (F5 S4)."""

    frequency: int | None = Field(default=None, ge=1, le=7)
    daily_minutes: int | None = Field(default=None, ge=5, le=120)


class PlanSessionOut(BaseModel):
    """One session of the schedule, with the state its lesson's attempts give it (S5)."""

    id: str
    week: int
    position: int
    lesson_id: str
    lesson_title: str
    status: PlanSessionState

    @classmethod
    def from_entry(cls, entry: PlanSessionEntry) -> "PlanSessionOut":
        return cls(
            id=entry.session.id,
            week=entry.session.week,
            position=entry.session.position,
            lesson_id=entry.session.lesson_id,
            lesson_title=entry.lesson_title,
            status=entry.status,
        )


class PlanOut(BaseModel):
    id: str
    language_id: str
    goal: str
    frequency: int
    daily_minutes: int
    weeks: int
    created_at: str
    adjusted_at: str | None
    next_session: PlanSessionOut | None
    sessions: list[PlanSessionOut]

    @classmethod
    def from_entity(cls, view: PlanView) -> "PlanOut":
        return cls(
            id=view.plan.id,
            language_id=view.plan.language_id,
            goal=view.plan.goal,
            frequency=view.plan.frequency,
            daily_minutes=view.plan.daily_minutes,
            weeks=view.weeks,
            created_at=to_iso(view.plan.created_at),
            adjusted_at=to_iso(view.plan.adjusted_at) if view.plan.adjusted_at else None,
            next_session=(
                PlanSessionOut.from_entry(view.next_session)
                if view.next_session is not None
                else None
            ),
            sessions=[PlanSessionOut.from_entry(entry) for entry in view.sessions],
        )


class LanguagePlanOut(BaseModel):
    """`GET /plans?language_id=`: the plan of one language, or `null` when it has none."""

    language_id: str
    plan: PlanOut | None

    @classmethod
    def from_entity(cls, language_id: str, view: PlanView | None) -> "LanguagePlanOut":
        return cls(
            language_id=language_id,
            plan=PlanOut.from_entity(view) if view is not None else None,
        )


class ProgressLanguageOut(BaseModel):
    """The language whose progress is shown: its badge-level comes from the profile (F6 S5)."""

    id: str
    code: str
    name: str
    level: CefrLevel

    @classmethod
    def from_entity(cls, language: LanguageProfile) -> "ProgressLanguageOut":
        return cls(
            id=language.id,
            code=language.code,
            name=language.name,
            level=language.level,
        )


class ProgressWeeklyGoalOut(BaseModel):
    """Conversations of the current week against the goal stored in the profile (F6 S1)."""

    conversations: int
    target: int


class ProgressSummaryOut(BaseModel):
    """The stored level plus the counters the user can verify in their own history (F6 S1, S5)."""

    level: CefrLevel
    lessons_completed: int
    lessons_total: int
    conversations: int
    weekly_goal: ProgressWeeklyGoalOut

    @classmethod
    def from_view(cls, summary: ProgressSummary) -> "ProgressSummaryOut":
        return cls(
            level=summary.level,
            lessons_completed=summary.lessons_completed,
            lessons_total=summary.lessons_total,
            conversations=summary.conversations,
            weekly_goal=ProgressWeeklyGoalOut(
                conversations=summary.weekly_conversations,
                target=summary.weekly_target,
            ),
        )


class SkillProgressOut(BaseModel):
    """One of the five skills; unavailable ones keep `count` and `last_at` null (F6 S2)."""

    id: SkillId
    available: bool
    count: int | None
    last_at: str | None

    @classmethod
    def from_entity(cls, skill: SkillProgress) -> "SkillProgressOut":
        return cls(
            id=skill.id,
            available=skill.available,
            count=skill.count,
            last_at=to_iso(skill.last_at) if skill.last_at is not None else None,
        )


class FrequentErrorOut(BaseModel):
    """One grouped, repeated mistake; `prompt` is null for tutor corrections (F6 S3)."""

    kind: FrequentErrorKind
    prompt: str | None
    original: str
    expected: str
    count: int
    last_at: str

    @classmethod
    def from_entity(cls, error: FrequentError) -> "FrequentErrorOut":
        return cls(
            kind=error.kind,
            prompt=error.prompt,
            original=error.original,
            expected=error.expected,
            count=error.count,
            last_at=to_iso(error.last_at),
        )


class HistoryEntryOut(BaseModel):
    """One history row: a lesson attempt with its score or a conversation with its messages."""

    kind: HistoryKind
    id: str
    title: str
    at: str
    correct: int | None
    total: int | None
    message_count: int | None

    @classmethod
    def from_entity(cls, entry: HistoryEntry) -> "HistoryEntryOut":
        return cls(
            kind=entry.kind,
            id=entry.id,
            title=entry.title,
            at=to_iso(entry.at),
            correct=entry.correct,
            total=entry.total,
            message_count=entry.message_count,
        )


class ProgressOut(BaseModel):
    """`GET /progress`: the whole screen, derived from stored activity (F6, ADR-018)."""

    language: ProgressLanguageOut
    summary: ProgressSummaryOut
    skills: list[SkillProgressOut]
    frequent_errors: list[FrequentErrorOut]
    history: list[HistoryEntryOut]

    @classmethod
    def from_view(cls, view: ProgressView) -> "ProgressOut":
        return cls(
            language=ProgressLanguageOut.from_entity(view.language),
            summary=ProgressSummaryOut.from_view(view.summary),
            skills=[SkillProgressOut.from_entity(skill) for skill in view.skills],
            frequent_errors=[FrequentErrorOut.from_entity(error) for error in view.frequent_errors],
            history=[HistoryEntryOut.from_entity(entry) for entry in view.history],
        )
