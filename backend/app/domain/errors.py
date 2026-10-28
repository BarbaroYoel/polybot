"""Domain failures. They carry no HTTP status: `api/` decides how each one looks."""


class DomainError(Exception):
    """Base class for expected, meaningful failures in the domain."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class LanguageNotFound(DomainError):
    pass


class ConversationNotFound(DomainError):
    pass


class MessageNotFound(DomainError):
    """The message does not exist or belongs to another conversation (F3)."""


class InvalidTurnMessage(DomainError):
    """Only a user message starts a tutor turn (F3)."""


class BlockNotFound(DomainError):
    """The message has no block with that id, or it belongs to another conversation (ADR-020)."""


class BlockNotAnswerable(DomainError):
    """The block is not a drill: only an exercise is answered (ADR-020)."""


class LanguageAlreadyExists(DomainError):
    pass


class LastLanguageCannotBeArchived(DomainError):
    """Archiving the only remaining language would leave the app without a context."""


class ActiveLanguageCannotBeArchived(DomainError):
    """The active language is the user's current context; archiving it needs an explicit switch."""


class LlmUnavailable(DomainError):
    """The tutor provider failed, exited early or returned an unusable answer (F3)."""


class LlmTimeout(DomainError):
    """The tutor did not answer within the configured time (F3)."""


class InvalidAudio(DomainError):
    """The upload is empty, is not a WAV, or is not the shape the engine takes (F4 S3)."""


class AudioTooLong(DomainError):
    """The clip is longer than the transcription limit (F4 S3)."""


class SttUnavailable(DomainError):
    """The speech-to-text engine failed or answered something unusable (F4 S3)."""


class VoiceNotAvailable(DomainError):
    """No voice speaks that language, or the requested voice is not installed (F4, ADR-016)."""


class TtsUnavailable(DomainError):
    """The speech engine failed, timed out or is not installed (F4, ADR-016)."""


class SpeechNotFound(DomainError):
    """The synthesized clip is not in the cache: it has to be generated again (F4)."""


class LessonNotFound(DomainError):
    """The lesson does not exist or belongs to another language (F5 S6)."""


class NoLessonsForLanguage(DomainError):
    """The language has no catalog: the UI shows an empty state, not an invented lesson (S5)."""


class MissingLessonAnswers(DomainError):
    """A submit that does not answer every exercise of the lesson (F5 S7)."""


class PlanNotFound(DomainError):
    """The plan does not exist (F5 S3)."""


class PlanAlreadyExists(DomainError):
    """The language already has a plan: one per language, adjusted instead of duplicated (S4)."""


class InvalidTimezone(DomainError):
    """The `tz` of `/progress` is not an IANA zone, so the weekly window cannot be computed (F6)."""
