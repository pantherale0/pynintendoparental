# pylint: disable=line-too-long
"""Defines a single Nintendo Switch device."""

import asyncio

from datetime import datetime, timedelta, time
from typing import Callable

from pynintendoauth.exceptions import HttpException

from .api import Api
from .const import _LOGGER, DAYS_OF_WEEK
from .exceptions import (
    BedtimeOutOfRangeError,
    DailyPlaytimeOutOfRangeError,
    InvalidDeviceStateError,
)
from .enum import (
    AlarmSettingState,
    DeviceTimerMode,
    FunctionalRestrictionLevel,
    RestrictionMode,
)
from .player import Player
from .utils import is_awaitable
from .application import Application


class Device:
    """A device"""

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
        """Return the model."""
        model_map = {"P00": "Switch", "P01": "Switch 2"}
        return model_map.get(self.generation, "Unknown")

    @property
    def generation(self) -> str | None:
        """Return the generation."""
        return self.extra.get("platformGeneration", None)

    @property
    def last_sync(self) -> float | None:
        """Return the last time this device was synced."""
        return self.extra.get("synchronizedParentalControlSetting", {}).get(
            "synchronizedAt", None
        )

    async def update(self):
        """Update data."""
        _LOGGER.debug(">> Device.update()")
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

    def add_device_callback(self, callback):
        """Add a callback to the device."""
        if not callable(callback):
            raise ValueError("Object must be callable.")
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_device_callback(self, callback):
        """Remove a given device callback."""
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
        """Updates the pin for the device."""
        _LOGGER.debug(">> Device.set_new_pin(pin=REDACTED)")
        await self._send_api_update(
            self._api.async_update_unlock_code, new_code=pin, device_id=self.device_id
        )

    async def add_extra_time(self, minutes: int):
        """Add extra time to the device."""
        _LOGGER.debug(">> Device.add_extra_time(minutes=%s)", minutes)
        # This endpoint does not return parental control settings, so we call it directly.
        await self._api.async_update_extra_playing_time(self.device_id, minutes)
        await self._get_parental_control_setting(datetime.now())

    async def set_restriction_mode(self, mode: RestrictionMode):
        """Updates the restriction mode of the device."""
        _LOGGER.debug(">> Device.set_restriction_mode(mode=%s)", mode)
        self.parental_control_settings["playTimerRegulations"]["restrictionMode"] = str(
            mode
        )
        response = await self._api.async_update_play_timer(
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
        )
        now = datetime.now()
        self._parse_parental_control_setting(
            response["json"], now
        )  # Don't need to recalculate times
        await self._execute_callbacks()

    async def set_bedtime_alarm(self, value: time):
        """Update the bedtime alarm for the device."""
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
            _LOGGER.debug(
                ">> Device.set_bedtime_alarm(value=%s): Daily timer mode", value
            )
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"][
                "bedtime"
            ] = regulation
        else:
            _LOGGER.debug(
                ">> Device.set_bedtime_alarm(value=%s): Each day timer mode", value
            )
            self.parental_control_settings["playTimerRegulations"][
                "eachDayOfTheWeekRegulations"
            ][DAYS_OF_WEEK[now.weekday()]]["bedtime"] = regulation
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
        """Update the bedtime end time for the device."""
        _LOGGER.debug(">> Device.set_bedtime_end_time(value=%s)", value)
        if not time(5, 0) <= value <= time(9, 0):
            raise BedtimeOutOfRangeError(value=value)
        now = datetime.now()
        if self.timer_mode == DeviceTimerMode.DAILY:
            regulation = self.parental_control_settings["playTimerRegulations"][
                "dailyRegulations"
            ]
        else:
            regulation = self.parental_control_settings["playTimerRegulations"][
                "eachDayOfTheWeekRegulations"
            ][DAYS_OF_WEEK[now.weekday()]]
        regulation["bedtime"]["startingTime"] = {
            "hour": value.hour,
            "minute": value.minute,
        }
        await self._send_api_update(
            self._api.async_update_play_timer,
            self.device_id,
            self.parental_control_settings["playTimerRegulations"],
            now=now,
        )

    async def set_timer_mode(self, mode: DeviceTimerMode):
        """Updates the timer mode of the device."""
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
        """Updates the daily restrictions of a device."""
        _LOGGER.debug(
            ">> Device.set_daily_restrictions(enabled=%s, bedtime_enabled=%s, day_of_week=%s, bedtime_start=%s, bedtime_end=%s, max_daily_playtime=%s)",
            enabled,
            bedtime_enabled,
            day_of_week,
            bedtime_start,
            bedtime_end,
            max_daily_playtime,
        )
        if self.timer_mode != DeviceTimerMode.EACH_DAY_OF_THE_WEEK:
            raise InvalidDeviceStateError(
                "Daily restrictions can only be set when timer_mode is EACH_DAY_OF_THE_WEEK."
            )
        if day_of_week not in DAYS_OF_WEEK:
            raise ValueError(f"Invalid day_of_week: {day_of_week}")
        regulation = self.parental_control_settings["playTimerRegulations"][
            "eachDayOfTheWeekRegulations"
        ][day_of_week]

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
        """Updates the functional restriction level of a device."""
        _LOGGER.debug(">> Device.set_functional_restriction_level(level=%s)", level)
        self.parental_control_settings["functionalRestrictionLevel"] = str(level)
        await self._send_api_update(
            self._api.async_update_restriction_level,
            self.device_id,
            self.parental_control_settings,
        )

    async def update_max_daily_playtime(self, minutes: int | float = 0):
        """Updates the maximum daily playtime of a device."""
        _LOGGER.debug(">> Device.update_max_daily_playtime(minutes=%s)", minutes)
        if isinstance(minutes, float):
            minutes = int(minutes)
        if minutes > 360 or minutes < -1:
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
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"][
                "timeToPlayInOneDay"
            ]["enabled"] = ttpiod
            if (
                "limitTime"
                in self.parental_control_settings["playTimerRegulations"][
                    "dailyRegulations"
                ]["timeToPlayInOneDay"]
                and minutes is None
            ):
                self.parental_control_settings["playTimerRegulations"][
                    "dailyRegulations"
                ]["timeToPlayInOneDay"].pop("limitTime")
            else:
                self.parental_control_settings["playTimerRegulations"][
                    "dailyRegulations"
                ]["timeToPlayInOneDay"]["limitTime"] = minutes
        else:
            _LOGGER.debug(
                "Setting timeToPlayInOneDay.limitTime for device %s to value %s",
                self.device_id,
                minutes,
            )
            day_of_week_regs = self.parental_control_settings["playTimerRegulations"][
                "eachDayOfTheWeekRegulations"
            ]
            current_day = DAYS_OF_WEEK[now.weekday()]
            day_of_week_regs[current_day]["timeToPlayInOneDay"]["enabled"] = ttpiod
            if (
                "limitTime" in day_of_week_regs[current_day]["timeToPlayInOneDay"]
                and minutes is None
            ):
                day_of_week_regs[current_day]["timeToPlayInOneDay"].pop("limitTime")
            else:
                day_of_week_regs[current_day]["timeToPlayInOneDay"]["limitTime"] = (
                    minutes
                )

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
            day_of_week_regs = self.parental_control_settings[
                "playTimerRegulations"
            ].get("eachDayOfTheWeekRegulations", {})
            return day_of_week_regs.get(DAYS_OF_WEEK[now.weekday()], {})
        return self.parental_control_settings.get("playTimerRegulations", {}).get(
            "dailyRegulations", {}
        )

    def _parse_parental_control_setting(self, pcs: dict, now: datetime):
        """Parse a parental control setting request response."""
        _LOGGER.debug(">> Device._parse_parental_control_setting()")
        self.parental_control_settings = pcs["parentalControlSetting"]
        self.parental_control_settings["playTimerRegulations"].pop("bedtimeStartingTime", None)
        self.parental_control_settings["playTimerRegulations"].pop("bedtimeEndingTime", None)
        self.forced_termination_mode = self.parental_control_settings[
            "playTimerRegulations"
        ]["restrictionMode"] == str(RestrictionMode.FORCED_TERMINATION)

        # Update limit and bedtime from regulations
        self.timer_mode = DeviceTimerMode(
            self.parental_control_settings["playTimerRegulations"]["timerMode"]
        )
        today_reg = self._get_today_regulation(now)
        limit_time = today_reg.get("timeToPlayInOneDay", {}).get("limitTime")
        self.limit_time = limit_time if limit_time is not None else -1
        extra_playing_time_data = (
            pcs.get("ownedDevice", {}).get("device", {}).get("extraPlayingTime")
        )
        self.extra_playing_time = None
        if extra_playing_time_data:
            self.extra_playing_time = extra_playing_time_data.get("inOneDay", {}).get(
                "duration"
            )

        bedtime_setting = today_reg.get("bedtime", {})
        if bedtime_setting.get("enabled") and bedtime_setting["endingTime"]:
            self.bedtime_alarm = time(
                hour=bedtime_setting["endingTime"]["hour"],
                minute=bedtime_setting["endingTime"]["minute"],
            )
        else:
            self.bedtime_alarm = time(hour=0, minute=0)
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
                time_remaining_by_play_limit = (
                    minutes_in_day - current_minutes_past_midnight
                )
            else:
                time_remaining_by_play_limit = self.limit_time - self.today_playing_time

            # 2. Calculate remaining time until bedtime
            if (
                self.bedtime_alarm
                and self.bedtime_alarm != time(hour=0, minute=0)
                and self.alarms_enabled
            ):
                bedtime_dt = datetime.combine(now.date(), self.bedtime_alarm)
                if bedtime_dt > now:  # Bedtime is in the future today
                    time_remaining_by_bedtime = (bedtime_dt - now).total_seconds() / 60
                else:  # Bedtime has passed
                    time_remaining_by_bedtime = 0.0
            else:
                time_remaining_by_bedtime = (
                    minutes_in_day - current_minutes_past_midnight
                )

            # Effective remaining time is the minimum of the two constraints
            effective_remaining_time = min(
                time_remaining_by_play_limit, time_remaining_by_bedtime
            )
            self.today_time_remaining = int(max(0.0, effective_remaining_time))
            _LOGGER.debug(
                "Calculated today's remaining time: %s minutes",
                self.today_time_remaining,
            )
            self.stats_update_failed = False
        except (ValueError, TypeError, AttributeError) as err:
            _LOGGER.warning(
                "Unable to calculate remaining time for device %s: %s", self.name, err
            )

    async def _get_parental_control_setting(self, now: datetime):
        """Retreives parental control settings from the API."""
        _LOGGER.debug(">> Device._get_parental_control_setting()")
        response = await self._api.async_get_device_parental_control_setting(
            device_id=self.device_id
        )
        self._parse_parental_control_setting(response["json"], now)
        self._calculate_times(now)

    async def _get_daily_summaries(self, now: datetime):
        """Retrieve daily summaries."""
        _LOGGER.debug(">> Device._get_daily_summaries()")
        response = await self._api.async_get_device_daily_summaries(
            device_id=self.device_id
        )
        self.daily_summaries = response["json"]["dailySummaries"]
        _LOGGER.debug("New daily summary %s", self.daily_summaries)
        self._calculate_times(now)

    async def _get_extras(self):
        """Retrieve extra properties."""
        _LOGGER.debug(">> Device._get_extras()")
        if self.alarms_enabled is not None:
            # first refresh can come from self.extra without http request
            response = await self._api.async_get_account_device(
                device_id=self.device_id
            )
            self.extra = response["json"]["ownedDevice"]["device"]
        status = self.extra["alarmSetting"]["visibility"]
        self.alarms_enabled = status == str(AlarmSettingState.VISIBLE)
        _LOGGER.debug(
            "Cached alarms enabled to state %s for device %s",
            self.alarms_enabled,
            self.device_id,
        )

    async def get_monthly_summary(self, search_date: datetime = None) -> dict | None:
        """Gets the monthly summary."""
        _LOGGER.debug(">> Device.get_monthly_summary(search_date=%s)", search_date)
        latest = False
        if search_date is None:
            try:
                response = await self._api.async_get_device_monthly_summaries(
                    device_id=self.device_id
                )
            except HttpException as exc:
                _LOGGER.debug("Could not retrieve monthly summaries: %s", exc)
                return
            else:
                available_summaries = response["json"]["available"]
                _LOGGER.debug("Available monthly summaries: %s", available_summaries)
                if not available_summaries:
                    _LOGGER.debug(
                        "No monthly summaries available for device %s", self.device_id
                    )
                    return None
                # Use the most recent available summary
                available_summary = available_summaries[0]
                search_date = datetime.strptime(
                    f"{available_summary['year']}-{available_summary['month']}-01",
                    "%Y-%m-%d",
                )
                _LOGGER.debug(
                    "Using search date %s for monthly summary request", search_date
                )
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
                for player in (
                    response.get("json", {}).get("summary", {}).get("players", [])
                ):
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
        """Returns usage for a given date."""
        if not self.daily_summaries:
            raise ValueError("No daily summaries available to search.")
        summary = [
            x
            for x in self.daily_summaries
            if x["date"] == input_date.strftime("%Y-%m-%d")
        ]
        if len(summary) == 0:
            input_date -= timedelta(days=1)
            summary = [
                x
                for x in self.daily_summaries
                if x["date"] == input_date.strftime("%Y-%m-%d")
            ]
        if len(summary) == 0:
            raise ValueError(
                f"A summary for the given date {input_date} does not exist"
            )
        return summary

    def get_application(self, application_id: str) -> Application:
        """Returns a single application."""
        if application_id in self.applications:
            return self.applications[application_id]
        raise ValueError(f"Application with id {application_id} not found.")

    def get_player(self, player_id: str) -> Player:
        """Returns a player."""
        player = self.players.get(player_id)
        if player:
            return player
        raise ValueError(f"Player with id {player_id} not found.")

    @classmethod
    async def from_devices_response(cls, raw: dict, api) -> list["Device"]:
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
            await parsed.update()
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
