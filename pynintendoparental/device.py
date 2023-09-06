# pylint: disable=line-too-long
"""Defines a single Nintendo Switch device."""

from datetime import date

from .api import Api
from .enum import AlarmSettingState
from .player import Player

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

    async def update(self):
        """Update data."""
        await self._update_daily_summaries()
        await self._update_parental_control_setting()
        self.players = Player.from_device_daily_summary(self.daily_summaries)

    async def set_new_pin(self, pin: str):
        """Updates the pin for the device."""
        self.parental_control_settings["unlockCode"] = pin
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
        await self._api.send_request(
            endpoint="update_device_parental_control_setting",
            body=self._get_update_parental_control_setting_body(),
            DEVICE_ID=self.device_id
        )
        await self._update_parental_control_setting()

    def _get_update_parental_control_setting_body(self):
        """Returns the dict that is required to update the parental control settings."""
        return {
            "unlockCode": self.parental_control_settings["unlockCode"],
            "functionalRestrictionLevel": self.parental_control_settings["functionalRestrictionLevel"],
            "customSettings": self.parental_control_settings["customSettings"],
            "playTimerRegulations": self.parental_control_settings["playTimerRegulations"]
        }

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
        self.today_playing_time = self.get_date_summary()[0].get("playingTime")/60

    async def set_alarm_state(self, state: AlarmSettingState):
        """Updates the alarm state for the device."""
        await self._api.send_request(
            endpoint="update_device_alarm_setting_state",
            body={
                "status": str(state)
            },
            DEVICE_ID = self.device_id
        )

    def get_date_summary(self, input_date: date = date.today()) -> dict:
        """Returns usage for a given date."""
        return [
            x for x in self.daily_summaries
            if x["date"] == input_date.strftime('%Y-%m-%d')
        ]

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
