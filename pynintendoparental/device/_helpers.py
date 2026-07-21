"""Pure helpers for Device parental-control mutations and parsing."""

from __future__ import annotations

from datetime import time

from ..exceptions import BedtimeOutOfRangeError, DailyPlaytimeOutOfRangeError

_DISABLED_BEDTIME = time(0, 0)
_DEFAULT_STARTING_TIME = {"hour": 6, "minute": 0}


def time_to_api_dict(value: time) -> dict[str, int]:
    """Convert a ``time`` to the Nintendo API ``{hour, minute}`` shape."""
    return {"hour": value.hour, "minute": value.minute}


def api_dict_to_time(value: dict | None) -> time | None:
    """Convert an API ``{hour, minute}`` dict to ``time``, or None."""
    if not value:
        return None
    return time(hour=value["hour"], minute=value["minute"])


def is_bedtime_disabled(value: time | None) -> bool:
    """Return True when bedtime is the disabled sentinel ``time(0, 0)``."""
    return value is None or value == _DISABLED_BEDTIME


def disabled_bedtime() -> time:
    """Return the disabled-bedtime sentinel."""
    return _DISABLED_BEDTIME


def validate_bedtime_alarm(value: time) -> None:
    """Validate a bedtime alarm time (16:00–23:00, or disabled)."""
    if not ((16 <= value.hour <= 23) or (value.hour == 0 and value.minute == 0)):
        raise BedtimeOutOfRangeError(value=value)


def validate_bedtime_end(value: time) -> None:
    """Validate a bedtime end time (05:00–09:00, or disabled)."""
    if not time(5, 0) <= value <= time(9, 0) and value != _DISABLED_BEDTIME:
        raise BedtimeOutOfRangeError(value=value)


def validate_daily_restriction_bedtime_start(value: time) -> None:
    """Validate bedtime start for set_daily_restrictions (05:00–09:00)."""
    if not time(5, 0) <= value <= time(9, 0):
        raise BedtimeOutOfRangeError(value=value)


def validate_daily_restriction_bedtime_end(value: time) -> None:
    """Validate bedtime end for set_daily_restrictions (16:00–22:xx, 23:00, or 00:00)."""
    if not (
        (16 <= value.hour <= 22) or (value.hour == 23 and value.minute == 0) or (value.hour == 0 and value.minute == 0)
    ):
        raise BedtimeOutOfRangeError(value=value)


def default_starting_time(bedtime: dict | None = None) -> dict[str, int]:
    """Return startingTime for disabled bedtime (API requires it).

    Preserves an existing startingTime when present; otherwise defaults to 06:00.
    """
    bedtime = bedtime or {}
    return dict(bedtime.get("startingTime") or _DEFAULT_STARTING_TIME)


def build_bedtime_dict(
    *,
    enabled: bool,
    starting_time: dict[str, int] | None = None,
    ending_time: dict[str, int] | None = None,
) -> dict:
    """Build a bedtime regulation dict for the API."""
    return {
        "enabled": enabled,
        "startingTime": starting_time,
        "endingTime": ending_time,
    }


def apply_time_to_play_in_one_day(
    regulation: dict,
    minutes: int | None,
    *,
    enabled: bool | None = None,
    pop_when_disabled: bool = True,
) -> None:
    """Mutate ``regulation['timeToPlayInOneDay']`` for a play limit update.

    Args:
        regulation: Today's (or a day's) regulation dict.
        minutes: Limit in minutes, or None when removing the limit.
        enabled: Explicit enabled flag; defaults to ``minutes is not None``.
        pop_when_disabled: If True (update_max_daily_playtime), pop limitTime when
            minutes is None. If False (set_daily_restrictions), set limitTime to None.
    """
    if enabled is None:
        enabled = minutes is not None
    ttpiod = regulation.setdefault("timeToPlayInOneDay", {})
    ttpiod["enabled"] = enabled
    if pop_when_disabled and minutes is None and "limitTime" in ttpiod:
        ttpiod.pop("limitTime")
    else:
        # set_daily_restrictions always assigns (including None); update_max also
        # assigns when limitTime was absent so the API still receives the key.
        ttpiod["limitTime"] = minutes


def normalize_playtime_minutes(minutes: int | float) -> int:
    """Coerce float minutes to int."""
    if isinstance(minutes, float):
        return int(minutes)
    return minutes


def validate_max_daily_playtime(minutes: int) -> None:
    """Validate minutes for update_max_daily_playtime (-1..360)."""
    if not (-1 <= minutes <= 360):
        raise DailyPlaytimeOutOfRangeError(minutes)


def validate_daily_restriction_playtime(minutes: int) -> None:
    """Validate minutes for set_daily_restrictions (0..360)."""
    if not 0 <= minutes <= 360:
        raise DailyPlaytimeOutOfRangeError(minutes)


def minutes_until_end_of_day(now_hour: int, now_minute: int) -> int:
    """Return minutes remaining until midnight."""
    return 1440 - (now_hour * 60 + now_minute)


def time_to_minutes(value: time) -> int:
    """Convert a time to minutes past midnight."""
    return value.hour * 60 + value.minute
