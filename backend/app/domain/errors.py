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


class LanguageAlreadyExists(DomainError):
    pass


class LastLanguageCannotBeArchived(DomainError):
    """Archiving the only remaining language would leave the app without a context."""


class ActiveLanguageCannotBeArchived(DomainError):
    """The active language is the user's current context; archiving it needs an explicit switch."""
