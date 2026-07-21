"""Tests for the Device class."""

import copy
import logging
from datetime import datetime, time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pynintendoauth.exceptions import HttpException
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from pynintendoparental.api import Api
from pynintendoparental.device import Device
from pynintendoparental.enum import (
    DeviceTimerMode,
    FunctionalRestrictionLevel,
    RestrictionMode,
)
from pynintendoparental.exceptions import (
    BedtimeOutOfRangeError,
    DailyPlaytimeOutOfRangeError,
    InvalidDeviceStateError,
)

from .conftest import FIXED_NOW
from .helpers import (
    clean_device_for_snapshot,
    daily_summaries_for,
    load_fixture,
    pcs_with_bedtime,
    pcs_with_extra_bedtime,
    pcs_with_extra_in_one_day,
    pcs_with_play_limit,
)

MONDAY = datetime(2023, 10, 30, 12, 0, 0)


async def test_device_parsing(device: Device, mock_api: Api, snapshot: SnapshotAssertion):
    """Test that the device class parsing works as expected."""
    mock_api.async_get_device_monthly_summary.assert_called_once()
    mock_api.async_get_device_daily_summaries.assert_called_once()
    mock_api.async_get_device_parental_control_setting.assert_called_once()

    test_device = copy.deepcopy(device)
    assert test_device.last_sync is not None
    assert test_device.last_sync == device.extra["synchronizedParentalControlSetting"]["synchronizedAt"]
    del test_device.extra["synchronizedParentalControlSetting"]["synchronizedAt"]
    assert test_device.last_sync is None
    del test_device.extra["synchronizedParentalControlSetting"]
    assert test_device.last_sync is None

    assert len(getattr(device, "_internal_callbacks")) == len(device.applications)
    assert clean_device_for_snapshot(device) == snapshot(exclude=props("today_time_remaining"))


async def test_player_discovery(device: Device, mock_api: Api):
    """Test that the device correctly parses players in different scenarios."""
    assert len(device.players) > 0

    monthly_summary_response = await load_fixture("device_monthly_summary")
    players = copy.deepcopy(monthly_summary_response["summary"]["players"][0])
    del players["profile"]["playerId"]
    monthly_summary_response["summary"]["players"][0] = players

    mock_api.async_get_device_monthly_summary.return_value = {
        "status": 200,
        "json": monthly_summary_response,
    }

    await device.update()
    assert mock_api.async_get_device_monthly_summary.call_count == 2


async def test_get_player(device: Device):
    """Test that the get_player method works as expected."""
    first_player_id = list(device.players.keys())[0]
    player = device.get_player(first_player_id)
    assert player.player_id == first_player_id

    with pytest.raises(ValueError):
        device.get_player("invalid_player_id")


async def test_get_application(device: Device):
    """Test that the get_application method works as expected."""
    first_app_id = list(device.applications.keys())[0]
    application = device.get_application(first_app_id)
    assert application.application_id == first_app_id

    with pytest.raises(ValueError):
        device.get_application("invalid_application_id")


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(time(hour=6, minute=30), id="mid"),
        pytest.param(time(hour=5, minute=0), id="lower_bound"),
        pytest.param(time(hour=9, minute=0), id="upper_bound"),
        pytest.param(time(hour=0, minute=0), id="disable"),
    ],
)
async def test_update_device_bedtime_end_time(device: Device, mock_api: Api, pcs: dict, value: time):
    """Test that updating the device bedtime end time works as expected."""
    expected_pcs = {"json": copy.deepcopy(pcs)}
    bedtime = expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"]["dailyRegulations"]["bedtime"]
    if value == time(0, 0):
        bedtime["enabled"] = False
    else:
        bedtime["enabled"] = True
        bedtime["startingTime"] = {"hour": value.hour, "minute": value.minute}

    mock_api.async_update_play_timer.return_value = expected_pcs
    await device.set_bedtime_end_time(value)

    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"],
    )
    assert device.bedtime_end == value


