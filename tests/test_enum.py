"""Test enum methods."""

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

def test_nintendo_enum_options():
    """Test NintendoEnum options method."""
    assert AlarmSettingState.options() == ["SUCCESS", "TO_VISIBLE", "TO_INVISIBLE", "VISIBLE", "INVISIBLE"]
    assert RestrictionMode.options() == ["FORCED_TERMINATION", "ALARM"]
    assert DeviceTimerMode.options() == ["DAILY", "EACH_DAY_OF_THE_WEEK"]
    assert FunctionalRestrictionLevel.options() == ["NONE", "YOUNG_CHILD", "YOUNG_TEENS", "TEEN", "CUSTOM"]
