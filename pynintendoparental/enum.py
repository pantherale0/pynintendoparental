"""Enums"""

from enum import Enum, StrEnum


class NintendoEnum(Enum):
    """Base enum for Nintendo-related enums."""

    def __str__(self) -> str:
        return self.name

    @classmethod
    def options(cls) -> list[str]:
        """Return a list of string representations of the enum members."""
        return [str(e) for e in cls]


class AlarmSettingState(NintendoEnum):
    """Alarm setting states."""

    SUCCESS = 0
    TO_VISIBLE = 1
    TO_INVISIBLE = 2
    VISIBLE = 4
    INVISIBLE = 8


class RestrictionMode(NintendoEnum):
    """Restriction modes."""

    FORCED_TERMINATION = 0
    ALARM = 1


class SafeLaunchSetting(StrEnum, NintendoEnum):
    """Safe launch settings."""

    NONE = "NONE"
    ALLOW = "ALLOW"


class DeviceTimerMode(StrEnum, NintendoEnum):
    """Device timer modes."""

    DAILY = "DAILY"
    EACH_DAY_OF_THE_WEEK = "EACH_DAY_OF_THE_WEEK"


class FunctionalRestrictionLevel(StrEnum, NintendoEnum):
    """Functional restriction levels."""

    NONE = "NONE"
    YOUNG_CHILD = "CHILDREN"
    YOUNG_TEENS = "YOUNG_TEENS"
    TEEN = "OLDER_TEENS"
    CUSTOM = "CUSTOM"

    def __str__(self) -> str:
        return self.value

class ExtraPlayingTimeStatus(StrEnum, NintendoEnum):
    """Extra playing time statuses."""

    TO_ADDED = "TO_ADDED"
    TO_CANCELED = "TO_CANCELED"
    TO_INFINITY = "TO_INFINITY"
    SUCCESS = "SUCCESS"
    NO_EFFECT = "NO_EFFECT"
    OVERTIME_ERROR = "OVERTIME_ERROR"
    DURING_LATE_NIGHT_ERROR = "DURING_LATE_NIGHT_ERROR"
    FAILED = "FAILED"

    @property
    def is_error(self) -> bool:
        """Return True if the status is an error."""
        return self in [
            self.NO_EFFECT,
            self.OVERTIME_ERROR,
            self.DURING_LATE_NIGHT_ERROR,
            self.FAILED,
        ]