@pytest.mark.parametrize(
    "new_bedtime",
    [
        pytest.param(time(hour=20, minute=0), id="lower_bound"),
        pytest.param(time(hour=23, minute=0), id="upper_bound"),
        pytest.param(time(hour=21, minute=30), id="mid"),
        pytest.param(time(hour=0, minute=0), id="disable"),
    ],
)
async def test_update_device_bedtime_alarm(device: Device, mock_api: Api, pcs: dict, new_bedtime: time):
    """Test that updating the device bedtime alarm works as expected."""
    assert device.timer_mode is DeviceTimerMode.DAILY
    assert device.bedtime_alarm == time(0, 0)

    expected_pcs = {"json": copy.deepcopy(pcs)}
    ending_time = None if new_bedtime == time(0, 0) else {"hour": new_bedtime.hour, "minute": new_bedtime.minute}
    expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"]["dailyRegulations"]["bedtime"].update(
        {
            "enabled": new_bedtime != time(0, 0),
            "endingTime": ending_time,
        }
    )
    mock_api.async_update_play_timer.return_value = expected_pcs

    await device.set_bedtime_alarm(new_bedtime)
    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"],
    )
    assert device.parental_control_settings["playTimerRegulations"]["dailyRegulations"]["bedtime"]["enabled"] == (
        new_bedtime != time(0, 0)
    )
    assert device.bedtime_alarm == new_bedtime


@pytest.mark.parametrize(
    "side_effect,function_name,expected_log",
    [
        pytest.param(
            BedtimeOutOfRangeError(value=time(4, 0)),
            "set_bedtime_end_time",
            "Bedtime is outside of the allowed range.",
            id="end_too_early",
        ),
        pytest.param(
            BedtimeOutOfRangeError(value=time(0, 1)),
            "set_bedtime_end_time",
            "Bedtime is outside of the allowed range.",
            id="end_invalid",
        ),
        pytest.param(
            BedtimeOutOfRangeError(value=time(14, 30)),
            "set_bedtime_alarm",
            "Bedtime is outside of the allowed range.",
            id="alarm_afternoon",
        ),
    ],
)
async def test_update_device_exceptions(
    device: Device,
    side_effect: Exception,
    function_name: str,
    expected_log: str,
):
    """Test that updating bedtime raises exceptions as expected."""
    with pytest.raises(type(side_effect)) as err:
        await getattr(device, function_name)(side_effect.value)

    assert str(err.value) == f"{expected_log} Received value: {side_effect.value}"


@pytest.mark.parametrize(
    "mock_api_function,side_effect,expected_log",
    [
        pytest.param(
            "async_get_device_monthly_summary",
            HttpException(404, "test", "test"),
            "HTTP Exception raised while getting monthly summary for device {DEVICE_ID}: HTTP 404: test (test)",
            id="summary",
        ),
        pytest.param(
            "async_get_device_monthly_summaries",
            HttpException(404, "test", "test"),
            "Could not retrieve monthly summaries: HTTP 404: test (test)",
            id="summaries_list",
        ),
    ],
)
async def test_get_monthly_summary_error(
    device: Device,
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    mock_api_function: str,
    side_effect: Exception,
    expected_log: str,
):
    """Test that get_monthly_summary correctly handles and logs HTTP exceptions."""
    getattr(mock_api, mock_api_function).side_effect = side_effect

    await device.get_monthly_summary()
    assert expected_log.format(DEVICE_ID=device.device_id) in caplog.text


