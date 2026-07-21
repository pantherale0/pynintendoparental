"""Parental control setting mutators for Device."""

from __future__ import annotations

from datetime import datetime, time

from ..const import _LOGGER, DAYS_OF_WEEK
from ..enum import DeviceTimerMode, FunctionalRestrictionLevel, RestrictionMode
from ..exceptions import BedtimeOutOfRangeError, InvalidDeviceStateError
from ._helpers import (
    apply_time_to_play_in_one_day,
    build_bedtime_dict,
    default_starting_time,
    is_bedtime_disabled,
    normalize_playtime_minutes,
    time_to_api_dict,
    validate_bedtime_alarm,
    validate_bedtime_end,
    validate_daily_restriction_bedtime_end,
    validate_daily_restriction_bedtime_start,
    validate_daily_restriction_playtime,
    validate_max_daily_playtime,
)


class DeviceSettingsMixin:
    """Mixin providing parental-control mutation APIs on Device."""

    async def set_new_pin(self, pin: str):
        """Set a new PIN code for parental controls on this device.

        Args:
            pin: The new PIN code to set. Must be a valid 4-digit string.
        """
        _LOGGER.debug(">> Device.set_new_pin(pin=REDACTED)")
        await self._send_api_update(self._api.async_update_unlock_code, new_code=pin, device_id=self.device_id)

    async def add_extra_time(self, minutes: int):
        """Add extra playing time for the current day.

        Args:
            minutes: Number of additional minutes to add (must be positive).
        """
        _LOGGER.debug(">> Device.add_extra_time(minutes=%s)", minutes)
        with_bedtime = (
            self.bedtime_alarm is not None and not is_bedtime_disabled(self.bedtime_alarm) and self.alarms_enabled
        )
        if minutes != -1 and with_bedtime:
            await self._api.async_confirm_extra_playing_time(self.device_id, minutes, True)
        else:
            await self._api.async_update_extra_playing_time(self.device_id, minutes)
        await self._get_parental_control_setting(datetime.now())

    async def set_restriction_mode(self, mode: RestrictionMode):
        """Set the restriction mode for playtime limits.

        Args:
            mode: RestrictionMode.FORCED_TERMINATION or RestrictionMode.ALARM.
        """
        _LOGGER.debug(">> Device.set_restriction_mode(mode=%s)", mode)
        self.parental_control_settings["playTimerRegulations"]["restrictionMode"] = str(mode)
        response = await self._api.async_update_play_timer(
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
        )
        now = datetime.now()
        self._parse_parental_control_setting(response["json"], now)  # Don't need to recalculate times
        await self._execute_callbacks()

    async def set_bedtime_alarm(self, value: time):
        """Set the bedtime alarm time (16:00–23:00, or time(0, 0) to disable)."""
        _LOGGER.debug(">> Device.set_bedtime_alarm(value=%s)", value)
        validate_bedtime_alarm(value)
        now = datetime.now()
        regulation = self._get_today_regulation(now)
        enabled = 16 <= value.hour <= 23
        bedtime = {
            **regulation.get("bedtime", {}),
            "enabled": enabled,
            "endingTime": time_to_api_dict(value) if enabled else None,
        }
        regulation["bedtime"] = bedtime
        _LOGGER.debug(
            ">> Device.set_bedtime_alarm(value=%s): Updating bedtime with object %s",
            value,
            bedtime,
        )
        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
            now=now,
        )

    async def set_bedtime_end_time(self, value: time):
        """Set when bedtime restrictions end (05:00–09:00, or time(0, 0) to disable)."""
        _LOGGER.debug(">> Device.set_bedtime_end_time(value=%s)", value)
        validate_bedtime_end(value)
        now = datetime.now()
        regulation = self._get_today_regulation(now)
        enabled = not is_bedtime_disabled(value)
        regulation["bedtime"] = {
            **regulation["bedtime"],
            "enabled": enabled,
            "startingTime": time_to_api_dict(value) if enabled else default_starting_time(regulation.get("bedtime")),
        }
        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
            now=now,
        )

    async def set_timer_mode(self, mode: DeviceTimerMode):
        """Set the timer mode (DAILY or EACH_DAY_OF_THE_WEEK)."""
        _LOGGER.debug(">> Device.set_timer_mode(mode=%s)", mode)
        self.timer_mode = mode
        self.parental_control_settings["playTimerRegulations"]["timerMode"] = str(mode)
        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
        )

    async def set_daily_restrictions(
        self,
        enabled: bool,
        bedtime_enabled: bool,
        day_of_week: str,
        bedtime_start: time | None = None,
        bedtime_end: time | None = None,
        max_daily_playtime: int | float | None = None,
    ):
        """Set restrictions for a specific day of the week.

        Only works when timer_mode is EACH_DAY_OF_THE_WEEK.
        """
        _LOGGER.debug(
            ">> Device.set_daily_restrictions(enabled=%s, bedtime_enabled=%s, day_of_week=%s, "
            "bedtime_start=%s, bedtime_end=%s, max_daily_playtime=%s)",
            enabled,
            bedtime_enabled,
            day_of_week,
            bedtime_start,
            bedtime_end,
            max_daily_playtime,
        )
        if self.timer_mode != DeviceTimerMode.EACH_DAY_OF_THE_WEEK:
            raise InvalidDeviceStateError("Daily restrictions can only be set when timer_mode is EACH_DAY_OF_THE_WEEK.")
        if day_of_week not in DAYS_OF_WEEK:
            raise ValueError(f"Invalid day_of_week: {day_of_week}")

        regulation = self.parental_control_settings["playTimerRegulations"]["eachDayOfTheWeekRegulations"][day_of_week]
        regulation["bedtime"] = self._build_daily_restriction_bedtime(
            regulation,
            bedtime_enabled=bedtime_enabled,
            bedtime_start=bedtime_start,
            bedtime_end=bedtime_end,
        )

        playtime = None
        if enabled and max_daily_playtime is not None:
            playtime = normalize_playtime_minutes(max_daily_playtime)
            validate_daily_restriction_playtime(playtime)
        apply_time_to_play_in_one_day(
            regulation,
            playtime,
            enabled=enabled,
            pop_when_disabled=False,
        )

        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
        )

    def _build_daily_restriction_bedtime(
        self,
        regulation: dict,
        *,
        bedtime_enabled: bool,
        bedtime_start: time | None,
        bedtime_end: time | None,
    ) -> dict:
        """Build the bedtime dict for set_daily_restrictions."""
        if bedtime_enabled and bedtime_start is not None and bedtime_end is not None:
            validate_daily_restriction_bedtime_start(bedtime_start)
            validate_daily_restriction_bedtime_end(bedtime_end)
            return build_bedtime_dict(
                enabled=True,
                starting_time=time_to_api_dict(bedtime_start),
                ending_time=time_to_api_dict(bedtime_end),
            )
        if bedtime_enabled:
            raise BedtimeOutOfRangeError(value=None)
        # API requires startingTime even when bedtime is disabled.
        return build_bedtime_dict(
            enabled=False,
            starting_time=default_starting_time(regulation.get("bedtime")),
            ending_time=None,
        )

    async def set_functional_restriction_level(self, level: FunctionalRestrictionLevel):
        """Set the content restriction level based on age ratings."""
        _LOGGER.debug(">> Device.set_functional_restriction_level(level=%s)", level)
        self.parental_control_settings["functionalRestrictionLevel"] = str(level)
        await self._send_api_update(
            self._api.async_update_restriction_level,
            self.device_id,
            self.parental_control_settings,
        )

    async def update_max_daily_playtime(self, minutes: int | float = 0):
        """Set the maximum daily playtime limit (0–360, or -1 to remove)."""
        _LOGGER.debug(">> Device.update_max_daily_playtime(minutes=%s)", minutes)
        minutes = normalize_playtime_minutes(minutes)
        validate_max_daily_playtime(minutes)
        now = datetime.now()
        limit = None if minutes == -1 else minutes
        regulation = self._get_today_regulation(now)
        _LOGGER.debug(
            "Setting timeToPlayInOneDay.limitTime for device %s to value %s",
            self.device_id,
            limit,
        )
        apply_time_to_play_in_one_day(regulation, limit, pop_when_disabled=True)
        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
            now=now,
        )
