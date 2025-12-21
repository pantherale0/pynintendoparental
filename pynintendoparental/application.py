"""A Nintendo application."""

import copy
from datetime import datetime
from typing import Callable, TYPE_CHECKING

from .api import Api
from .const import _LOGGER
from .enum import SafeLaunchSetting
from .utils import is_awaitable

if TYPE_CHECKING:
    from .device import Device


class Application:
    """Model for an application"""

    def __init__(
        self,
        app_id: str,
        name: str,
        device_id: str,
        api: Api,
        send_api_update: Callable,
        callbacks: list,
    ) -> None:
        """Initialise a application."""
        self.application_id: str = app_id
        self._device_id: str = device_id
        self._api: Api = api
        self._send_api_update: Callable = send_api_update
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
        self._device: "Device" | None = None

        # Register internal callbacks
        callbacks.append(self._internal_update_callback)

    async def set_safe_launch_setting(self, safe_launch_setting: SafeLaunchSetting):
        """Set the safe launch setting for the application."""
        if (
            not self._device
            or "whitelistedApplicationList" not in self._parental_control_settings
        ):
            raise ValueError("Unable to set SafeLaunchSetting, callbacks not executed.")
        # Update the application safe_launch_setting in the PCS
        pcs = copy.deepcopy(self._parental_control_settings)
        for app in pcs["whitelistedApplicationList"]:
            if app["applicationId"].upper() == self.application_id.upper():
                app["safeLaunch"] = str(safe_launch_setting)
                break
        else:
            raise LookupError(
                "Unable to set SafeLaunchSetting, application no longer in whitelist."
            )

        await self._send_api_update(
            self._api.async_update_restriction_level,
            self._device_id,
            pcs,
            now=datetime.now(),
        )

    async def _internal_update_callback(self, device: "Device"):
        """Internal update callback method for the Device object to inform this Application has been updated."""
        if not device:
            return
        _LOGGER.debug(
            "Internal callback started for app %s - device %s",
            self.application_id,
            device.device_id,
        )
        self._device = device
        self._device_id = device.device_id
        self._parental_control_settings = device.parental_control_settings
        self._monthly_summary = device.last_month_summary
        self._daily_summary = device.daily_summaries
        if "whitelistedApplicationList" not in self._parental_control_settings:
            _LOGGER.warning(
                ">> Device %s is missing a application whitelist, unable to update safe launch settings for %s",
                device.device_id,
                self.application_id,
            )
        for app in self._parental_control_settings.get(
            "whitelistedApplicationList", []
        ):
            if app["applicationId"].upper() == self.application_id.upper():
                self.safe_launch_setting = SafeLaunchSetting(
                    app.get("safeLaunch", "NONE")
                )
                self.image_url = app["imageUri"]
                break
        total_time_played: int = 0
        if self._daily_summary:
            for player_summary in self._daily_summary[0].get("players", []):
                for player_app in player_summary.get("playedGames", []):
                    if (
                        player_app["meta"]["applicationId"].upper()
                        == self.application_id.upper()
                    ):
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