@pytest.mark.parametrize(
    "side_effect,timer_state,kwargs",
    [
        pytest.param(
            None,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": False,
                "day_of_week": "monday",
                "max_daily_playtime": 260,
            },
            id="success_int",
        ),
        pytest.param(
            None,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": False,
                "day_of_week": "monday",
                "max_daily_playtime": 260.0,
            },
            id="success_float",
        ),
        pytest.param(
            None,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": False,
                "day_of_week": "monday",
                "max_daily_playtime": None,
            },
            id="success_no_limit",
        ),
        pytest.param(
            None,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": True,
                "bedtime_end": time(hour=20, minute=0),
                "bedtime_start": time(hour=7, minute=0),
                "day_of_week": "monday",
                "max_daily_playtime": 260,
            },
            id="success_with_bedtime",
        ),
        pytest.param(
            InvalidDeviceStateError,
            DeviceTimerMode.DAILY,
            {
                "enabled": True,
                "bedtime_enabled": False,
                "day_of_week": "monday",
                "max_daily_playtime": 260,
            },
            id="error_daily_mode",
        ),
        pytest.param(
            ValueError,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": False,
                "day_of_week": "invalid_day",
                "max_daily_playtime": 260,
            },
            id="error_invalid_day",
        ),
        pytest.param(
            DailyPlaytimeOutOfRangeError,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": False,
                "day_of_week": "monday",
                "max_daily_playtime": 380,
            },
            id="error_playtime_range",
        ),
        pytest.param(
            BedtimeOutOfRangeError,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": True,
                "bedtime_start": time(hour=3, minute=0),
                "bedtime_end": time(hour=8, minute=0),
                "day_of_week": "monday",
                "max_daily_playtime": 380,
            },
            id="error_start_range",
        ),
        pytest.param(
            BedtimeOutOfRangeError,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": True,
                "bedtime_start": time(hour=6, minute=0),
                "bedtime_end": time(hour=8, minute=0),
                "day_of_week": "monday",
                "max_daily_playtime": 380,
            },
            id="error_end_range",
        ),
        pytest.param(
            BedtimeOutOfRangeError,
            DeviceTimerMode.EACH_DAY_OF_THE_WEEK,
            {
                "enabled": True,
                "bedtime_enabled": True,
                "day_of_week": "monday",
                "max_daily_playtime": 280,
            },
            id="error_missing_bedtime_times",
        ),
    ],
)
async def test_set_daily_restrictions(
    device: Device,
    mock_api: Api,
    pcs: dict,
    side_effect: type[Exception] | None,
    timer_state: DeviceTimerMode,
    kwargs: dict,
):
    """Test that set_daily_restrictions succeeds or raises as expected."""
    device._parse_parental_control_setting(pcs, MONDAY)  # pylint: disable=protected-access
    device.timer_mode = timer_state
    mock_api.async_update_play_timer.return_value = {"json": pcs}

    if side_effect is None:
        await device.set_daily_restrictions(**kwargs)
        mock_api.async_update_play_timer.assert_called_once()
    else:
        with pytest.raises(side_effect):
            await device.set_daily_restrictions(**kwargs)


async def test_set_daily_restrictions_bedtime_disabled_preserves_starting_time(
    device: Device,
    mock_api: Api,
    pcs: dict,
):
    """When bedtime_enabled=False, startingTime must be preserved from existing data."""
    pcs["parentalControlSetting"]["playTimerRegulations"]["eachDayOfTheWeekRegulations"]["monday"]["bedtime"][
        "startingTime"
    ] = {"hour": 7, "minute": 30}
    device._parse_parental_control_setting(pcs, MONDAY)  # pylint: disable=protected-access
    device.timer_mode = DeviceTimerMode.EACH_DAY_OF_THE_WEEK
    mock_api.async_update_play_timer.return_value = {"json": pcs}

    await device.set_daily_restrictions(
        enabled=True,
        bedtime_enabled=False,
        day_of_week="monday",
        max_daily_playtime=120,
    )

    mock_api.async_update_play_timer.assert_called_once()
    sent_regulations = mock_api.async_update_play_timer.call_args[0][1]
    monday_bedtime = sent_regulations["eachDayOfTheWeekRegulations"]["monday"]["bedtime"]
    assert monday_bedtime["enabled"] is False
    assert monday_bedtime["startingTime"] == {"hour": 7, "minute": 30}
    assert monday_bedtime["endingTime"] is None


