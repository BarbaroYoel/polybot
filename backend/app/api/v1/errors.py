"""Domain failures translated to HTTP (docs/conventions.md §2: `domain/` never raises HTTP).

The `code` is stable and stays in English; the `message` is what the user reads, in Spanish.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.handlers import error_response
from app.domain.errors import (
    ActiveLanguageCannotBeArchived,
    AudioTooLong,
    ConversationNotFound,
    DomainError,
    InvalidAudio,
    InvalidTurnMessage,
    LanguageAlreadyExists,
    LanguageNotFound,
    LastLanguageCannotBeArchived,
    LlmTimeout,
    LlmUnavailable,
    MessageNotFound,
    SpeechNotFound,
    SttUnavailable,
    TtsUnavailable,
    VoiceNotAvailable,
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
    MessageNotFound: (
        404,
        "message_not_found",
        "No encontramos ese mensaje en esta conversación.",
    ),
    InvalidTurnMessage: (
        400,
        "invalid_turn_message",
        "Solo se puede transmitir un mensaje del usuario.",
    ),
    LlmUnavailable: (
        502,
        "llm_unavailable",
        "El tutor no pudo responder. Vuelve a intentar en unos segundos.",
    ),
    LlmTimeout: (
        504,
        "llm_timeout",
        "El tutor tardó demasiado en responder. Vuelve a intentar.",
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
    InvalidAudio: (
        400,
        "invalid_audio",
        "No pudimos leer ese audio. Graba de nuevo, cerca del micrófono.",
    ),
    AudioTooLong: (
        413,
        "audio_too_long",
        "El audio supera los 120 segundos. Graba un mensaje más corto.",
    ),
    VoiceNotAvailable: (
        400,
        "voice_not_available",
        "No hay una voz instalada para ese idioma. Revisá las voces y volvé a intentar.",
    ),
    SpeechNotFound: (
        404,
        "speech_not_found",
        "Ese audio ya no está disponible. Volvé a generarlo.",
    ),
    TtsUnavailable: (
        502,
        "tts_unavailable",
        "No pudimos generar el audio. Vuelve a intentar en unos segundos.",
    ),
    SttUnavailable: (
        502,
        "stt_unavailable",
        "No pudimos transcribir el audio. Vuelve a intentar en unos segundos.",
    ),
}

_UNEXPECTED = (
    500,
    "internal_error",
    "Ocurrió un error inesperado. Vuelve a intentar en unos segundos.",
)


def describe_domain_error(exc: DomainError) -> tuple[int, str, str]:
    """Status and contract `code`/`message` for a domain failure.

    The exception handler and the SSE `error` event share it: one mapping, two transports.
    """
    return _DOMAIN_ERRORS.get(type(exc), _UNEXPECTED)


def install_domain_error_handler(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status_code, code, message = describe_domain_error(exc)
        return error_response(request, status_code, code, message)
