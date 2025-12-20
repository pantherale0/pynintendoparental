"""Test enum methods."""

import pytest

from pynintendoparental.enum import (
    AlarmSettingState,
    RestrictionMode,
    DeviceTimerMode,
    FunctionalRestrictionLevel,
)


@pytest.mark.parametrize(
    "enum_member, expected_str",
    [
        (AlarmSettingState.SUCCESS, "SUCCESS"),
        (RestrictionMode.ALARM, "ALARM"),
        (DeviceTimerMode.DAILY, "DAILY"),
        (FunctionalRestrictionLevel.CUSTOM, "CUSTOM"),
        (FunctionalRestrictionLevel.TEEN, "OLDER_TEENS"),
        (FunctionalRestrictionLevel.YOUNG_TEENS, "YOUNG_TEENS"),
        (FunctionalRestrictionLevel.YOUNG_CHILD, "CHILDREN"),
        (FunctionalRestrictionLevel.NONE, "NONE"),
    ],
)
def test_nintendo_enum_str(enum_member, expected_str):
    """Test NintendoEnum __str__ method."""
    assert str(enum_member) == expected_str


@pytest.mark.parametrize(
    "enum_class, expected_values",
    [
        (
            AlarmSettingState,
            ["SUCCESS", "TO_VISIBLE", "TO_INVISIBLE", "VISIBLE", "INVISIBLE"],
        ),
        (RestrictionMode, ["FORCED_TERMINATION", "ALARM"]),
        (DeviceTimerMode, ["DAILY", "EACH_DAY_OF_THE_WEEK"]),
        (
            FunctionalRestrictionLevel,
            ["NONE", "CHILDREN", "YOUNG_TEENS", "OLDER_TEENS", "CUSTOM"],
        ),
    ],
)
def test_nintendo_enum_options(enum_class, expected_values):
    """Test NintendoEnum options method."""
    assert enum_class.options() == expected_values