async def test_set_functional_restriction_level(device: Device, mock_api: Api, pcs: dict):
    """Test that set_functional_restriction_level calls correctly."""
    device._parse_parental_control_setting(pcs, MONDAY)  # pylint: disable=protected-access

    new_level = FunctionalRestrictionLevel.TEEN
    expected_response = copy.deepcopy(pcs)
    expected_response["parentalControlSetting"]["functionalRestrictionLevel"] = "OLDER_TEENS"
    mock_api.async_update_restriction_level.return_value = {"json": expected_response}

    await device.set_functional_restriction_level(new_level)
    mock_api.async_update_restriction_level.assert_called_with(
        device.device_id,
        device.parental_control_settings,
    )


async def test_model_map(device: Device):
    """Test that the model map works as expected."""
    device.extra["platformGeneration"] = "P01"
    assert device.model == "Switch 2"

    device.extra["platformGeneration"] = "P00"
    assert device.model == "Switch"

    device.extra["platformGeneration"] = "invalid"
    assert device.model == "Unknown"

    device.extra.pop("platformGeneration")
    assert device.model == "Unknown"


async def test_device_callbacks(device: Device):
    """Test that the device callbacks work as expected."""
    assert len(device._callbacks) == 0
    assert len(device._internal_callbacks) == len(device.applications)

    sync_callback = Mock()
    async_callback = AsyncMock()
    device.add_device_callback(sync_callback)
    device.add_device_callback(async_callback)
    assert len(device._callbacks) == 2

    await device.update()
    sync_callback.assert_called_once()
    async_callback.assert_called_once()

    sync_callback.reset_mock()
    async_callback.reset_mock()
    device.remove_device_callback(sync_callback)
    device.remove_device_callback(async_callback)
    assert len(device._callbacks) == 0
    await device.update()
    sync_callback.assert_not_called()
    async_callback.assert_not_called()

    with pytest.raises(ValueError, match="Object must be callable."):
        device.remove_device_callback("not a function")

    with pytest.raises(ValueError, match="Object must be callable."):
        device.add_device_callback("not a function")


async def test_internal_callbacks(device: Device):
    """Test that the internal callbacks work as expected."""
    sync_callback = Mock()
    async_callback = AsyncMock()

    device._internal_callbacks.append(sync_callback)
    device._internal_callbacks.append(async_callback)
    assert len(device._internal_callbacks) == len(device.applications) + 2

    await device.update()
    sync_callback.assert_called_once_with(device=device)
    async_callback.assert_called_once_with(device=device)


@pytest.mark.parametrize(
    "pin",
    [
        pytest.param("1234"),
        pytest.param("2359434069346"),
    ],
)
async def test_set_new_pin(device: Device, mock_api: Api, pin: str):
    """Test that the set_new_pin method works as expected."""
    mock_api.async_update_unlock_code.return_value = {"json": await load_fixture("device_parental_control_setting")}
    await device.set_new_pin(pin)
    mock_api.async_update_unlock_code.assert_called_with(new_code=pin, device_id=device.device_id)


@pytest.mark.parametrize(
    "extra_time",
    [
        pytest.param(10),
        pytest.param(0),
    ],
)
async def test_add_extra_time(device: Device, mock_api: Api, extra_time: int):
    """Test that the add_extra_time method works as expected."""
    mock_api.async_update_extra_playing_time.return_value = None

    await device.add_extra_time(extra_time)
    mock_api.async_update_extra_playing_time.assert_called_with(device.device_id, extra_time)
    mock_api.async_confirm_extra_playing_time.assert_not_called()


