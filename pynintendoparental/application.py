"""A Nintendo application."""

import copy
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from .api import Api
from .const import _LOGGER
from .enum import SafeLaunchSetting
from .utils import current_datetime, is_awaitable

if TYPE_CHECKING:
    from .device import Device


class Application:
    """A Nintendo Switch game or application.

    Represents a game or application on a Nintendo Switch console with parental control settings.

    Attributes:
        application_id: Unique identifier for the application.
        name: Display name of the application.
        image_url: URL to the application's icon image.
        safe_launch_setting: Whether the app is on the Allow List (bypasses age restrictions).
        today_time_played: Total time played today across all players in minutes.
        first_played_date: Date when the application was first played.
        playing_days: Number of days the application has been played.
        shop_url: URL to the application in the Nintendo eShop.
    """

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
        self._device: Device | None = None

        # Register internal callbacks
        callbacks.append(self._internal_update_callback)

    def __eq__(self, other: object) -> bool:
        """Check if the application is equal to another object."""
        if not isinstance(other, Application):
            return False
        return self.application_id == other.application_id and self.name == other.name

    async def set_safe_launch_setting(self, safe_launch_setting: SafeLaunchSetting):
        """Set the application's status on the Allow List.

        Applications on the Allow List can bypass general age/content restrictions.

        Args:
            safe_launch_setting: The setting to apply. Options are:
                - SafeLaunchSetting.NONE: Remove from Allow List (apply normal restrictions).
                - SafeLaunchSetting.ALLOW: Add to Allow List (bypass restrictions).

        Raises:
            ValueError: If the application data is not properly initialized.
            LookupError: If the application is no longer in the whitelist.

        Example:
            ```python
            from pynintendoparental.enum import SafeLaunchSetting

            await app.set_safe_launch_setting(SafeLaunchSetting.ALLOW)
            ```
        """
        if not self._device or "whitelistedApplicationList" not in self._parental_control_settings:
            raise ValueError("Unable to set SafeLaunchSetting, callbacks not executed.")
        # Update the application safe_launch_setting in the PCS
        pcs = copy.deepcopy(self._parental_control_settings)
        for app in pcs["whitelistedApplicationList"]:
            if app["applicationId"].upper() == self.application_id.upper():
                app["safeLaunch"] = str(safe_launch_setting)
                break
        else:
            raise LookupError("Unable to set SafeLaunchSetting, application no longer in whitelist.")

        await self._send_api_update(
            self._api.async_update_restriction_level,
            self._device_id,
            pcs,
            now=current_datetime(self._api._tz),
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
        for app in self._parental_control_settings.get("whitelistedApplicationList", []):
            if app["applicationId"].upper() == self.application_id.upper():
                self.safe_launch_setting = SafeLaunchSetting(app.get("safeLaunch", "NONE"))
                self.image_url = app["imageUri"]
                break
        total_time_played: int = 0
        if self._daily_summary:
            for player_summary in self._daily_summary[0].get("players", []):
                for player_app in player_summary.get("playedGames", []):
                    if player_app["meta"]["applicationId"].upper() == self.application_id.upper():
                        total_time_played += player_app["playingTime"]
                        break
        self.today_time_played = total_time_played

        for cb in self._callbacks:
            if is_awaitable(cb):
                await cb(self)
            else:
                cb(self)

    def add_application_callback(self, callback: Callable):
        """Add a callback function to be called when application state changes.

        Args:
            callback: A callable function. Can be sync or async.

        Raises:
            ValueError: If the provided object is not callable.

        Example:
            ```python
            async def on_app_update(app):
                print(f"App {app.name} updated!")

            app.add_application_callback(on_app_update)
            ```
        """
        if not callable(callback):
            raise ValueError("Object must be callable.")
        self._callbacks.append(callback)

    def remove_application_callback(self, callback: Callable):
        """Remove a previously registered application callback.

        Args:
            callback: The callback function to remove.

        Raises:
            ValueError: If the callback is not found.
        """
        if callback not in self._callbacks:
            raise ValueError("Callback not found.")
        self._callbacks.remove(callback)


class ApplicationRegistry:
    """Registry of applications for a device."""

    def __init__(self):
        """Initialise the application registry."""
        self._applications: list[Application] = []
        self._application_ids: set[str] = set()

    def __contains__(self, application_id: str) -> bool:
        """Check if an application is in the registry."""
        return application_id in self._application_ids

    def __len__(self) -> int:
        """Get the number of applications in the registry."""
        return len(self._applications)

    def __iter__(self):
        """Iterate over the applications in the registry."""
        yield from self._applications

    def get_application(self, application_id: str) -> Application:
        """Get an application by its ID."""
        if application_id not in self._application_ids:
            raise ValueError(f"Application {application_id} not found.")
        for application in self._applications:
            if application.application_id == application_id:
                return application

    def get_application_by_name(self, name: str) -> Application:
        """Get an application by its name."""
        for application in self._applications:
            if application.name == name:
                return application
        raise ValueError(f"Application {name} not found.")

    def add_application(self, application: Application):
        """Add an application to the registry."""
        if application.application_id in self._application_ids:
            raise ValueError(f"Application {application.application_id} already in registry.")
        self._applications.append(application)
        self._application_ids.add(application.application_id)

    def remove_application(self, application_id: str):
        """Remove an application from the registry."""
        if application_id not in self._application_ids:
            raise ValueError(f"Application {application_id} not found.")
        self._applications.remove(self.get_application(application_id))
        self._application_ids.remove(application_id)


@dataclass(frozen=True, slots=True, repr=False)
class PlayedAppUsage:
    """Usage information for a played application for a given player."""

    application: Application
    playing_time: int
