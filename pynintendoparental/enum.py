"""Enums"""

from enum import Enum

class AlarmSettingState(Enum):
    """Alarm setting states."""
    SUCCESS = 0
    TO_VISIBLE = 1
    TO_INVISIBLE = 2
    VISIBLE = 4
    INVISIBLE = 8

    def __str__(self) -> str:
        return self.name

class RestrictionMode(Enum):
    """Restriction modes."""
    FORCED_TERMINATION = 0
    ALARM = 1

    def __str__(self) -> str:
        return self.name
