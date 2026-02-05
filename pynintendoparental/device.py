# pylint: disable=line-too-long
"""Defines a single Nintendo Switch device."""

import asyncio
from datetime import datetime, time, timedelta
from typing import Callable

from pynintendoauth.exceptions import HttpException

from .api import Api
from .application import Application
from .const import _LOGGER, DAYS_OF_WEEK
from .enum import (
    AlarmSettingState,
    DeviceTimerMode,
    FunctionalRestrictionLevel,
    RestrictionMode,
)
from .exceptions import (
    BedtimeOutOfRangeError,
    DailyPlaytimeOutOfRangeError,
    InvalidDeviceStateError,
)
from .player import Player
from .utils import is_awaitable


class Device:
    """A Nintendo Switch device.

    Represents a single Nintendo Switch console with parental controls enabled.
    This class provides methods to monitor and control various parental control settings.

    Attributes:
        device_id: Unique identifier for the device.
        name: User-friendly name/label for the device.
        model: Device model (e.g., "Switch", "Switch 2").
        limit_time: Daily playtime limit in minutes (-1 if no limit).
        today_playing_time: Total playing time for the current day in minutes.
        today_time_remaining: Remaining playtime for the current day in minutes.
        players: Dictionary of Player objects keyed by player ID.
        applications: Dictionary of Application objects keyed by application ID.
        timer_mode: Current timer mode (DAILY or EACH_DAY_OF_THE_WEEK).
        bedtime_alarm: Time when bedtime alarm sounds.
        bedtime_end: Time when bedtime restrictions end.
        forced_termination_mode: True if software suspension is enabled at playtime limit.
        alarms_enabled: True if alarms are enabled.
        last_sync: Timestamp of the last sync with Nintendo servers.
    """

    def __init__(self, api):
        """INIT"""
        self.device_id: str = None
        self.name: str = None
        self.sync_state: str = None
        self.extra: dict = {}
        self._api: Api = api
        self.daily_summaries: dict = {}
        self.parental_control_settings: dict = {}
        self.players: dict[str, Player] = {}
        self.limit_time: int | float | None = 0
        self.extra_playing_time: int | None = None
        self.timer_mode: DeviceTimerMode | None = None
        self.today_playing_time: int | float = 0
        self.today_time_remaining: int | float = 0
        self.bedtime_alarm: time | None = None
        self.bedtime_end: time | None = None
        self.month_playing_time: int | float = 0
        self.today_disabled_time: int | float = 0
        self.today_exceeded_time: int | float = 0
        self.today_notices: list = []
        self.today_important_info: list = []
        self.today_observations: list = []
        self.last_month_summary: dict = {}
        self.applications: dict[str, Application] = {}
        self.whitelisted_applications: dict[str, bool] = {}
        self.last_month_playing_time: int = 0
        self.forced_termination_mode: bool = False
        self.alarms_enabled: bool = False
        self.stats_update_failed: bool = False
        self._callbacks: list[Callable] = []
        self._internal_callbacks: list[Callable] = []
        _LOGGER.debug("Device init complete for %s", self.device_id)

    @property
    def model(self) -> str:
        """Return the device model.

        Returns:
            Device model name (e.g., "Switch", "Switch 2", or "Unknown").
        """
        model_map = {"P00": "Switch", "P01": "Switch 2"}
        return model_map.get(self.generation, "Unknown")

    @property
    def generation(self) -> str | None:
        """Return the device generation code.

        Returns:
            Platform generation code (e.g., "P00", "P01") or None if unknown.
        """
        return self.extra.get("platformGeneration", None)

    @property
    def last_sync(self) -> float | None:
        """Return the last time this device was synced with Nintendo servers.

        Returns:
            Unix timestamp of the last synchronization, or None if never synced.
        """
        return self.extra.get("synchronizedParentalControlSetting", {}).get("synchronizedAt", None)

    async def update(self, now: datetime = None):
        """Update device data from Nintendo servers.

        Fetches the latest information including daily summaries, parental control
        settings, monthly summaries, and extra device information. Also updates
        all associated players and applications.

        Args:
            now: Optional datetime for the update. Defaults to current time if not provided.
        """
        _LOGGER.debug(">> Device.update()")
        if now is None:
            now = datetime.now()
        await asyncio.gather(
            self._get_daily_summaries(now),
            self._get_parental_control_setting(now),
            self.get_monthly_summary(),
            self._get_extras(),
        )
        for player in self.players.values():
            player.update_from_daily_summary(self.daily_summaries)
        self._update_applications()
        await self._execute_callbacks()

    def add_device_callback(self, callback: Callable):
        """Add a callback function to be called when device state changes.

        The callback will be invoked whenever the device data is updated.
        Callbacks can be either synchronous or asynchronous functions.

        Args:
            callback: A callable function. Can be sync or async.

        Raises:
            ValueError: If the provided object is not callable.

        Example:
            ```python
            async def on_device_update():
                print("Device updated!")

            device.add_device_callback(on_device_update)
            ```
        """
        if not callable(callback):
            raise ValueError("Object must be callable.")
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_device_callback(self, callback: Callable):
        """Remove a previously registered device callback.

        Args:
            callback: The callback function to remove.

        Raises:
            ValueError: If the provided object is not callable or not found.
        """
        if not callable(callback):
            raise ValueError("Object must be callable.")
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def _execute_callbacks(self):
        """Execute all callbacks."""
        for cb in self._internal_callbacks:
            if is_awaitable(cb):
                await cb(device=self)
            else:
                cb(device=self)

        for cb in self._callbacks:
            if is_awaitable(cb):
                await cb()
            else:
                cb()

    async def _send_api_update(self, api_call: Callable, *args, **kwargs):
        """Sends an update to the API and refreshes local state."""
        now = kwargs.pop("now", datetime.now())
        response = await api_call(*args, **kwargs)
        self._parse_parental_control_setting(response["json"], now)
        self._calculate_times(now)
        await self._execute_callbacks()

    async def set_new_pin(self, pin: str):
        """Set a new PIN code for parental controls on this device.

        Args:
            pin: The new PIN code to set. Must be a valid 4-digit string.

        Example:
            ```python
            await device.set_new_pin("1234")
            ```
        """
        _LOGGER.debug(">> Device.set_new_pin(pin=REDACTED)")
        await self._send_api_update(self._api.async_update_unlock_code, new_code=pin, device_id=self.device_id)

    async def add_extra_time(self, minutes: int):
        """Add extra playing time for the current day.

        This grants additional playing time beyond the configured daily limit
        for the current day only. The extra time does not carry over to other days.

        Args:
            minutes: Number of additional minutes to add (must be positive).

        Example:
            ```python
            await device.add_extra_time(30)  # Add 30 minutes
            ```
        """
        _LOGGER.debug(">> Device.add_extra_time(minutes=%s)", minutes)
        # This endpoint does not return parental control settings, so we call it directly.
        await self._api.async_update_extra_playing_time(self.device_id, minutes)
        await self._get_parental_control_setting(datetime.now())

    async def set_restriction_mode(self, mode: RestrictionMode):
        """Set the restriction mode for playtime limits.

        Args:
            mode: The restriction mode to set. Options are:
                - RestrictionMode.FORCED_TERMINATION: Software will be suspended when playtime limit is reached.
                - RestrictionMode.ALARM: An alarm will be shown but software won't be suspended.

        Example:
            ```python
            from pynintendoparental.enum import RestrictionMode

            await device.set_restriction_mode(RestrictionMode.FORCED_TERMINATION)
            ```
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
        """Set the bedtime alarm time.

        The bedtime alarm will sound at the specified time to notify that bedtime has arrived.

        Args:
            value: Time when the bedtime alarm should sound. Must be between 16:00 (4 PM) and 23:00 (11 PM),
                  or time(0, 0) to disable the alarm.

        Raises:
            BedtimeOutOfRangeError: If the time is outside the valid range.

        Example:
            ```python
            from datetime import time

            await device.set_bedtime_alarm(time(21, 0))  # Set alarm to 9:00 PM
            await device.set_bedtime_alarm(time(0, 0))   # Disable alarm
            ```
        """
        _LOGGER.debug(">> Device.set_bedtime_alarm(value=%s)", value)
        if not ((16 <= value.hour <= 23) or (value.hour == 0 and value.minute == 0)):
            raise BedtimeOutOfRangeError(value=value)
        now = datetime.now()
        regulation = self._get_today_regulation(now).get("bedtime", {})
        regulation["enabled"] = 16 <= value.hour <= 23

        if regulation["enabled"]:
            _LOGGER.debug(">> Device.set_bedtime_alarm(value=%s): Enabled", value)
            regulation = {
                **regulation,
                "endingTime": {"hour": value.hour, "minute": value.minute},
            }
        else:
            regulation = {**regulation, "endingTime": None}
        if self.timer_mode == DeviceTimerMode.DAILY:
            _LOGGER.debug(">> Device.set_bedtime_alarm(value=%s): Daily timer mode", value)
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["bedtime"] = regulation
        else:
            _LOGGER.debug(">> Device.set_bedtime_alarm(value=%s): Each day timer mode", value)
            self.parental_control_settings["playTimerRegulations"]["eachDayOfTheWeekRegulations"][
                DAYS_OF_WEEK[now.weekday()]
            ]["bedtime"] = regulation
        _LOGGER.debug(
            ">> Device.set_bedtime_alarm(value=%s): Updating bedtime with object %s",
            value,
            regulation,
        )
        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
            now=now,
        )

    async def set_bedtime_end_time(self, value: time):
        """Set the time when bedtime restrictions end.

        This sets when the device can be used again after bedtime restrictions.

        Args:
            value: Time when bedtime ends. Must be between 05:00 (5 AM) and 09:00 (9 AM),
                  or time(0, 0) to disable bedtime restrictions.

        Raises:
            BedtimeOutOfRangeError: If the time is outside the valid range.

        Example:
            ```python
            from datetime import time

            await device.set_bedtime_end_time(time(7, 0))   # Bedtime ends at 7:00 AM
            await device.set_bedtime_end_time(time(0, 0))  # Disable bedtime restrictions
            ```
        """
        _LOGGER.debug(">> Device.set_bedtime_end_time(value=%s)", value)
        if not time(5, 0) <= value <= time(9, 0) and value != time(0, 0):
            raise BedtimeOutOfRangeError(value=value)
        now = datetime.now()
        if self.timer_mode == DeviceTimerMode.DAILY:
            regulation = self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]
        else:
            regulation = self.parental_control_settings["playTimerRegulations"]["eachDayOfTheWeekRegulations"][
                DAYS_OF_WEEK[now.weekday()]
            ]
        new_bedtime_settings = {
            **regulation["bedtime"],
            "enabled": regulation["bedtime"]["endingTime"] or value != time(0, 0),
            "startingTime": (
                {
                    "hour": value.hour,
                    "minute": value.minute,
                }
                if value != time(0, 0)
                else None
            ),
        }
        regulation["bedtime"] = new_bedtime_settings
        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
            now=now,
        )

    async def set_timer_mode(self, mode: DeviceTimerMode):
        """Set the timer mode for playtime limits.

        Args:
            mode: The timer mode to set. Options are:
                - DeviceTimerMode.DAILY: Single playtime limit for all days.
                - DeviceTimerMode.EACH_DAY_OF_THE_WEEK: Different limits for each day of the week.

        Example:
            ```python
            from pynintendoparental.enum import DeviceTimerMode

            await device.set_timer_mode(DeviceTimerMode.DAILY)
            ```
        """
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

        This method only works when timer_mode is set to EACH_DAY_OF_THE_WEEK.

        Args:
            enabled: Whether to enable playtime restrictions for this day.
            bedtime_enabled: Whether to enable bedtime restrictions for this day.
            day_of_week: Day of the week (e.g., "MONDAY", "TUESDAY", etc.).
            bedtime_start: Time when bedtime restrictions start (required if bedtime_enabled=True).
            bedtime_end: Time when bedtime restrictions end (required if bedtime_enabled=True).
            max_daily_playtime: Maximum playtime in minutes for this day (required if enabled=True).

        Raises:
            InvalidDeviceStateError: If timer_mode is not EACH_DAY_OF_THE_WEEK.
            ValueError: If day_of_week is invalid.
            BedtimeOutOfRangeError: If bedtime values are outside valid ranges.

        Example:
            ```python
            from datetime import time

            # Set Monday restrictions
            await device.set_daily_restrictions(
                enabled=True,
                bedtime_enabled=True,
                day_of_week="MONDAY",
                bedtime_start=time(21, 0),  # 9 PM
                bedtime_end=time(7, 0),     # 7 AM
                max_daily_playtime=120      # 2 hours
            )
            ```
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

        if bedtime_enabled and bedtime_start is not None and bedtime_end is not None:
            if not time(5, 0) <= bedtime_start <= time(9, 0):
                raise BedtimeOutOfRangeError(value=bedtime_start)
            if not (
                (16 <= bedtime_end.hour <= 22)
                or (bedtime_end.hour == 23 and bedtime_end.minute == 0)
                or (bedtime_end.hour == 0 and bedtime_end.minute == 0)
            ):
                raise BedtimeOutOfRangeError(value=bedtime_end)
            regulation["bedtime"] = {
                "enabled": True,
                "startingTime": {
                    "hour": bedtime_start.hour,
                    "minute": bedtime_start.minute,
                },
                "endingTime": {"hour": bedtime_end.hour, "minute": bedtime_end.minute},
            }
        elif bedtime_enabled:
            raise BedtimeOutOfRangeError(value=None)
        else:
            # Even when disabled, the API seems to expect a starting time.
            regulation["bedtime"] = {
                "enabled": False,
                "startingTime": None,
                "endingTime": None,
            }

        regulation["timeToPlayInOneDay"] = {"enabled": enabled}
        if enabled and max_daily_playtime is not None:
            if isinstance(max_daily_playtime, float):
                max_daily_playtime = int(max_daily_playtime)
            if not 0 <= max_daily_playtime <= 360:
                raise DailyPlaytimeOutOfRangeError(max_daily_playtime)
            regulation["timeToPlayInOneDay"]["limitTime"] = max_daily_playtime
        else:
            regulation["timeToPlayInOneDay"]["limitTime"] = None

        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
        )

    async def set_functional_restriction_level(self, level: FunctionalRestrictionLevel):
        """Set the content restriction level based on age ratings.

        This controls which games and applications can be launched based on their age rating.

        Args:
            level: The restriction level to set. Options are:
                - FunctionalRestrictionLevel.CHILD: Suitable for young children.
                - FunctionalRestrictionLevel.TEEN: Suitable for teenagers.
                - FunctionalRestrictionLevel.YOUNG_ADULT: Suitable for young adults.
                - FunctionalRestrictionLevel.CUSTOM: Custom restrictions.

        Example:
            ```python
            from pynintendoparental.enum import FunctionalRestrictionLevel

            await device.set_functional_restriction_level(FunctionalRestrictionLevel.TEEN)
            ```
        """
        _LOGGER.debug(">> Device.set_functional_restriction_level(level=%s)", level)
        self.parental_control_settings["functionalRestrictionLevel"] = str(level)
        await self._send_api_update(
            self._api.async_update_restriction_level,
            self.device_id,
            self.parental_control_settings,
        )

    async def update_max_daily_playtime(self, minutes: int | float = 0):
        """Set the maximum daily playtime limit.

        Args:
            minutes: Maximum playtime in minutes (0-360). Use -1 to remove the limit.

        Raises:
            DailyPlaytimeOutOfRangeError: If minutes is outside the valid range.

        Example:
            ```python
            await device.update_max_daily_playtime(180)  # 3 hours
            await device.update_max_daily_playtime(-1)   # Remove limit
            ```
        """
        _LOGGER.debug(">> Device.update_max_daily_playtime(minutes=%s)", minutes)
        if isinstance(minutes, float):
            minutes = int(minutes)
        if not (-1 <= minutes <= 360):
            raise DailyPlaytimeOutOfRangeError(minutes)
        now = datetime.now()
        ttpiod = True
        if minutes == -1:
            ttpiod = False
            minutes = None
        if self.timer_mode == DeviceTimerMode.DAILY:
            _LOGGER.debug(
                "Setting timeToPlayInOneDay.limitTime for device %s to value %s",
                self.device_id,
                minutes,
            )
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"][
                "enabled"
            ] = ttpiod
            if (
                "limitTime"
                in self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]
                and minutes is None
            ):
                self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"].pop(
                    "limitTime"
                )
            else:
                self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"][
                    "limitTime"
                ] = minutes
        else:
            _LOGGER.debug(
                "Setting timeToPlayInOneDay.limitTime for device %s to value %s",
                self.device_id,
                minutes,
            )
            day_of_week_regs = self.parental_control_settings["playTimerRegulations"]["eachDayOfTheWeekRegulations"]
            current_day = DAYS_OF_WEEK[now.weekday()]
            day_of_week_regs[current_day]["timeToPlayInOneDay"]["enabled"] = ttpiod
            if "limitTime" in day_of_week_regs[current_day]["timeToPlayInOneDay"] and minutes is None:
                day_of_week_regs[current_day]["timeToPlayInOneDay"].pop("limitTime")
            else:
                day_of_week_regs[current_day]["timeToPlayInOneDay"]["limitTime"] = minutes

        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
            now=now,
        )

    def _update_applications(self):
        """Updates applications from whitelisted applications list."""
        _LOGGER.debug(">> Device._update_applications()")
        for app in self.parental_control_settings.get("whitelistedApplicationList", []):
            if app["applicationId"] in self.applications:
                continue
            self.applications[app["applicationId"]] = Application(
                app_id=app["applicationId"],
                name=app["title"],
                device_id=self.device_id,
                api=self._api,
                send_api_update=self._send_api_update,
                callbacks=self._internal_callbacks,
            )

    def _get_today_regulation(self, now: datetime) -> dict:
        """Returns the regulation settings for the current day."""
        if self.timer_mode == DeviceTimerMode.EACH_DAY_OF_THE_WEEK:
            day_of_week_regs = self.parental_control_settings["playTimerRegulations"].get(
                "eachDayOfTheWeekRegulations", {}
            )
            return day_of_week_regs.get(DAYS_OF_WEEK[now.weekday()], {})
        return self.parental_control_settings.get("playTimerRegulations", {}).get("dailyRegulations", {})

    def _parse_parental_control_setting(self, pcs: dict, now: datetime):
        """Parse a parental control setting request response."""
        _LOGGER.debug(">> Device._parse_parental_control_setting()")
        self.parental_control_settings = pcs["parentalControlSetting"]
        self.parental_control_settings["playTimerRegulations"].pop("bedtimeStartingTime", None)
        self.parental_control_settings["playTimerRegulations"].pop("bedtimeEndingTime", None)
        self.forced_termination_mode = self.parental_control_settings["playTimerRegulations"]["restrictionMode"] == str(
            RestrictionMode.FORCED_TERMINATION
        )

        # Update limit and bedtime from regulations
        self.timer_mode = DeviceTimerMode(self.parental_control_settings["playTimerRegulations"]["timerMode"])
        today_reg = self._get_today_regulation(now)
        limit_time = today_reg.get("timeToPlayInOneDay", {}).get("limitTime")
        self.limit_time = limit_time if limit_time is not None else -1
        bedtime_setting = today_reg.get("bedtime", {})
        bedtime_enabled = bedtime_setting.get("enabled", False)

        # Set bedtime_alarm first as we need it for extra_playing_time calculation
        if bedtime_enabled and bedtime_setting.get("endingTime"):
            self.bedtime_alarm = time(
                hour=bedtime_setting["endingTime"]["hour"],
                minute=bedtime_setting["endingTime"]["minute"],
            )
        else:
            self.bedtime_alarm = time(hour=0, minute=0)

        # Parse extra playing time based on whether bedtime is enabled
        extra_playing_time_data = pcs.get("ownedDevice", {}).get("device", {}).get("extraPlayingTime")
        self.extra_playing_time = None
        if extra_playing_time_data is not None:
            if bedtime_enabled and extra_playing_time_data.get("bedtime"):
                # When bedtime is enabled, calculate the difference between new bedtime and original bedtime
                extended_bedtime_data = extra_playing_time_data.get("bedtime", {}).get("endTime")
                if extended_bedtime_data:
                    extended_bedtime = time(
                        hour=extended_bedtime_data["hour"],
                        minute=extended_bedtime_data["minute"],
                    )
                    # Calculate difference in minutes
                    original_minutes = self.bedtime_alarm.hour * 60 + self.bedtime_alarm.minute
                    extended_minutes = extended_bedtime.hour * 60 + extended_bedtime.minute
                    self.extra_playing_time = extended_minutes - original_minutes
                    # Update bedtime_alarm to the extended bedtime
                    self.bedtime_alarm = extended_bedtime
            else:
                # When bedtime is disabled, use inOneDay duration
                in_one_day = extra_playing_time_data.get("inOneDay")
                if in_one_day is not None:
                    self.extra_playing_time = in_one_day.get("duration")
        if bedtime_setting.get("enabled") and bedtime_setting["startingTime"]:
            self.bedtime_end = time(
                hour=bedtime_setting["startingTime"]["hour"],
                minute=bedtime_setting["startingTime"]["minute"],
            )
        else:
            self.bedtime_end = time(hour=0, minute=0)

    def _calculate_times(self, now: datetime):
        """Calculate times from parental control settings."""
        if not isinstance(self.daily_summaries, list) or not self.daily_summaries:
            return
        if len(self.daily_summaries) == 0:
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

    def _calculate_today_remaining_time(self, now: datetime):
        """Calculates the remaining playing time for today."""
        self.stats_update_failed = True  # Assume failure until success
        try:
            minutes_in_day = 1440  # 24 * 60
            current_minutes_past_midnight = now.hour * 60 + now.minute

            if self.limit_time in (-1, None):
                # No play limit, so remaining time is until end of day.
                time_remaining_by_play_limit = minutes_in_day - current_minutes_past_midnight
            else:
                # Calculate remaining time from play limit, adding any extra playing time
                effective_limit = self.limit_time
                if self.extra_playing_time:
                    effective_limit += self.extra_playing_time
                time_remaining_by_play_limit = effective_limit - self.today_playing_time

            # 2. Calculate remaining time until bedtime
            if self.bedtime_alarm and self.bedtime_alarm != time(hour=0, minute=0) and self.alarms_enabled:
                bedtime_dt = datetime.combine(now.date(), self.bedtime_alarm)
                if bedtime_dt > now:  # Bedtime is in the future today
                    time_remaining_by_bedtime = (bedtime_dt - now).total_seconds() / 60
                else:  # Bedtime has passed
                    time_remaining_by_bedtime = 0.0
            else:
                time_remaining_by_bedtime = minutes_in_day - current_minutes_past_midnight

            # Effective remaining time is the minimum of the two constraints
            effective_remaining_time = min(time_remaining_by_play_limit, time_remaining_by_bedtime)
            self.today_time_remaining = int(max(0.0, effective_remaining_time))
            _LOGGER.debug(
                "Calculated today's remaining time: %s minutes",
                self.today_time_remaining,
            )
            self.stats_update_failed = False
        except (ValueError, TypeError, AttributeError) as err:
            _LOGGER.warning("Unable to calculate remaining time for device %s: %s", self.name, err)

    async def _get_parental_control_setting(self, now: datetime):
        """Retreives parental control settings from the API."""
        _LOGGER.debug(">> Device._get_parental_control_setting()")
        response = await self._api.async_get_device_parental_control_setting(device_id=self.device_id)
        self._parse_parental_control_setting(response["json"], now)
        self._calculate_times(now)

    async def _get_daily_summaries(self, now: datetime):
        """Retrieve daily summaries."""
        _LOGGER.debug(">> Device._get_daily_summaries()")
        response = await self._api.async_get_device_daily_summaries(device_id=self.device_id)
        self.daily_summaries = response["json"]["dailySummaries"]
        _LOGGER.debug("New daily summary %s", self.daily_summaries)
        self._calculate_times(now)

    async def _get_extras(self):
        """Retrieve extra properties."""
        _LOGGER.debug(">> Device._get_extras()")
        if self.alarms_enabled is not None:
            # first refresh can come from self.extra without http request
            response = await self._api.async_get_account_device(device_id=self.device_id)
            self.extra = response["json"]["ownedDevice"]["device"]
        status = self.extra["alarmSetting"]["visibility"]
        self.alarms_enabled = status == str(AlarmSettingState.VISIBLE)
        _LOGGER.debug(
            "Cached alarms enabled to state %s for device %s",
            self.alarms_enabled,
            self.device_id,
        )

    async def get_monthly_summary(self, search_date: datetime = None) -> dict | None:
        """Get the monthly usage summary for a specific month.

        Args:
            search_date: The month to get the summary for. If None, returns the most recent available summary.

        Returns:
            Dictionary containing monthly usage data, or None if no summary is available.

        Example:
            ```python
            from datetime import datetime

            # Get summary for January 2024
            summary = await device.get_monthly_summary(datetime(2024, 1, 1))

            # Get most recent summary
            summary = await device.get_monthly_summary()
            ```
        """
        _LOGGER.debug(">> Device.get_monthly_summary(search_date=%s)", search_date)
        latest = False
        if search_date is None:
            try:
                response = await self._api.async_get_device_monthly_summaries(device_id=self.device_id)
            except HttpException as exc:
                _LOGGER.debug("Could not retrieve monthly summaries: %s", exc)
                return
            else:
                available_summaries = response["json"]["available"]
                _LOGGER.debug("Available monthly summaries: %s", available_summaries)
                if not available_summaries:
                    _LOGGER.debug("No monthly summaries available for device %s", self.device_id)
                    return None
                # Use the most recent available summary
                available_summary = available_summaries[0]
                search_date = datetime.strptime(
                    f"{available_summary['year']}-{available_summary['month']}-01",
                    "%Y-%m-%d",
                )
                _LOGGER.debug("Using search date %s for monthly summary request", search_date)
                latest = True

        try:
            response = await self._api.async_get_device_monthly_summary(
                device_id=self.device_id, year=search_date.year, month=search_date.month
            )
        except HttpException as exc:
            _LOGGER.warning(
                "HTTP Exception raised while getting monthly summary for device %s: %s",
                self.device_id,
                exc,
            )
            return None
        else:
            _LOGGER.debug(
                "Monthly summary query complete for device %s: %s",
                self.device_id,
                response["json"]["summary"],
            )
            if latest:
                self.last_month_summary = summary = response["json"]["summary"]
                # Generate player objects
                for player in response.get("json", {}).get("summary", {}).get("players", []):
                    profile = player.get("profile")
                    if not profile or not profile.get("playerId"):
                        continue
                    player_id = profile["playerId"]
                    if player_id not in self.players:
                        self.players[player_id] = Player.from_profile(profile)
                    self.players[player_id].month_summary = player.get("summary", {})
                return summary
            return response["json"]["summary"]

    def get_date_summary(self, input_date: datetime = datetime.now()) -> dict:
        """Get the usage summary for a specific date.

        Args:
            input_date: The date to get the summary for. Defaults to today.

        Returns:
            Dictionary containing usage data for the specified date.

        Raises:
            ValueError: If no summary exists for the given date or no summaries are available.

        Example:
            ```python
            from datetime import datetime, timedelta

            # Get today's summary
            today = device.get_date_summary()

            # Get yesterday's summary
            yesterday = device.get_date_summary(datetime.now() - timedelta(days=1))
            ```
        """
        if not self.daily_summaries:
            raise ValueError("No daily summaries available to search.")
        summary = [x for x in self.daily_summaries if x["date"] == input_date.strftime("%Y-%m-%d")]
        if len(summary) == 0:
            input_date -= timedelta(days=1)
            summary = [x for x in self.daily_summaries if x["date"] == input_date.strftime("%Y-%m-%d")]
        if len(summary) == 0:
            raise ValueError(f"A summary for the given date {input_date} does not exist")
        return summary

    def get_application(self, application_id: str) -> Application:
        """Get an Application object by its application ID.

        Args:
            application_id: The unique identifier for the application.

        Returns:
            The Application object for the specified ID.

        Raises:
            ValueError: If the application is not found.

        Example:
            ```python
            app = device.get_application("0100ABC001234000")
            print(f"Application: {app.name}")
            ```
        """
        if application_id in self.applications:
            return self.applications[application_id]
        raise ValueError(f"Application with id {application_id} not found.")

    def get_player(self, player_id: str) -> Player:
        """Get a Player object by player ID.

        Args:
            player_id: The unique identifier for the player.

        Returns:
            The Player object for the specified ID.

        Raises:
            ValueError: If the player is not found.

        Example:
            ```python
            player = device.get_player("player123")
            print(f"Player: {player.nickname}")
            ```
        """
        player = self.players.get(player_id)
        if player:
            return player
        raise ValueError(f"Player with id {player_id} not found.")

    @classmethod
    async def from_devices_response(cls, raw: dict, api, now: datetime = None) -> list["Device"]:
        """Parses a device request response body."""
        _LOGGER.debug("Parsing device list response")
        if "ownedDevices" not in raw.keys():
            raise ValueError("Invalid response from API.")
        devices = []
        for device in raw.get("ownedDevices", []):
            parsed = Device(api)
            parsed.device_id = device["deviceId"]
            parsed.name = device["label"]
            parsed.sync_state = device["parentalControlSettingState"]["updatedAt"]
            parsed.extra = device
            await parsed.update(now=now)
            devices.append(parsed)

        return devices

    @classmethod
    def from_device_response(cls, raw: dict, api) -> "Device":
        """Parses a single device request response body."""
        _LOGGER.debug("Parsing device response")
        if "deviceId" not in raw.keys():
            raise ValueError("Invalid response from API.")

        parsed = Device(api)
        parsed.device_id = raw["deviceId"]
        parsed.name = raw["label"]
        parsed.sync_state = raw["parentalControlSettingState"]["updatedAt"]
        parsed.extra = raw
        return parsed
