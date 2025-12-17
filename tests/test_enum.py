"""Test enum methods."""

from pynintendoparental.enum import (
    AlarmSettingState,
    RestrictionMode,
    DeviceTimerMode,
    FunctionalRestrictionLevel,
)

def test_nintendo_enum_str():
    """Test NintendoEnum __str__ method."""
    assert str(AlarmSettingState.SUCCESS) == "SUCCESS"
    assert str(RestrictionMode.ALARM) == "ALARM"
    assert str(DeviceTimerMode.DAILY) == "DAILY"
    assert str(FunctionalRestrictionLevel.CUSTOM) == "CUSTOM"
    assert str(FunctionalRestrictionLevel.TEEN) == "OLDER_TEENS"
    assert str(FunctionalRestrictionLevel.YOUNG_TEENS) == "YOUNG_TEENS"
    assert str(FunctionalRestrictionLevel.YOUNG_CHILD) == "CHILDREN"
    assert str(FunctionalRestrictionLevel.NONE) == "NONE"

def test_nintendo_enum_options():
    """Test NintendoEnum options method."""
    assert AlarmSettingState.options() == ["SUCCESS", "TO_VISIBLE", "TO_INVISIBLE", "VISIBLE", "INVISIBLE"]
    assert RestrictionMode.options() == ["FORCED_TERMINATION", "ALARM"]
    assert DeviceTimerMode.options() == ["DAILY", "EACH_DAY_OF_THE_WEEK"]
    assert FunctionalRestrictionLevel.options() == ["NONE", "YOUNG_CHILD", "YOUNG_TEENS", "TEEN", "CUSTOM"]
