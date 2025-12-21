"""A Nintendo application."""

from datetime import datetime
from typing import Callable

from .api import Api
from .const import _LOGGER
from .enum import SafeLaunchSetting
from .utils import is_awaitable


class Application:
    """Model for an application"""

    def __init__(
        self,
        app_id: str,
        name: str,
        device_id: str,
        api: Api,
    ) -> None:
        """Initialise a application."""
        self.application_id: str = app_id
        self._device_id: str = device_id
        self._api: Api = api
        self.first_played_date: datetime = None
        self.has_ugc: bool = None
        self.image_url: str = None  # uses small image from Nintendo
        self.playing_days: int = None
        self.shop_url: str = None
        self.name: str = name
        self.safe_launch_setting: SafeLaunchSetting = SafeLaunchSetting.NONE
        self.today_time_played: int = 0
        self._callbacks: list[Callable] = []
        self._parental_control_settings: dict = {}
        self._monthly_summary: dict = {}
        self._daily_summary: dict = {}

    async def _internal_update_callback(self, device):
        """Internal update callback method for the Device object to inform this Application has been updated."""
        if not device:
            return
        _LOGGER.debug(
            "Internal callback started for app %s - device %s",
            self.application_id,
            device.device_id,
        )
        self._device_id = device.device_id
        self._parental_control_settings = device.parental_control_settings
        self._monthly_summary = device.last_month_summary
        self._daily_summary = device.daily_summaries
        for app in self._parental_control_settings["whitelistedApplicationList"]:
            if app["applicationId"].capitalize() == self.application_id:
                self.safe_launch_setting = SafeLaunchSetting(
                    app.get("safeLaunch", "NONE")
                )
                self.image_url = app["imageUri"]
                break
        total_time_played: int = 0
        if self._daily_summary:
            for app in self._daily_summary[0].get("players", []):
                for player_app in app.get("playedGames", []):
                    if player_app["meta"]["applicationId"] == self.application_id:
                        total_time_played += player_app["playingTime"]
                        break
        self.today_time_played = total_time_played

        for cb in self._callbacks:
            if is_awaitable(cb):
                await cb(self)
            else:
                cb(self)

    def add_application_callback(self, callback):
        """Add a callback to the application."""
        if not callable(callback):
            raise ValueError("Object must be callable.")
        self._callbacks.append(callback)

    def remove_application_callback(self, callback):
        """Remove a callback from the application."""
        if callback not in self._callbacks:
            raise ValueError("Callback not found.")
        self._callbacks.remove(callback)
