"""Time handling: everything is stored as naive UTC and serialized with a `Z` suffix.

docs/api-contract.md: "Fechas: ISO 8601 UTC (`2026-10-22T14:03:00Z`)". SQLite has no timezone
type, so the codebase keeps one convention instead of relying on the driver.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Current time as naive UTC, ready to be stored."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_iso(value: datetime) -> str:
    """Serialize a stored (naive UTC) timestamp the way the contract asks."""
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat(timespec="seconds").replace("+00:00", "Z")


def from_iso(value: str) -> datetime:
    """Parse an ISO 8601 string into naive UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