async def test_add_extra_time_with_bedtime(device: Device, mock_api: Api):
    """Test add_extra_time uses confirmExtraPlayingTime when bedtime is active."""
    device.bedtime_alarm = time(hour=21, minute=0)
    device.alarms_enabled = True

    mock_api.async_confirm_extra_playing_time.return_value = None

    await device.add_extra_time(15)
    mock_api.async_confirm_extra_playing_time.assert_called_with(device.device_id, 15, True)
    mock_api.async_update_extra_playing_time.assert_not_called()


@pytest.mark.parametrize(
    "restriction_mode,expected_restriction_state_flag",
    [
        pytest.param(RestrictionMode.ALARM, False),
        pytest.param(RestrictionMode.FORCED_TERMINATION, True),
    ],
)
async def test_set_restriction_mode(
    device: Device,
    mock_api: Api,
    pcs: dict,
    restriction_mode: RestrictionMode,
    expected_restriction_state_flag: bool,
):
    """Test that the set_restriction_mode method works as expected."""
    expected_pcs = copy.deepcopy(pcs)
    expected_pcs["parentalControlSetting"]["playTimerRegulations"]["restrictionMode"] = str(restriction_mode)
    mock_api.async_update_play_timer.return_value = {"json": expected_pcs}

    await device.set_restriction_mode(restriction_mode)
    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        device.parental_control_settings["playTimerRegulations"],
    )
    assert device.forced_termination_mode == expected_restriction_state_flag


@pytest.mark.parametrize(
    "new_mode",
    [
        pytest.param(DeviceTimerMode.DAILY),
        pytest.param(DeviceTimerMode.EACH_DAY_OF_THE_WEEK),
    ],
)
async def test_set_timer_mode(device: Device, mock_api: Api, pcs: dict, new_mode: DeviceTimerMode):
    """Test that the set_timer_mode method works as expected."""
    expected_pcs = {"json": copy.deepcopy(pcs)}
    expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"]["timerMode"] = str(new_mode)
    mock_api.async_update_play_timer.return_value = expected_pcs
    await device.set_timer_mode(new_mode)
    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        device.parental_control_settings["playTimerRegulations"],
    )
    assert device.timer_mode == new_mode


@pytest.mark.parametrize(
    "minutes,expected_exception",
    [
        pytest.param(-2, DailyPlaytimeOutOfRangeError, id="below"),
        pytest.param(-1, None, id="unlimited"),
        pytest.param(0, None, id="zero"),
        pytest.param(1, None, id="one"),
        pytest.param(1.5, None, id="float"),
        pytest.param(360, None, id="max"),
        pytest.param(361, DailyPlaytimeOutOfRangeError, id="above"),
    ],
)
async def test_update_max_daily_playtime(
    device: Device,
    mock_api: Api,
    pcs: dict,
    minutes: int,
    expected_exception: type[Exception] | None,
):
    """Test that the update_max_daily_playtime method works as expected."""
    ttpiod = pcs["parentalControlSetting"]["playTimerRegulations"]["dailyRegulations"]["timeToPlayInOneDay"]
    if minutes == -1:
        ttpiod["enabled"] = False
        ttpiod.pop("limitTime")
    else:
        ttpiod["enabled"] = True
        ttpiod["limitTime"] = int(minutes)

    mock_api.async_update_play_timer.return_value = {"json": pcs}

    if expected_exception is None:
        await device.update_max_daily_playtime(minutes)
        mock_api.async_update_play_timer.assert_called_with(
            device.device_id,
            pcs["parentalControlSetting"]["playTimerRegulations"],
        )
    else:
        with pytest.raises(expected_exception):
            await device.update_max_daily_playtime(minutes)


async def test_parse_with_extra_playing_time(device: Device, mock_api: Api, pcs: dict):
    """Test that the `extra_playing_time` property is correctly set in the PCS parser."""
    assert device.extra_playing_time is None

    pcs_response = pcs_with_extra_in_one_day(pcs, duration=50)
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs_response}
    await device.update()

    assert device.extra_playing_time == 50


