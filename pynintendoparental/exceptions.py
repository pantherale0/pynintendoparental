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

class ExtraPlayingTimeActiveError(DeviceError):
    """Extra playing time is active for the current day."""

    error_key = RangeErrorKeys.EXTRA_PLAYING_TIME_ACTIVE
    extra_playing_time: int

    def __init__(self, extra_playing_time: int) -> None:
        super().__init__(
            f"Extra playing time is active for the current day: {extra_playing_time} minutes"
        )
        self.extra_playing_time = extra_playing_time
