"""Nintendo Parental exceptions."""

from enum import StrEnum


class RangeErrorKeys(StrEnum):
    """Keys for range errors."""

    DAILY_PLAYTIME = "daily_playtime_out_of_range"
    BEDTIME = "bedtime_alarm_out_of_range"
    INVALID_DEVICE_STATE = "invalid_device_state"
    EXTRA_PLAYING_TIME_ACTIVE = "extra_playing_time_active"


class NoDevicesFoundException(Exception):
    """No devices were found for the account."""


class DeviceError(Exception):
    """Generic Device Error."""

    error_key: str

    def __init__(self, message: str) -> None:
        super().__init__(f"{self.__doc__} {message}")
        self.message = message


class InputValidationError(DeviceError):
    """Input Validation Failed."""

    value: object
    error_key: str

    def __init__(self, value: object) -> None:
        super().__init__(f"Received value: {value}")
        self.value = value


class BedtimeOutOfRangeError(InputValidationError):
    """Bedtime is outside of the allowed range."""

    error_key = RangeErrorKeys.BEDTIME


class DailyPlaytimeOutOfRangeError(InputValidationError):
    """Daily playtime is outside of the allowed range."""

    error_key = RangeErrorKeys.DAILY_PLAYTIME


class InvalidDeviceStateError(DeviceError):
    """The device is in an invalid state for the requested operation."""

    error_key = RangeErrorKeys.INVALID_DEVICE_STATE


class ExtraPlayingTimeActiveError(InvalidDeviceStateError):
    """Playtime limits and bedtime cannot be changed while extra playing time is active.

    This mirrors a restriction enforced by Nintendo's own app: cancel the
    active extra time (see `Device.cancel_extra_time`) before changing the
    daily limit, per-day restrictions, timer mode, or bedtime.
    """

    error_key = RangeErrorKeys.EXTRA_PLAYING_TIME_ACTIVE
