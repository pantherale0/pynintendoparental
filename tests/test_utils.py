"""Tests for generic utilities."""

from datetime import datetime, timezone

from freezegun import freeze_time

from pynintendoparental.utils import current_datetime


def test_current_datetime_uses_iana_zone():
    """current_datetime returns the civil date in the requested zone."""
    with freeze_time(datetime(2025, 6, 1, 23, 30, tzinfo=timezone.utc)):
        london = current_datetime("Europe/London")
        assert london.date().isoformat() == "2025-06-02"

        los_angeles = current_datetime("America/Los_Angeles")
        assert los_angeles.date().isoformat() == "2025-06-01"
