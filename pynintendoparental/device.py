# pylint: disable=line-too-long
"""Defines a single Nintendo Switch device."""

import asyncio

from datetime import datetime, timedelta, time, date

from .api import Api
from .const import _LOGGER, DAYS_OF_WEEK
from .exceptions import HttpException
from .enum import AlarmSettingState, RestrictionMode
from .player import Player
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
        self.limit_time: int = 0
        self.timer_mode: str = ""
        self.bonus_time: int = 0
        self.bonus_time_set: datetime = None
        self.previous_limit_time: int = 0
        self.today_playing_time: int = 0
        self.bedtime_alarm: time
        self.month_playing_time: int = 0
        self.today_disabled_time: int = 0
        self.today_exceeded_time: int = 0
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
        _LOGGER.debug("Device init complete for %s", self.device_id)

    async def update(self):
        """Update data."""
        _LOGGER.debug("Updating device %s", self.device_id)
        await asyncio.gather(
                self._update_daily_summaries(),
                self._update_parental_control_setting(),
                self.get_monthly_summary(),
                self._update_extras()
        )
        if (self.bonus_time_set is not None) and (self.bonus_time_set < (datetime.strptime(
            f"{date.today().isoformat()}T00:00:00",
            "%Y-%m-%dT%H:%M:%S"
        ))):
            self.bonus_time = 0
            self.bonus_time_set = None
        if self.players is None:
            self.players = Player.from_device_daily_summary(self.daily_summaries)
        else:
            for player in self.players:
                player.update_from_daily_summary(self.daily_summaries)

    async def set_new_pin(self, pin: str):
        """Updates the pin for the device."""
        _LOGGER.debug("Setting new pin for device %s", self.device_id)
        self.parental_control_settings["unlockCode"] = pin
        await self._set_parental_control_setting()

    async def set_restriction_mode(self, mode: RestrictionMode):
        """Updates the restriction mode of the device."""
        _LOGGER.debug("Setting restriction mode for device %s", self.device_id)
        self.parental_control_settings["playTimerRegulations"]["restrictionMode"] = str(mode)
        await self._set_parental_control_setting()

    async def set_bedtime_alarm(self, end_time: time = None, enabled: bool = True):
        """Update the bedtime alarm for the device."""
        _LOGGER.debug("Setting bedtime alarm for device %s", self.device_id)
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
        await self._set_parental_control_setting()

    async def _set_parental_control_setting(self):
        """Shortcut method to deduplicate code used to update parental control settings."""
        _LOGGER.debug("Internal set parental control setting for device %s", self.device_id)
        await self._api.send_request(
            endpoint="update_device_parental_control_setting",
            body=self._get_update_parental_control_setting_body(),
            DEVICE_ID=self.device_id
        )
        await self._update_parental_control_setting()

    async def update_max_daily_playtime(self, minutes: int = 0, restore: bool = False):
        """Updates the maximum daily playtime of a device."""
        if restore and self.previous_limit_time == 0:
            raise RuntimeError("Invalid state for restore operation.")
        if restore:
            minutes = self.previous_limit_time
        elif not restore and minutes == 0:
            self.previous_limit_time = self.limit_time
        if self.timer_mode == "DAILY":
            _LOGGER.debug(
                "Setting timeToPlayInOneDay.limitTime for device %s to value %s with bonus %s",
                self.device_id,
                minutes,
                self.bonus_time)
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["enabled"] = True
            self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["limitTime"] = minutes + self.bonus_time
            await self._set_parental_control_setting()
        else:
            _LOGGER.debug(
                "Setting timeToPlayInOneDay.limitTime for device %s to value %s with bonus %s",
                self.device_id,
                minutes,
                self.bonus_time
            )
            day_of_week_regs = self.parental_control_settings["playTimerRegulations"].get("eachDayOfTheWeekRegulations", {})
            current_day = day_of_week_regs.get(DAYS_OF_WEEK[datetime.now().weekday()], {})
            day_of_week_regs[current_day]["timeToPlayInOneDay"]["limitTime"] = minutes + self.bonus_time
            day_of_week_regs[current_day]["timeToPlayInOneDay"]["enabled"] = True
            self.parental_control_settings["playTimerRegulations"]["eachDayOfTheWeekRegulations"][current_day] = day_of_week_regs
            await self._set_parental_control_setting()

    def _get_update_parental_control_setting_body(self):
        """Returns the dict that is required to update the parental control settings."""
        return {
            "unlockCode": self.parental_control_settings["unlockCode"],
            "functionalRestrictionLevel": self.parental_control_settings["functionalRestrictionLevel"],
            "customSettings": self.parental_control_settings["customSettings"],
            "playTimerRegulations": self.parental_control_settings["playTimerRegulations"]
        }

    def _update_applications(self):
        """Updates applications from daily summary."""
        _LOGGER.debug("Updating application stats for device %s", self.device_id)
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
            self.limit_time = current_day["timeToPlayInOneDay"]["limitTime"]
        else:
            self.limit_time = self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["limitTime"]

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


        if self.previous_limit_time is None:
            self.previous_limit_time = self.limit_time
        return True

    async def _update_parental_control_setting(self):
        """Retreives parental control settings from the API."""
        _LOGGER.debug("Updating parental control settings for device %s", self.device_id)
        response = await self._api.send_request(
            endpoint="get_device_parental_control_setting",
            DEVICE_ID=self.device_id
        )
        self.parental_control_settings = response["json"]
        self.forced_termination_mode = (
            self.parental_control_settings["playTimerRegulations"]["restrictionMode"] == str(RestrictionMode.FORCED_TERMINATION)
        )
        self._update_day_of_week_regulations()
        self._update_whitelisted_applications()
        self._update_applications()

    def _update_whitelisted_applications(self):
        """Update whitelisted applications from local parental control settings."""
        for app_id in self.parental_control_settings["whitelistedApplications"]:
            self.whitelisted_applications[app_id] = (
                self.parental_control_settings["whitelistedApplications"][app_id]["safeLaunch"] == "ALLOW"
            )

    async def _update_daily_summaries(self):
        """Update daily summaries."""
        _LOGGER.debug("Updating daily summaries for device %s", self.device_id)
        response = await self._api.send_request(
            endpoint="get_device_daily_summaries",
            DEVICE_ID = self.device_id
        )
        self.daily_summaries = response["json"]["items"]
        _LOGGER.debug("New daily summary %s", self.daily_summaries)
        try:
            today_playing_time = self.get_date_summary()[0].get("playingTime", 0)
            self.today_playing_time = None if today_playing_time is None else today_playing_time/60
            today_disabled_time = self.get_date_summary()[0].get("disabledTime", 0)
            self.today_disabled_time = None if today_disabled_time is None else today_disabled_time/60
            today_exceeded_time = self.get_date_summary()[0].get("exceededTime", 0)
            self.today_exceeded_time = None if today_exceeded_time is None else today_exceeded_time/60
            _LOGGER.debug("Set playing, disabled and exceeded time for today for device %s",
                        self.device_id)

            self.today_important_info = self.get_date_summary()[0].get("importantInfos", [])
            self.today_notices = self.get_date_summary()[0].get("notices", [])
            self.today_observations = self.get_date_summary()[0].get("observations", [])
            _LOGGER.debug("Set today important info, notices and observations for device %s",
                        self.device_id)
            self.stats_update_failed = False
        except ValueError as err:
            _LOGGER.warning("Unable to update daily summary for device %s: %s", self.name, err)
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
        _LOGGER.debug("Set current month playing time for device %s", self.device_id)
        parsed_apps = Application.from_daily_summary(self.daily_summaries)
        for app in parsed_apps:
            try:
                int_app = self.get_application(app.application_id)
                _LOGGER.debug("Updating app %s for device %s",
                              int_app.application_id,
                              self.device_id)
                int_app.update(app)
            except ValueError:
                _LOGGER.debug("Creating new application entry %s for device %s",
                              app.application_id,
                              self.device_id)
                self.applications.append(app)

        # update application playtime
        try:
            for player in self.get_date_summary()[0].get("devicePlayers", []):
                for app in player.get("playedApps", []):
                    self.get_application(app["applicationId"]).update_today_time_played(app)
            self.application_update_failed = False
        except ValueError:
            _LOGGER.warning("Unable to update applications for device %s: %s", self.name, err)
            self.application_update_failed = True

    async def _update_extras(self):
        """Update extra props."""
        _LOGGER.debug("Updating extra dicts for device %s", self.device_id)
        if self.alarms_enabled is not None:
            # first refresh can come from self.extra without http request
            response = await self._api.send_request(
                endpoint="get_account_device",
                ACCOUNT_ID = self._api.account_id,
                DEVICE_ID = self.device_id
            )
            self.extra = response["json"]
        status = self.extra["device"]["alarmSetting"]["visibility"]
        self.alarms_enabled = status == str(AlarmSettingState.VISIBLE)
        _LOGGER.debug("Set alarms enabled to state %s for device %s",
                      self.alarms_enabled,
                      self.device_id)

    async def get_monthly_summary(self, search_date: datetime = None):
        """Gets the monthly summary."""
        _LOGGER.debug("Updating monthly summary for device %s", self.device_id)
        latest = False
        if search_date is None:
            response = await self._api.send_request(
                endpoint="get_device_monthly_summaries",
                DEVICE_ID=self.device_id
            )
            _LOGGER.debug("Available monthly summaries: %s", response)
            response = response["json"]["indexes"][0]
            search_date = datetime.strptime(f"{response}-01", "%Y-%m-%d")
            _LOGGER.debug("Using search date %s for latest summary", search_date)
            latest = True

        try:
            response = await self._api.send_request(
                endpoint="get_device_monthly_summary",
                DEVICE_ID = self.device_id,
                YEAR=search_date.year,
                MONTH=str(search_date.month).zfill(2)
            )
            _LOGGER.debug("Monthly summary query complete for device %s: %s",
                        self.device_id,
                        response)
            if latest:
                self.last_month_summary = response["json"]["insights"]
                self.last_month_playing_time = self.last_month_summary["thisMonth"]["playingTime"]
                return self.last_month_summary
            return response["json"]["insights"]
        except HttpException as exc:
            _LOGGER.warning("HTTP Exception raised while getting monthly summary for device %s: %s",
                            self.device_id,
                            exc)

    async def set_alarm_state(self, state: AlarmSettingState):
        """Updates the alarm state for the device."""
        _LOGGER.debug("Setting alarm state to %s for device %s",
                      state,
                      self.device_id)
        await self._api.send_request(
            endpoint="update_device_alarm_setting_state",
            body={
                "status": str(state)
            },
            DEVICE_ID = self.device_id
        )

    async def set_whitelisted_application(self, app_id: str, allowed: bool):
        """Set the state of the application."""
        # check if the application exists first
        self.get_application(app_id)
        # take a snapshot of the whitelisted apps state
        current_state = self.parental_control_settings["whitelistedApplications"]
        current_state[app_id]["safeLaunch"] = "ALLOW" if allowed else "NONE"
        await self._api.send_request(
            endpoint="update_device_whitelisted_applications",
            body=current_state,
            DEVICE_ID=self.device_id
        )
        await self._update_parental_control_setting()

    async def give_bonus_time(self, minutes: int = 0):
        """Give additional bonus minutes to the device."""
        self.bonus_time += minutes
        self.bonus_time_set = datetime.now()
        await self.update_max_daily_playtime(
            minutes=self.limit_time + minutes,
            restore=False
        )

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
        if "items" not in raw.keys():
            raise ValueError("Invalid response from API.")
        devices = []
        for device in raw.get("items", []):
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
