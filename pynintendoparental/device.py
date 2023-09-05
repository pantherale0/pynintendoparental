"""Defines a single Nintendo Switch device."""

from datetime import date

from .api import Api
from .enum import AlarmSettingState

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

    async def update(self):
        """Update data."""
        await self._update_daily_summaries()
        await self._update_parental_control_setting()

    async def set_new_pin(self, pin: str):
        """Updates the pin for the device."""
        self.parental_control_settings["unlockCode"] = pin
        await self._api.send_request(
            endpoint="update_device_parental_control_setting",
            body=self.parental_control_settings,
            DEVICE_ID=self.device_id
        )

    async def _update_parental_control_setting(self):
        """Retreives parental control settings from the API."""
        response = await self._api.send_request(
            endpoint="get_device_parental_control_setting",
            DEVICE_ID=self.device_id
        )
        self.parental_control_settings = response["json"]

    async def _update_daily_summaries(self):
        """Update daily summaries."""
        response = await self._api.send_request(
            endpoint="get_device_daily_summaries",
            DEVICE_ID = self.device_id
        )
        self.daily_summaries = response["json"]["items"]

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
