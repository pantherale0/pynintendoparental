"""Enums"""

from enum import Enum

class AlarmSettingState(Enum):
    """Alarm setting states."""
    SUCCESS = 0
    TO_VISIBLE = 1
    TO_INVISIBLE = 2

    def __str__(self) -> str:
        return self.name
