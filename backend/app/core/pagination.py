"""Opaque cursor pagination (docs/api-contract.md §1: `?limit=20&cursor=<opaco>`).

A cursor is the base64url encoding of the last row's ordering key: `(timestamp, id)`. The client
never builds one and never needs to know its shape.
"""

import base64
import binascii
from datetime import datetime

from app.core.dates import from_iso, to_iso

_SEPARATOR = "|"


class InvalidCursor(ValueError):
    """The cursor did not come from this API."""


def encode_cursor(created_at: datetime, row_id: str) -> str:
    raw = f"{to_iso(created_at)}{_SEPARATOR}{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise InvalidCursor(cursor) from exc

    timestamp, separator, row_id = raw.partition(_SEPARATOR)
    if not separator or not row_id:
        raise InvalidCursor(cursor)
    try:
        return from_iso(timestamp), row_id
    except ValueError as exc:
        raise InvalidCursor(cursor) from exc
