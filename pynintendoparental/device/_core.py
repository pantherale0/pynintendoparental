# pylint: disable=line-too-long
"""Defines a single Nintendo Switch device."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from typing import Callable

from pynintendoauth.exceptions import HttpException  # type: ignore[import-untyped]  # pylint: disable=import-error

from ..api import Api
from ..application import Application
from ..const import _LOGGER, DAYS_OF_WEEK
from ..enum import AlarmSettingState, DeviceTimerMode
from ..player import Player
from ._callbacks import DeviceCallbacksMixin
from ._parsing import DeviceParsingMixin
from ._settings import DeviceSettingsMixin
from ._times import DeviceTimesMixin


class Device(
    DeviceSettingsMixin,
    DeviceParsingMixin,
    DeviceTimesMixin,
    DeviceCallbacksMixin,
):
    """A Nintendo Switch device.

    Represents a single Nintendo Switch console with parental controls enabled.
    This class provides methods to monitor and control various parental control settings.

    Attributes:
        device_id: Unique identifier for the device.
        name: User-friendly name/label for the device.
        model: Device model (e.g., "Switch", "Switch 2").
        limit_time: Daily playtime limit in minutes (-1 if no limit).
        extra_playing_time: Extra playing time in minutes, or -1 if unlimited (TO_INFINITY).
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

    def __init__(self, api: Api) -> None:
        """INIT"""
        # Factories always set identity fields before API use; empty defaults keep types honest.
        self.device_id: str = ""
        self.name: str = ""
        self.sync_state: str = ""
        self.extra: dict = {}
        self._api: Api = api
        self.daily_summaries: list = []
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
        generation = self.generation
        return model_map.get(generation, "Unknown") if generation else "Unknown"

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

    async def update(self, now: datetime | None = None):
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
            self.get_monthly_summary(),
            self._get_extras(),
        )
        # Fetch PCS after daily summaries so extra_playing_time is not parsed from a
        # stale concurrent response (see #118 / debug-430f96).
        await self._get_parental_control_setting(now)
        for player in self.players.values():
            player.update_from_daily_summary(self.daily_summaries)
        self._update_applications()
        await self._execute_callbacks()

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

    async def get_monthly_summary(self, search_date: datetime | None = None) -> dict | None:
        """Get the monthly usage summary for a specific month.

        Args:
            search_date: The month to get the summary for. If None, returns the most recent available summary.

        Returns:
            Dictionary containing monthly usage data, or None if no summary is available.
        """
        _LOGGER.debug(">> Device.get_monthly_summary(search_date=%s)", search_date)
        latest = False
        if search_date is None:
            search_date = await self._resolve_latest_monthly_summary_date()
            if search_date is None:
                return None
            latest = True

        summary = await self._fetch_monthly_summary(search_date)
        if summary is None:
            return None
        if latest:
            self.last_month_summary = summary
            self._hydrate_players_from_monthly_summary(summary)
        return summary

    async def _resolve_latest_monthly_summary_date(self) -> datetime | None:
        """Discover the most recent available monthly summary date."""
        try:
            response = await self._api.async_get_device_monthly_summaries(device_id=self.device_id)
        except HttpException as exc:
            _LOGGER.debug("Could not retrieve monthly summaries: %s", exc)
            return None

        available_summaries = response["json"]["available"]
        _LOGGER.debug("Available monthly summaries: %s", available_summaries)
        if not available_summaries:
            _LOGGER.debug("No monthly summaries available for device %s", self.device_id)
            return None

        available_summary = available_summaries[0]
        search_date = datetime.strptime(
            f"{available_summary['year']}-{available_summary['month']}-01",
            "%Y-%m-%d",
        )
        _LOGGER.debug("Using search date %s for monthly summary request", search_date)
        return search_date

    async def _fetch_monthly_summary(self, search_date: datetime) -> dict | None:
        """Fetch a monthly summary for the given date."""
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

        summary = response["json"]["summary"]
        _LOGGER.debug(
            "Monthly summary query complete for device %s: %s",
            self.device_id,
            summary,
        )
        return summary

    def _hydrate_players_from_monthly_summary(self, summary: dict) -> None:
        """Create or update Player objects from a monthly summary payload."""
        for player in summary.get("players", []):
            profile = player.get("profile")
            if not profile or not profile.get("playerId"):
                continue
            player_id = profile["playerId"]
            if player_id not in self.players:
                self.players[player_id] = Player.from_profile(profile)
            self.players[player_id].month_summary = player.get("summary", {})

    def get_date_summary(self, input_date: datetime | None = None) -> list:
        """Get the usage summary for a specific date.

        Args:
            input_date: The date to get the summary for. Defaults to today.

        Returns:
            List containing usage data for the specified date.

        Raises:
            ValueError: If no summary exists for the given date or no summaries are available.
        """
        if input_date is None:
            input_date = datetime.now()
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
        """Get an Application object by its application ID."""
        if application_id in self.applications:
            return self.applications[application_id]
        raise ValueError(f"Application with id {application_id} not found.")

    def get_player(self, player_id: str) -> Player:
        """Get a Player object by player ID."""
        player = self.players.get(player_id)
        if player:
            return player
        raise ValueError(f"Player with id {player_id} not found.")

    @classmethod
    async def from_devices_response(cls, raw: dict, api: Api, now: datetime | None = None) -> list[Device]:
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
    def from_device_response(cls, raw: dict, api: Api) -> Device:
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
