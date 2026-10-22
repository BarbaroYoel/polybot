"""Translate every exception into the contract envelope (docs/api-contract.md §1 and §4)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ApiError, error_body

logger = logging.getLogger(__name__)

# Status code -> (stable English code, Spanish message shown to the user).
_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    400: ("invalid_request", "La solicitud no se pudo procesar. Revisa los datos enviados."),
    401: ("unauthorized", "Necesitas autorización para esta acción."),
    403: ("forbidden", "No tienes permiso para esta acción."),
    404: ("not_found", "No encontramos lo que buscabas."),
    405: ("method_not_allowed", "Ese método no está permitido en esta ruta."),
    409: (
        "conflict",
        "La operación entra en conflicto con el estado actual. Actualiza y reintenta.",
    ),
    413: ("payload_too_large", "Lo que enviaste supera el tamaño permitido."),
    422: ("validation_error", "Revisa los datos enviados y vuelve a intentar."),
    429: ("rate_limited", "Alcanzaste el límite de uso. Espera un momento y reintenta."),
    500: ("internal_error", "Ocurrió un error inesperado. Vuelve a intentar en unos segundos."),
}

_VALIDATION_MESSAGE = "Revisa los datos enviados y vuelve a intentar."


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _json(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_body(code, message, details=details, request_id=_request_id(request)),
    )


def _describe_http_error(status_code: int) -> tuple[str, str]:
    if status_code in _HTTP_ERRORS:
        return _HTTP_ERRORS[status_code]
    if 500 <= status_code < 600:
        return _HTTP_ERRORS[500]
    return ("http_error", "La solicitud no se pudo completar.")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _json(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Our own Spanish message, never Starlette's English default: the client shows this text.
        code, message = _describe_http_error(exc.status_code)
        return _json(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {
                "location": ".".join(str(part) for part in error.get("loc", ())),
                "message": error.get("msg", ""),
            }
            for error in exc.errors()
        ]
        return _json(request, 422, "validation_error", _VALIDATION_MESSAGE, {"fields": fields})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error [request_id=%s]", _request_id(request), exc_info=exc)
        code, message = _HTTP_ERRORS[500]
        return _json(request, 500, code, message)
