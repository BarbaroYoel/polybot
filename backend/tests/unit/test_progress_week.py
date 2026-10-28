"""The weekly window of the goal: Monday 00:00 in the caller's zone, compared as naive UTC.

The contract lets the client send an IANA `tz` so the week starts where the user lives (F6 S1).
A wrong offset would count the wrong practices, and a bad zone must fail with an actionable error
instead of silently falling back to UTC.
"""

from datetime import UTC, datetime

import pytest

from app.application.progress import week_start
from app.domain.errors import InvalidTimezone


def test_the_week_starts_on_monday_at_midnight_utc() -> None:
    wednesday = datetime(2026, 10, 28, 15, 30, tzinfo=UTC)

    assert week_start("UTC", now=wednesday) == datetime(2026, 10, 26, 0, 0)


def test_monday_itself_belongs_to_the_week_it_starts() -> None:
    monday_late = datetime(2026, 10, 26, 23, 59, tzinfo=UTC)

    assert week_start("UTC", now=monday_late) == datetime(2026, 10, 26, 0, 0)


def test_a_local_monday_can_start_on_the_previous_utc_day() -> None:
    # Kiritimati is UTC+14: its Monday 00:00 is Sunday 10:00 UTC.
    tuesday_local = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)

    assert week_start("Pacific/Kiritimati", now=tuesday_local) == datetime(2026, 10, 25, 10, 0)


def test_a_local_monday_can_start_later_than_midnight_utc() -> None:
    # Honolulu is UTC-10: its Monday 00:00 is Monday 10:00 UTC.
    monday_local = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)

    assert week_start("Pacific/Honolulu", now=monday_local) == datetime(2026, 10, 26, 10, 0)


@pytest.mark.parametrize("tz", ["", "No/Existe", "../etc/passwd"])
def test_an_unknown_zone_is_an_invalid_timezone_error(tz: str) -> None:
    with pytest.raises(InvalidTimezone):
        week_start(tz, now=datetime(2026, 10, 26, 12, 0, tzinfo=UTC))
