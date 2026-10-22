"""Query-parameter helpers shared by the routers."""

from datetime import datetime

from app.core.errors import ApiError
from app.core.pagination import InvalidCursor, decode_cursor


def parse_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    """Decode an opaque cursor. A cursor we did not issue is a client error, not a 500."""
    if not cursor:
        return None
    try:
        return decode_cursor(cursor)
    except InvalidCursor as exc:
        raise ApiError(
            "invalid_cursor",
            "Ese enlace de paginación ya no es válido. Vuelve a abrir la lista desde el principio.",
            status_code=400,
        ) from exc