async def test_parse_with_extra_playing_time_bedtime_disabled_in_one_day_missing(
    device: Device, mock_api: Api, pcs: dict
):
    """If bedtime is disabled and PCS has extraPlayingTime but no inOneDay, keep unset."""
    pcs_response = pcs_with_bedtime(pcs, enabled=False)
    pcs_response["ownedDevice"]["device"]["extraPlayingTime"] = {
        "expiresAt": 1770335999,
        "bedtime": None,
    }
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs_response}
    await device.update()

    assert device.extra_playing_time is None


async def test_parse_with_extra_playing_time_bedtime_enabled(device: Device, mock_api: Api, pcs: dict):
    """Test that extra_playing_time is calculated from bedtime when bedtime is enabled."""
    pcs_response = pcs_with_bedtime(
        pcs,
        enabled=True,
        start=time(6, 0),
        end=time(21, 0),
    )
    pcs_response = pcs_with_extra_bedtime(pcs_response, time(21, 30))
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs_response}
    await device.update()

    assert device.extra_playing_time == 30
    assert device.bedtime_alarm == time(hour=21, minute=30)


async def test_parse_with_extra_playing_time_bedtime_midnight_wrap(device: Device, mock_api: Api, pcs: dict):
    """Test that extra_playing_time normalises when extended bedtime wraps past midnight."""
    pcs_response = pcs_with_bedtime(
        pcs,
        enabled=True,
        start=time(6, 0),
        end=time(23, 30),
    )
    pcs_response = pcs_with_extra_bedtime(pcs_response, time(0, 15))
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs_response}
    await device.update()

    assert device.extra_playing_time == 45
    assert device.bedtime_alarm == time(hour=0, minute=15)


async def test_parse_with_extra_playing_time_infinity(device: Device, mock_api: Api, pcs: dict):
    """Test that isInfinity is parsed into extra_playing_time as -1."""
    assert device.extra_playing_time is None

    pcs_response = pcs_with_extra_in_one_day(pcs, is_infinity=True)
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs_response}
    await device.update()

    assert device.extra_playing_time == -1


@pytest.mark.parametrize(
    "extra_kwargs,expected_remaining_from_limit",
    [
        pytest.param({"duration": 30}, 70, id="finite_extra"),
        pytest.param({"is_infinity": True}, None, id="infinite_extra"),
    ],
)
async def test_today_time_remaining_with_extra_playing_time(
    device: Device,
    mock_api: Api,
    pcs: dict,
    extra_kwargs: dict,
    expected_remaining_from_limit: int | None,
):
    """today_time_remaining accounts for finite or unlimited extra playing time."""
    now = FIXED_NOW
    pcs_response = pcs_with_play_limit(pcs, 60)
    pcs_response = pcs_with_bedtime(pcs_response, enabled=False)
    pcs_response = pcs_with_extra_in_one_day(pcs_response, **extra_kwargs)
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs_response}

    summaries = await load_fixture("device_daily_summaries")
    mock_api.async_get_device_daily_summaries.return_value = {
        "json": daily_summaries_for(summaries, now.strftime("%Y-%m-%d"), playing_time=20)
    }

    await device.update(now=now)

    assert device.limit_time == 60
    assert device.today_playing_time == 20

    minutes_until_eod = 1440 - (now.hour * 60 + now.minute)
    if expected_remaining_from_limit is None:
        assert device.extra_playing_time == -1
        assert device.today_time_remaining == minutes_until_eod
    else:
        assert device.extra_playing_time == 30
        assert device.today_time_remaining == min(expected_remaining_from_limit, minutes_until_eod)


