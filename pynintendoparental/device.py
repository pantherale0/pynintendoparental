# pylint: disable=line-too-long
"""Defines a single Nintendo Switch device."""

from datetime import datetime, timedelta

from .api import Api
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
        self.extra: dict = None
        self._api: Api = api
        self.daily_summaries: dict = None
        self.parental_control_settings: dict = None
        self.players: list[Player] = None
        self.limit_time: int = None
        self.previous_limit_time: int = None
        self.today_playing_time: int = None
        self.month_playing_time: int = None
        self.today_disabled_time: int = None
        self.today_exceeded_time: int = None
        self.today_notices: list = []
        self.today_important_info: list = []
        self.today_observations: list = []
        self.last_month_summary: dict = None
        self.applications: list[Application] = []
        self.last_month_playing_time: int = None

    async def update(self):
        """Update data."""
        await self._update_daily_summaries()
        await self._update_parental_control_setting()
        await self.get_monthly_summary()
        if self.players is None:
            self.players = Player.from_device_daily_summary(self.daily_summaries)
        else:
            for player in self.players:
                player.update_from_daily_summary(self.daily_summaries)

    async def set_new_pin(self, pin: str):
        """Updates the pin for the device."""
        self.parental_control_settings["unlockCode"] = pin
        await self._set_parental_control_setting()

    async def set_restriction_mode(self, mode: RestrictionMode):
        """Updates the restriction mode of the device."""
        self.parental_control_settings["playTimerRegulations"]["restrictionMode"] = str(mode)
        await self._set_parental_control_setting()

    async def _set_parental_control_setting(self):
        """Shortcut method to deduplicate code used to update parental control settings."""
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
        self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["enabled"] = True
        self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["limitTime"] = minutes
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
        updated_apps = Application.from_daily_summary([])
        for app in self.applications:
            updated = [x for x in updated_apps if x.application_id == app.application_id][0]
            app.update(updated)

    async def _update_parental_control_setting(self):
        """Retreives parental control settings from the API."""
        response = await self._api.send_request(
            endpoint="get_device_parental_control_setting",
            DEVICE_ID=self.device_id
        )
        self.parental_control_settings = response["json"]
        self.limit_time = self.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]["limitTime"]
        if self.previous_limit_time is None:
            self.previous_limit_time = self.limit_time

    async def _update_daily_summaries(self):
        """Update daily summaries."""
        response = await self._api.send_request(
            endpoint="get_device_daily_summaries",
            DEVICE_ID = self.device_id
        )
        self.daily_summaries = response["json"]["items"]

        today_playing_time = self.get_date_summary()[0].get("playingTime", 0)
        self.today_playing_time = None if today_playing_time is None else today_playing_time/60
        today_disabled_time = self.get_date_summary()[0].get("disabledTime", 0)
        self.today_disabled_time = None if today_disabled_time is None else today_disabled_time/60
        today_exceeded_time = self.get_date_summary()[0].get("exceededTime", 0)
        self.today_exceeded_time = None if today_exceeded_time is None else today_exceeded_time/60

        self.today_important_info = self.get_date_summary()[0].get("importantInfos", [])
        self.today_notices = self.get_date_summary()[0].get("notices", [])
        self.today_observations = self.get_date_summary()[0].get("observations", [])

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

        parsed_apps = Application.from_daily_summary(self.daily_summaries)
        for app in parsed_apps:
            try:
                int_app = self.get_application(app.application_id)
                int_app.update(app)
            except ValueError:
                self.applications.append(app)

        # update application playtime
        for player in self.get_date_summary()[0].get("devicePlayers", []):
            for app in player.get("playedApps", []):
                self.get_application(app["applicationId"]).update_today_time_played(app)

    async def get_monthly_summary(self, search_date: datetime = None):
        """Gets the monthly summary."""
        latest = False
        if search_date is None:
            search_date = datetime.now()-timedelta(days=datetime.today().day+1)
            latest = True

        response = await self._api.send_request(
            endpoint="get_device_monthly_summary",
            DEVICE_ID = self.device_id,
            YEAR=search_date.year,
            MONTH=str(search_date.month).zfill(2)
        )
        if latest:
            self.last_month_summary = response["json"]["insights"]
            self.last_month_playing_time = self.last_month_summary["thisMonth"]["playingTime"]
            return self.last_month_summary
        return response["json"]["insights"]

    async def set_alarm_state(self, state: AlarmSettingState):
        """Updates the alarm state for the device."""
        await self._api.send_request(
            endpoint="update_device_alarm_setting_state",
            body={
                "status": str(state)
            },
            DEVICE_ID = self.device_id
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
