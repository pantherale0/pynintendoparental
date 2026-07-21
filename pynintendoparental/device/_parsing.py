"""Parental control setting parsing for Device."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from ..const import _LOGGER
from ..enum import DeviceTimerMode, RestrictionMode
from ._helpers import api_dict_to_time, disabled_bedtime, time_to_minutes

if TYPE_CHECKING:
    from ._core import Device


class DeviceParsingMixin:
    """Mixin that parses parental control setting API responses onto Device."""

    parental_control_settings: dict
    forced_termination_mode: bool
    timer_mode: DeviceTimerMode | None
    limit_time: int | float | None
    bedtime_alarm: time | None
    bedtime_end: time | None
    extra_playing_time: int | None

    def _parse_parental_control_setting(self: Device, pcs: dict, now: datetime) -> None:  # type: ignore[misc]
        """Parse a parental control setting request response."""
        _LOGGER.debug(">> Device._parse_parental_control_setting()")
        self.parental_control_settings = pcs["parentalControlSetting"]
        self.parental_control_settings["playTimerRegulations"].pop("bedtimeStartingTime", None)
        self.parental_control_settings["playTimerRegulations"].pop("bedtimeEndingTime", None)
        self.forced_termination_mode = self.parental_control_settings["playTimerRegulations"]["restrictionMode"] == str(
            RestrictionMode.FORCED_TERMINATION
        )

        self.timer_mode = DeviceTimerMode(self.parental_control_settings["playTimerRegulations"]["timerMode"])
        today_reg = self._get_today_regulation(now)
        limit_time = today_reg.get("timeToPlayInOneDay", {}).get("limitTime")
        self.limit_time = limit_time if limit_time is not None else -1

        bedtime_setting = today_reg.get("bedtime", {})
        bedtime_enabled = bedtime_setting.get("enabled", False)
        self._parse_bedtime(bedtime_setting, bedtime_enabled)
        self._parse_extra_playing_time(pcs, bedtime_enabled)

    def _parse_bedtime(self: Device, bedtime_setting: dict, bedtime_enabled: bool) -> None:  # type: ignore[misc]
        """Parse bedtime alarm and end times from today's regulation."""
        # Set bedtime_alarm first — extra playing time may extend it.
        if bedtime_enabled and bedtime_setting.get("endingTime"):
            self.bedtime_alarm = api_dict_to_time(bedtime_setting["endingTime"])
        else:
            self.bedtime_alarm = disabled_bedtime()

        if bedtime_setting.get("enabled") and bedtime_setting.get("startingTime"):
            self.bedtime_end = api_dict_to_time(bedtime_setting["startingTime"])
        else:
            self.bedtime_end = disabled_bedtime()

    def _parse_extra_playing_time(self: Device, pcs: dict, bedtime_enabled: bool) -> None:  # type: ignore[misc]
        """Parse extra playing time; may extend bedtime_alarm when bedtime is on."""
        extra_playing_time_data = pcs.get("ownedDevice", {}).get("device", {}).get("extraPlayingTime")
        self.extra_playing_time = None
        if extra_playing_time_data is None:
            return

        if bedtime_enabled and extra_playing_time_data.get("bedtime"):
            extended_bedtime_data = extra_playing_time_data.get("bedtime", {}).get("endTime")
            if extended_bedtime_data and self.bedtime_alarm is not None:
                extended_bedtime = api_dict_to_time(extended_bedtime_data)
                if extended_bedtime is None:
                    return
                original_minutes = time_to_minutes(self.bedtime_alarm)
                extended_minutes = time_to_minutes(extended_bedtime)
                self.extra_playing_time = (extended_minutes - original_minutes) % 1440
                self.bedtime_alarm = extended_bedtime
            return

        in_one_day = extra_playing_time_data.get("inOneDay")
        if in_one_day is not None and in_one_day.get("isInfinity"):
            self.extra_playing_time = -1
        elif in_one_day is not None:
            self.extra_playing_time = in_one_day.get("duration")
        else:
            self.extra_playing_time = None