@pytest.mark.parametrize(
    "hour,expected_remaining",
    [
        pytest.param(23, 75, id="evening"),
        pytest.param(12, 480, id="daytime"),
        pytest.param(1, 0, id="after_midnight"),
    ],
)
async def test_bedtime_rollover(device: Device, hour: int, expected_remaining: int):
    """Test midnight-wrap bedtime remaining-time behaviour across times of day."""
    device.bedtime_alarm = time(hour=0, minute=15)
    device.alarms_enabled = True
    device.limit_time = 480
    device.today_playing_time = 0

    now = FIXED_NOW.replace(hour=hour, minute=0, second=0, microsecond=0)
    device._calculate_today_remaining_time(now)  # pylint: disable=protected-access

    assert device.today_time_remaining == expected_remaining


@pytest.mark.parametrize(
    "summaries,dt,expect_debug,today_playing,today_disabled,today_exceeded,month_playing",
    [
        pytest.param("not a list", MONDAY, False, None, None, None, None, id="invalid"),
        pytest.param([], MONDAY, False, None, None, None, None, id="empty"),
        pytest.param(None, MONDAY, False, None, None, None, None, id="null"),
        pytest.param("fixture", MONDAY, True, 0, 0, 0, None, id="no_today"),
        pytest.param("fixture", FIXED_NOW, True, 60, 15, 20, 75, id="matching_day"),
    ],
)
async def test_calculate_times(
    device: Device,
    caplog: pytest.LogCaptureFixture,
    summaries,
    dt: datetime,
    expect_debug: bool,
    today_playing: int | None,
    today_disabled: int | None,
    today_exceeded: int | None,
    month_playing: int | None,
):
    """Test that `_calculate_times` handles invalid, empty, and valid summaries."""
    fixture_summaries = copy.deepcopy(device.daily_summaries)
    device.daily_summaries = fixture_summaries if summaries == "fixture" else summaries

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        device._calculate_times(dt)  # pylint: disable=protected-access

    matching_logs = [r for r in caplog.records if r.message == ">> Device._calculate_times()"]
    assert len(matching_logs) == (1 if expect_debug else 0)

    if today_playing is not None:
        assert device.today_playing_time == today_playing
        assert device.today_disabled_time == today_disabled
        assert device.today_exceeded_time == today_exceeded
    if month_playing is not None:
        assert device.month_playing_time == month_playing
    if summaries == "fixture" and dt == MONDAY:
        assert "No daily summary for today, assuming 0 playing time." in caplog.text


async def test_get_date_summary(device: Device):
    """Test get_date_summary for today, yesterday fallback, and missing dates."""
    device.daily_summaries = [
        {"date": "2025-12-08", "playingTime": 60},
        {"date": "2025-12-07", "playingTime": 15},
    ]

    today = device.get_date_summary(datetime(2025, 12, 8, 12, 0, 0))
    assert today[0]["date"] == "2025-12-08"

    # No entry for the given day → fall back one day
    yesterday = device.get_date_summary(datetime(2025, 12, 9, 12, 0, 0))
    assert yesterday[0]["date"] == "2025-12-08"

    with pytest.raises(ValueError, match="does not exist"):
        device.get_date_summary(datetime(2020, 1, 1, 12, 0, 0))

    device.daily_summaries = []
    with pytest.raises(ValueError, match="No daily summaries"):
        device.get_date_summary()


async def test_from_device_response(mock_api: Api):
    """Test from_device_response builds a Device without calling update()."""
    raw = (await load_fixture("account_devices"))["ownedDevices"][0]
    device = Device.from_device_response(raw, mock_api)

    assert device.device_id == raw["deviceId"]
    assert device.name == raw["label"]
    assert device.extra == raw
    mock_api.async_get_device_parental_control_setting.assert_not_called()

    with pytest.raises(ValueError, match="Invalid response"):
        Device.from_device_response({"label": "missing-id"}, mock_api)


async def test_from_devices_response_invalid(mock_api: Api):
    """Test from_devices_response rejects payloads without ownedDevices."""
    with pytest.raises(ValueError, match="Invalid response"):
        await Device.from_devices_response({}, mock_api)


