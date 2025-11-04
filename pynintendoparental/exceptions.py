"""Nintendo Parental exceptions."""

from enum import StrEnum

class RangeErrorKeys(StrEnum):
    """Keys for range errors."""

    DAILY_PLAYTIME = "daily_playtime_out_of_range"
    BEDTIME = "bedtime_alarm_out_of_range"

class NoDevicesFoundException(Exception):
    """No devices were found for the account."""


class InputValidationError(Exception):
    """Input Validation Failed."""

    value: object
    error_key: str

    def __init__(self, value: object) -> None:
        super().__init__(f"{self.__doc__} Received value: {value}")
        self.value = value


class BedtimeOutOfRangeError(InputValidationError):
    """Bedtime is outside of the allowed range."""

    error_key = RangeErrorKeys.BEDTIME


class DailyPlaytimeOutOfRangeError(InputValidationError):
    """Daily playtime is outside of the allowed range."""

    error_key = RangeErrorKeys.DAILY_PLAYTIME
