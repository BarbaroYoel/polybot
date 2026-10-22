"""The single error envelope of the API (docs/api-contract.md §4).

`ApiError` is the only exception the HTTP layer raises on purpose. Domain exceptions live in
`app.domain.errors` and are translated here, so `domain/` never imports FastAPI.
"""

from typing import Any


class ApiError(Exception):
    """An error that already knows how it looks over HTTP."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(ApiError):
    def __init__(self, message: str = "No encontramos lo que buscabas.", **kwargs: Any) -> None:
        super().__init__("not_found", message, status_code=404, **kwargs)


class ConflictError(ApiError):
    def __init__(self, code: str, message: str, **kwargs: Any) -> None:
        super().__init__(code, message, status_code=409, **kwargs)


class InvalidRequestError(ApiError):
    def __init__(self, code: str, message: str, **kwargs: Any) -> None:
        super().__init__(code, message, status_code=400, **kwargs)


def error_body(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    """Serialize the envelope of docs/api-contract.md §4; every error goes out through this."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }
