"""Playtime / remaining-time calculations for Device."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from ..const import _LOGGER
from ..exceptions import ExtraPlayingTimeActiveError
from ._helpers import is_bedtime_disabled, minutes_until_end_of_day

if TYPE_CHECKING:  # pragma: no cover
    from ._core import Device


def remaining_play_minutes(
    now: datetime,
    *,
    limit_time: int | float | None,
    extra_playing_time: int | None,
    bedtime_alarm: time | None,
    alarms_enabled: bool,
    today_playing_time: int | float,
) -> int:
    """Compute remaining play minutes from limit and bedtime constraints.

    Pure function extracted from Device._calculate_today_remaining_time.
    """
    end_of_day = minutes_until_end_of_day(now.hour, now.minute)

    if limit_time is None or limit_time == -1 or extra_playing_time == -1:
        time_remaining_by_play_limit: float = float(end_of_day)
    else:
        effective_limit: float = float(limit_time)
        if extra_playing_time:
            effective_limit += extra_playing_time
        time_remaining_by_play_limit = effective_limit - today_playing_time

    if bedtime_alarm and not is_bedtime_disabled(bedtime_alarm) and alarms_enabled:
        bedtime_dt = datetime.combine(now.date(), bedtime_alarm)
        if bedtime_dt <= now and bedtime_alarm.hour < 6 and now.hour >= 6:
            bedtime_dt += timedelta(days=1)
        if bedtime_dt > now:
            time_remaining_by_bedtime = (bedtime_dt - now).total_seconds() / 60
        else:
            time_remaining_by_bedtime = 0.0
    else:
        time_remaining_by_bedtime = float(end_of_day)

    return int(max(0.0, min(time_remaining_by_play_limit, time_remaining_by_bedtime)))


class DeviceTimesMixin:
    """Mixin for daily/monthly playtime aggregates and remaining time."""

    daily_summaries: list
    device_id: str
    name: str | None
    today_playing_time: int | float
    today_disabled_time: int | float
    today_exceeded_time: int | float
    today_time_remaining: int | float
    month_playing_time: int | float
    limit_time: int | float | None
    extra_playing_time: int | None
    bedtime_alarm: time | None
    alarms_enabled: bool
    stats_update_failed: bool

    def _calculate_times(self: Device, now: datetime) -> None:  # type: ignore[misc]
        """Calculate times from parental control settings."""
        if not isinstance(self.daily_summaries, list) or not self.daily_summaries:
            return
        _LOGGER.debug(">> Device._calculate_times()")
        if self.daily_summaries[0]["date"] != now.strftime("%Y-%m-%d"):
            _LOGGER.debug("No daily summary for today, assuming 0 playing time.")
            self.today_playing_time = 0
            self.today_disabled_time = 0
            self.today_exceeded_time = 0
        else:
            self.today_playing_time = self.daily_summaries[0].get("playingTime") or 0
            self.today_disabled_time = self.daily_summaries[0].get("disabledTime") or 0
            self.today_exceeded_time = self.daily_summaries[0].get("exceededTime") or 0
        _LOGGER.debug(
            "Cached playing, disabled and exceeded time for today for device %s",
            self.device_id,
        )
        self._calculate_today_remaining_time(now)

        month_playing_time: int = 0
        for summary in self.daily_summaries:
            date_parsed = datetime.strptime(summary["date"], "%Y-%m-%d")
            if date_parsed.year == now.year and date_parsed.month == now.month:
                month_playing_time += summary["playingTime"]
        self.month_playing_time = month_playing_time
        _LOGGER.debug("Cached current month playing time for device %s", self.device_id)

    def _calculate_today_remaining_time(self: Device, now: datetime) -> None:  # type: ignore[misc]
        """Calculates the remaining playing time for today."""
        self.stats_update_failed = True
        try:
            self.today_time_remaining = remaining_play_minutes(
                now,
                limit_time=self.limit_time,
                extra_playing_time=self.extra_playing_time,
                bedtime_alarm=self.bedtime_alarm,
                alarms_enabled=self.alarms_enabled,
                today_playing_time=self.today_playing_time,
            )
            _LOGGER.debug(
                "Calculated today's remaining time: %s minutes",
                self.today_time_remaining,
            )
            self.stats_update_failed = False
        except (ValueError, TypeError, AttributeError) as err:
            _LOGGER.warning("Unable to calculate remaining time for device %s: %s", self.name, err)

    def _raise_if_extra_playing_time_active(self: Device) -> None: # type: ignore[misc]
        """Raise an exception if extra playing time is active for the current day."""
        if self.extra_playing_time:
            raise ExtraPlayingTimeActiveError(self.extra_playing_time)
