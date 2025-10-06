"""Nintendo Parental exceptions."""

from datetime import time

class HttpException(Exception):
    """A HTTP error occured"""
    def __init__(self, status_code: int, message: str) -> None:
        """Initialize the exception."""
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.message}"

class InvalidSessionTokenException(HttpException):
    """Provided session token was invalid (invalid_grant)."""

class InvalidOAuthConfigurationException(HttpException):
    """The OAuth scopes are invalid."""

class NoDevicesFoundException(Exception):
    """No devices were found for the account."""

class InputValidationError(Exception):
    """Input Validation Failed."""
    value: object
    error_key: str

class BedtimeOutOfRangeError(InputValidationError):
    """Bedtime is outside of the allowed range."""

    error_key = "bedtime_alarm_out_of_range"

    def __init__(self, value: object) -> None:
        super().__init__()
        self.value = value
