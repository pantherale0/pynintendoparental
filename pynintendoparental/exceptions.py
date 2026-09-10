"""Nintendo Parental exceptions."""

from enum import StrEnum

from .enum import ExtraPlayingTimeStatus


class RangeErrorKeys(StrEnum):
    """Keys for range errors."""

    DAILY_PLAYTIME = "daily_playtime_out_of_range"
    BEDTIME = "bedtime_alarm_out_of_range"
    INVALID_DEVICE_STATE = "invalid_device_state"
    EXTRA_PLAYING_TIME_ACTIVE = "extra_playing_time_active"
    EXTRA_PLAYING_TIME_REQUEST_FAILED = "extra_playing_time_request_failed"


# Mirrors the copy the official app shows for each rejected status.
_EXTRA_PLAYING_TIME_STATUS_MESSAGES: dict[ExtraPlayingTimeStatus, str] = {
    ExtraPlayingTimeStatus.NO_EFFECT: "Nintendo made no change; play time can't be extended any more today.",
    ExtraPlayingTimeStatus.OVERTIME_ERROR: "Play time can't be extended past the set bedtime.",
    ExtraPlayingTimeStatus.DURING_LATE_NIGHT_ERROR: "Play time can't be extended during the late-night block.",
    ExtraPlayingTimeStatus.FAILED: "Nintendo reported the request failed.",
}


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
        super().__init__(f"Extra playing time is active for the current day: {extra_playing_time} minutes")
        self.extra_playing_time = extra_playing_time


class ExtraPlayingTimeRequestError(DeviceError):
    """Nintendo rejected the extra playing time request."""

    error_key = RangeErrorKeys.EXTRA_PLAYING_TIME_REQUEST_FAILED
    status: ExtraPlayingTimeStatus
    response: dict

    def __init__(self, status: ExtraPlayingTimeStatus, response: dict) -> None:
        detail = _EXTRA_PLAYING_TIME_STATUS_MESSAGES.get(status, "Unexpected response from Nintendo.")
        super().__init__(f"{detail} (status: {status})")
        self.status = status
        self.response = response
