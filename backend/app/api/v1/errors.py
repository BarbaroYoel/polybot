"""Domain failures translated to HTTP (docs/conventions.md §2: `domain/` never raises HTTP).

The `code` is stable and stays in English; the `message` is what the user reads, in Spanish.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.handlers import error_response
from app.domain.errors import (
    ActiveLanguageCannotBeArchived,
    ConversationNotFound,
    DomainError,
    LanguageAlreadyExists,
    LanguageNotFound,
    LastLanguageCannotBeArchived,
)

_DOMAIN_ERRORS: dict[type[DomainError], tuple[int, str, str]] = {
    LanguageNotFound: (
        404,
        "language_not_found",
        "Ese idioma no está en tu lista. Actualiza la página y vuelve a intentar.",
    ),
    ConversationNotFound: (
        404,
        "conversation_not_found",
        "Esa conversación no existe o pertenece a otro idioma.",
    ),
    LanguageAlreadyExists: (
        409,
        "language_already_exists",
        "Ese idioma ya está en tu lista.",
    ),
    ActiveLanguageCannotBeArchived: (
        409,
        "active_language_cannot_be_archived",
        "Activa otro idioma antes de archivar el que está en uso.",
    ),
    LastLanguageCannotBeArchived: (
        409,
        "last_language_cannot_be_archived",
        "Necesitas al menos un idioma en tu lista.",
    ),
}

_UNEXPECTED = (
    500,
    "internal_error",
    "Ocurrió un error inesperado. Vuelve a intentar en unos segundos.",
)


def install_domain_error_handler(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status_code, code, message = _DOMAIN_ERRORS.get(type(exc), _UNEXPECTED)
        return error_response(request, status_code, code, message)