async def test_get_monthly_summary_empty_available(device: Device, mock_api: Api):
    """When no monthly summaries are available, get_monthly_summary returns None."""
    mock_api.async_get_device_monthly_summaries.return_value = {"json": {"available": []}}
    mock_api.async_get_device_monthly_summary.reset_mock()

    assert await device.get_monthly_summary() is None
    mock_api.async_get_device_monthly_summary.assert_not_called()


async def test_get_monthly_summary_with_search_date(device: Device, mock_api: Api):
    """Providing search_date fetches that month without treating it as latest."""
    summary = {"playingTime": 100, "players": []}
    mock_api.async_get_device_monthly_summary.return_value = {"json": {"summary": summary}}
    mock_api.async_get_device_monthly_summaries.reset_mock()

    result = await device.get_monthly_summary(datetime(2024, 1, 1))

    assert result == summary
    mock_api.async_get_device_monthly_summaries.assert_not_called()
    mock_api.async_get_device_monthly_summary.assert_called_with(
        device_id=device.device_id, year=2024, month=1
    )


async def test_get_monthly_summary_fetch_returns_none(device: Device, mock_api: Api):
    """HTTP failure on a dated monthly summary returns None."""
    mock_api.async_get_device_monthly_summary.side_effect = HttpException(404, "test", "test")

    assert await device.get_monthly_summary(datetime(2024, 1, 1)) is None


async def test_get_extras_skips_http_when_alarms_enabled_unset(device: Device, mock_api: Api):
    """_get_extras can use cached extra when alarms_enabled is None."""
    device.alarms_enabled = None  # type: ignore[assignment]
    mock_api.async_get_account_device.reset_mock()

    await device._get_extras()  # pylint: disable=protected-access

    mock_api.async_get_account_device.assert_not_called()
    assert isinstance(device.alarms_enabled, bool)


async def test_callback_idempotent_add_and_missing_remove(device: Device):
    """Adding an existing callback is a no-op; removing a missing one is too."""
    callback = Mock()
    device.add_device_callback(callback)
    device.add_device_callback(callback)
    assert device._callbacks.count(callback) == 1

    device.remove_device_callback(Mock())  # not registered
    assert callback in device._callbacks
    device.remove_device_callback(callback)
    assert callback not in device._callbacks


async def test_calculate_today_remaining_time_failure(device: Device):
    """stats_update_failed stays True when remaining-time math raises."""
    with patch(
        "pynintendoparental.device._times.remaining_play_minutes",
        side_effect=TypeError("boom"),
    ):
        device._calculate_today_remaining_time(FIXED_NOW)  # pylint: disable=protected-access

    assert device.stats_update_failed is True


def test_api_dict_to_time_helpers():
    """Cover empty/None api dict conversion and time packing."""
    from pynintendoparental.device._helpers import api_dict_to_time, time_to_api_dict

    assert api_dict_to_time(None) is None
    assert api_dict_to_time({}) is None
    assert api_dict_to_time({"hour": 21, "minute": 30}) == time(21, 30)
    assert time_to_api_dict(time(7, 15)) == {"hour": 7, "minute": 15}


async def test_parse_extra_playing_time_bedtime_without_end_time(device: Device, mock_api: Api, pcs: dict):
    """Bedtime extra-playing-time with no endTime leaves extra_playing_time unset."""
    from .helpers import pcs_with_bedtime

    pcs_response = pcs_with_bedtime(pcs, enabled=True, start=time(6, 0), end=time(21, 0))
    pcs_response["ownedDevice"]["device"]["extraPlayingTime"] = {
        "bedtime": {"endTime": None},  # present but no usable endTime
        "inOneDay": None,
        "expiresAt": 1770335999,
    }
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs_response}
    await device.update()

    assert device.extra_playing_time is None
    assert device.bedtime_alarm == time(21, 0)
