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
