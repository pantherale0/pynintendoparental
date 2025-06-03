# pylint: disable=line-too-long
"""Defines a single Nintendo Switch device."""

import asyncio

from datetime import datetime, timedelta, time
from typing import Callable

from .api import Api
from .const import _LOGGER, DAYS_OF_WEEK
from .exceptions import HttpException
from .enum import AlarmSettingState, RestrictionMode
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
        self.players: list[Player] = []
        self.limit_time: int | float | None = 0
        self.timer_mode: str = ""
        self.today_playing_time: int | float = 0
        self.today_time_remaining: int | float = 0
        self.bedtime_alarm: time | None = None
        self.month_playing_time: int | float = 0
        self.today_disabled_time: int | float = 0
        self.today_exceeded_time: int | float = 0
        self.today_notices: list = []
        self.today_important_info: list = []
        self.today_observations: list = []
        self.last_month_summary: dict = {}
        self.applications: list[Application] = []
        self.whitelisted_applications: dict[str, bool] = {}
        self.last_month_playing_time: int = 0
        self.forced_termination_mode: bool = False
        self.alarms_enabled: bool = False
        self.stats_update_failed: bool = False
        self.application_update_failed: bool = False
        self._callbacks: list[Callable] = []
        _LOGGER.debug("Device init complete for %s", self.device_id)

    async def update(self):
        """Update data."""
        _LOGGER.debug(">> Device.update()")
        await asyncio.gather(
                self._get_daily_summaries(),
                self._get_parental_control_setting(),
                self.get_monthly_summary(),
                self._get_extras()
        )
        if self.players is None:
            self.players = Player.from_device_daily_summary(self.daily_summaries)
        else:
            for player in self.players:
                player.update_from_daily_summary(self.daily_summaries)
        for cb in self._callbacks:
            if is_awaitable(cb):
                await cb()
            else:
                cb()

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

    async def set_new_pin(self, pin: str):
        """Updates the pin for the device."""
        _LOGGER.debug(">> Device.set_new_pin(pin=REDACTED)")
        self.parental_control_settings["unlockCode"] = pin
        response = await self._api.async_update_unlock_code(
            new_code=pin,
            device_id=self.device_id
        )
        self._parse_parental_control_setting(response["json"])

    async def set_restriction_mode(self, mode: RestrictionMode):
        """Updates the restriction mode of the device."""
        _LOGGER.debug(">> Device.set_restriction_mode(mode=%s)", mode)
        self.parental_control_settings["playTimerRegulations"]["restrictionMode"] = str(mode)
        response = await self._api.async_update_play_timer(
            settings={
                "deviceId": self.device_id,
                "playTimerRegulations": self.parental_control_settings["playTimerRegulations"]
            }
        )
        self._parse_parental_control_setting(response["json"])

    async def set_bedtime_alarm(self, end_time: time = None, enabled: bool = True):
        """Update the bedtime alarm for the device."""
        _LOGGER.debug(">> Device.set_bedtime_alarm(end_time=%s, enabled=%s)",
                      end_time,
                      enabled)
        bedtime = {
            "enabled": enabled,
        }
        if end_time is not None:
            bedtime = {
                **bedtime,
                "endingTime": {
                    "hour": end_time.hour,
                    "minute": end_time.minute
                }
            }
        if self.timer_mode == "DAILY":
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["bedtime"] = bedtime
        else:
            self.parental_control_settings["playTimerRegulations"]["eachDayOfTheWeekRegulations"][
                DAYS_OF_WEEK[datetime.now().weekday()]
            ]["bedtime"] = bedtime
        response = await self._api.async_update_play_timer(
            settings={
                "deviceId": self.device_id,
                "playTimerRegulations": self.parental_control_settings["playTimerRegulations"]
            }
        )
        self._parse_parental_control_setting(response["json"])

    async def update_max_daily_playtime(self, minutes: int = 0):
        """Updates the maximum daily playtime of a device."""
        _LOGGER.debug(">> Device.update_max_daily_playtime(minutes=%s)",
                      minutes)
        if minutes > 360:
            raise ValueError("Only values up to 360 minutes (6 hours) are accepted.")
        ttpiod = True
        if minutes == -1:
            ttpiod = False
            minutes = None
        if self.timer_mode == "DAILY":
            _LOGGER.debug(
                "Setting timeToPlayInOneDay.limitTime for device %s to value %s",
                self.device_id,
                minutes)
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["enabled"] = ttpiod
            if "limitTime" in self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"] and minutes is None:
                self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"].pop("limitTime")
            else:
                self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["limitTime"] = minutes
        else:
            _LOGGER.debug(
                "Setting timeToPlayInOneDay.limitTime for device %s to value %s",
                self.device_id,
                minutes
            )
            day_of_week_regs = self.parental_control_settings["playTimerRegulations"]["eachDayOfTheWeekRegulations"]
            current_day = DAYS_OF_WEEK[datetime.now().weekday()]
            day_of_week_regs[current_day]["timeToPlayInOneDay"]["enabled"] = ttpiod
            if "limitTime" in day_of_week_regs[current_day]["timeToPlayInOneDay"] and minutes is None:
                day_of_week_regs[current_day]["timeToPlayInOneDay"].pop("limitTime")
            else:
                day_of_week_regs[current_day]["timeToPlayInOneDay"]["limitTime"] = minutes

        response = await self._api.async_update_play_timer(
            settings={
                "deviceId": self.device_id,
                "playTimerRegulations": self.parental_control_settings["playTimerRegulations"]
            }
        )
        self._parse_parental_control_setting(response["json"])

    def _update_applications(self):
        """Updates applications from daily summary."""
        _LOGGER.debug(">> Device._update_applications()")
        parsed_apps = Application.from_whitelist(self.parental_control_settings.get("whitelistedApplications", []))
        for app in parsed_apps:
            try:
                self.get_application(app.application_id).update(app)
                # self.get_application(app.application_id).update_today_time_played(self.daily_summaries[0])
            except ValueError:
                self.applications.append(app)

    def _update_day_of_week_regulations(self):
        """Override the limit / bed time for the device from parental_control_settings if individual days are configured."""
        day_of_week_regs = self.parental_control_settings["playTimerRegulations"].get("eachDayOfTheWeekRegulations", {})
        current_day = day_of_week_regs.get(DAYS_OF_WEEK[datetime.now().weekday()], {})
        self.timer_mode = self.parental_control_settings["playTimerRegulations"]["timerMode"]
        if self.timer_mode == "EACH_DAY_OF_THE_WEEK":
            self.limit_time = current_day.get("timeToPlayInOneDay", {}).get("limitTime", None)
        else:
            self.limit_time = self.parental_control_settings.get("playTimerRegulations", {}).get(
                "dailyRegulations", {}).get("timeToPlayInOneDay", {}).get("limitTime", None)

        if self.timer_mode == "EACH_DAY_OF_THE_WEEK":
            if current_day["bedtime"]["enabled"]:
                self.bedtime_alarm = time(hour=
                                        current_day["bedtime"]["endingTime"]["hour"],
                                        minute=current_day["bedtime"]["endingTime"]["minute"])
            else:
                self.bedtime_alarm = None
        else:
            bedtime_alarm = self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["bedtime"]
            if bedtime_alarm["enabled"]:
                self.bedtime_alarm = time(hour=
                                        bedtime_alarm["endingTime"]["hour"],
                                        minute=bedtime_alarm["endingTime"]["minute"])
            else:
                self.bedtime_alarm = None
        return True

    def _parse_parental_control_setting(self, pcs: dict):
        """Parse a parental control setting request response."""
        _LOGGER.debug(">> Device._parse_parental_control_setting()")
        self.parental_control_settings = pcs["parentalControlSetting"]
        if "bedtimeStartingTime" in self.parental_control_settings["playTimerRegulations"]:
            if self.parental_control_settings["playTimerRegulations"].get("bedtimeStartingTime", {}).get("hour", 0) == 0:
                self.parental_control_settings["playTimerRegulations"].pop("bedtimeStartingTime")
        self.forced_termination_mode = (
            self.parental_control_settings["playTimerRegulations"]["restrictionMode"] == str(RestrictionMode.FORCED_TERMINATION)
        )
        self._update_day_of_week_regulations()
        self._update_applications()

    async def _get_parental_control_setting(self):
        """Retreives parental control settings from the API."""
        _LOGGER.debug(">> Device._get_parental_control_setting()")
        response = await self._api.async_get_device_parental_control_setting(
            device_id=self.device_id
        )
        self._parse_parental_control_setting(response["json"])

    async def _get_daily_summaries(self):
        """Retrieve daily summaries."""
        _LOGGER.debug(">> Device._get_daily_summaries()")
        response = await self._api.async_get_device_daily_summaries(
            device_id = self.device_id
        )
        self.daily_summaries = response["json"]["dailySummaries"]
        _LOGGER.debug("New daily summary %s", self.daily_summaries)
        try:
            today_playing_time = self.get_date_summary()[0].get("playingTime", 0)
            self.today_playing_time = 0 if today_playing_time is None else today_playing_time
            today_disabled_time = self.get_date_summary()[0].get("disabledTime", 0)
            self.today_disabled_time = 0 if today_disabled_time is None else today_disabled_time
            today_exceeded_time = self.get_date_summary()[0].get("exceededTime", 0)
            self.today_exceeded_time = 0 if today_exceeded_time is None else today_exceeded_time
            _LOGGER.debug("Cached playing, disabled and exceeded time for today for device %s",
                        self.device_id)
            now = datetime.now()
            current_minutes_past_midnight = now.hour * 60 + now.minute
            minutes_in_day = 1440 # 24 * 60

            # 1. Calculate remaining time based on play limit

            time_remaining_by_play_limit = 0.0
            if self.limit_time is None:
                # No specific play limit, effectively limited by end of day for this calculation step.
                time_remaining_by_play_limit = float(minutes_in_day - current_minutes_past_midnight)
            elif self.limit_time == 0:
                time_remaining_by_play_limit = 0.0
            else:
                time_remaining_by_play_limit = float(self.limit_time - self.today_playing_time)

            time_remaining_by_play_limit = max(0.0, time_remaining_by_play_limit)

            # Initialize overall remaining time with play limit constraint
            effective_remaining_time = time_remaining_by_play_limit

            # 2. Factor in bedtime alarm, if any, to further constrain remaining time
            if self.bedtime_alarm is not None:
                bedtime_dt = datetime.combine(now.date(), self.bedtime_alarm)
                time_remaining_by_bedtime = 0.0
                if bedtime_dt > now: # Bedtime is in the future today
                    time_remaining_by_bedtime = (bedtime_dt - now).total_seconds() / 60
                    time_remaining_by_bedtime = max(0.0, time_remaining_by_bedtime)
                # else: Bedtime has passed for today or is now, so time_remaining_by_bedtime remains 0.0

                effective_remaining_time = min(effective_remaining_time, time_remaining_by_bedtime)

            self.today_time_remaining = int(max(0.0, effective_remaining_time)) # Ensure non-negative and integer
            _LOGGER.debug("Calculated and updated the amount of time remaining for today: %s", self.today_time_remaining)
            self.stats_update_failed = False
        except ValueError as err:
            _LOGGER.debug("Unable to update daily summary for device %s: %s", self.name, err)
            self.stats_update_failed = True

        current_month = datetime(
            year=datetime.now().year,
            month=datetime.now().month,
            day=1)
        month_playing_time: int = 0

        for summary in self.daily_summaries:
            date_parsed = datetime.strptime(summary["date"], "%Y-%m-%d")
            if date_parsed > current_month:
                month_playing_time += summary["playingTime"]
        self.month_playing_time = month_playing_time
        _LOGGER.debug("Cached current month playing time for device %s", self.device_id)
        parsed_apps = Application.from_daily_summary(self.daily_summaries)
        for app in parsed_apps:
            try:
                int_app = self.get_application(app.application_id)
                _LOGGER.debug("Updating cached app state %s for device %s",
                              int_app.application_id,
                              self.device_id)
                int_app.update(app)
            except ValueError:
                _LOGGER.debug("Creating new cached application entry %s for device %s",
                              app.application_id,
                              self.device_id)
                self.applications.append(app)

        # update application playtime
        try:
            for player in self.get_date_summary()[0].get("devicePlayers", []):
                for app in player.get("playedApps", []):
                    self.get_application(app["applicationId"]).update_today_time_played(app)
            self.application_update_failed = False
        except ValueError as err:
            _LOGGER.debug("Unable to retrieve applications for device %s: %s", self.name, err)
            self.application_update_failed = True

    async def _get_extras(self):
        """Retrieve extra properties."""
        _LOGGER.debug(">> Device._get_extras()")
        if self.alarms_enabled is not None:
            # first refresh can come from self.extra without http request
            response = await self._api.async_get_account_device(
                device_id = self.device_id
            )
            self.extra = response["json"]["ownedDevice"]["device"]
        status = self.extra["alarmSetting"]["visibility"]
        self.alarms_enabled = status == str(AlarmSettingState.VISIBLE)
        _LOGGER.debug("Cached alarms enabled to state %s for device %s",
                      self.alarms_enabled,
                      self.device_id)

    async def get_monthly_summary(self, search_date: datetime = None):
        """Gets the monthly summary."""
        _LOGGER.debug(">> Device.get_monthly_summary(search_date=%s)", search_date)
        latest = False
        if search_date is None:
            response = await self._api.async_get_device_monthly_summaries(
                device_id=self.device_id
            )
            _LOGGER.debug("Available monthly summaries: %s", response["json"]["available"])
            response = response["json"]["available"][0]
            search_date = datetime.strptime(f"{response['year']}-{response['month']}-01", "%Y-%m-%d")
            _LOGGER.debug("Using search date %s for monthly summary request", search_date)
            latest = True

        try:
            response = await self._api.async_get_device_monthly_summary(
                device_id = self.device_id,
                year=search_date.year,
                month=search_date.month
            )
            _LOGGER.debug("Monthly summary query complete for device %s: %s",
                        self.device_id,
                        response["json"]["summary"])
            if latest:
                self.last_month_summary = summary = response["json"]["summary"]
                return summary
            return response["json"]["summary"]
        except HttpException as exc:
            _LOGGER.warning("HTTP Exception raised while getting monthly summary for device %s: %s",
                            self.device_id,
                            exc)

    def get_date_summary(self, input_date: datetime = datetime.now()) -> dict:
        """Returns usage for a given date."""
        summary = [
            x for x in self.daily_summaries
            if x["date"] == input_date.strftime('%Y-%m-%d')
        ]
        if len(summary) == 0:
            input_date -= timedelta(days=1)
            summary = [
            x for x in self.daily_summaries
            if x["date"] == input_date.strftime('%Y-%m-%d')
        ]
        if len(summary) == 0:
            raise ValueError(f"A summary for the given date {input_date} does not exist")
        return summary

    def get_application(self, application_id: str) -> Application:
        """Returns a single application."""
        app = [x for x in self.applications
                if x.application_id == application_id]
        if len(app) == 1:
            return app[0]
        raise ValueError("Application not found.")

    def get_player(self, player_id: str) -> Player:
        """Returns a player."""
        player = [x for x in self.players
                  if x.player_id == player_id]
        if len(player) == 1:
            return player[0]
        raise ValueError("Player not found.")

    @classmethod
    async def from_devices_response(cls, raw: dict, api) -> list['Device']:
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
    def from_device_response(cls, raw: dict, api) -> 'Device':
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
