"""Tests for the Device class."""

import copy
import logging
from datetime import datetime, time
from unittest.mock import AsyncMock, Mock

import pytest

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from pynintendoauth.exceptions import HttpException
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
from pynintendoparental.device import Device
from pynintendoparental.api import Api

from .helpers import load_fixture, clean_device_for_snapshot


async def test_device_parsing(mock_api: Api, snapshot: SnapshotAssertion):
    """Test that the device class parsing works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    mock_api.async_get_device_monthly_summary.assert_called_once()
    mock_api.async_get_device_daily_summaries.assert_called_once()
    mock_api.async_get_device_parental_control_setting.assert_called_once()

    test_device = copy.deepcopy(device)
    assert test_device.last_sync is not None
    assert (
        test_device.last_sync
        == device.extra["synchronizedParentalControlSetting"]["synchronizedAt"]
    )
    del test_device.extra["synchronizedParentalControlSetting"]["synchronizedAt"]
    assert test_device.last_sync is None
    del test_device.extra["synchronizedParentalControlSetting"]
    assert test_device.last_sync is None

    assert len(getattr(device, "_internal_callbacks")) == len(device.applications)

    assert clean_device_for_snapshot(device) == snapshot(
        exclude=props("today_time_remaining")
    )


async def test_player_discovery(mock_api: Api):
    """Test that the device correctly parses players in different scenarios."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.players) > 0

    # Test that the library correctly handles cases where the playerId is not found
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


async def test_get_player(mock_api: Api):
    """Test that the get_player method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.players) > 0

    # Get the ID of the first player in the dictionary
    first_player_id = list(device.players.keys())[0]
    player = device.get_player(first_player_id)
    assert player.player_id == first_player_id

    # Now test that it errors
    with pytest.raises(ValueError):
        device.get_player("invalid_player_id")


async def test_get_application(mock_api: Api):
    """Test that the get_application method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices: list[Device] = await Device.from_devices_response(
        devices_response, mock_api
    )
    assert len(devices) > 0
    device = devices[0]
    assert len(device.applications) > 0

    # Get the ID of the first application in the dict
    first_app_id = list(device.applications.keys())[0]
    application = device.get_application(first_app_id)
    assert application.application_id == first_app_id

    # Now test the errors
    with pytest.raises(ValueError):
        device.get_application("invalid_application_id")


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(time(hour=6, minute=30)),
        pytest.param(time(hour=5, minute=0)),  # lower bound
        pytest.param(time(hour=9, minute=0)),  # upper bound
        pytest.param(time(hour=0, minute=0)),  # Disable
    ],
)
async def test_update_device_bedtime_end_time(mock_api: Api, value: time):
    """Test that updating the device bedtime end time works as expected."""
    devices_response = await load_fixture("account_devices")
    pcs_response = {"json": await load_fixture("device_parental_control_setting")}
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.players) > 0

    expected_pcs = copy.deepcopy(pcs_response)
    bedtime = expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"][
        "dailyRegulations"
    ]["bedtime"]
    if value == time(0, 0):
        bedtime["startingTime"] = None
        bedtime["enabled"] = False
    else:
        bedtime["enabled"] = True
        bedtime["startingTime"] = {
            "hour": value.hour,
            "minute": value.minute,
        }

    mock_api.async_update_play_timer.return_value = (
        expected_pcs  # Override the response to correctly parse the data
    )
    await device.set_bedtime_end_time(value)

    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"],
    )

    assert device.bedtime_end == value


@pytest.mark.parametrize(
    "new_bedtime",
    [
        pytest.param(
            time(hour=20, minute=0)  # Lower bound
        ),
        pytest.param(
            time(hour=23, minute=0)  # Upper bound
        ),
        pytest.param(time(hour=21, minute=30)),
        pytest.param(time(hour=0, minute=0)),
    ],
)
async def test_update_device_bedtime_alarm(
    mock_api: Api,
    new_bedtime: time,
    caplog: pytest.LogCaptureFixture,
):
    """Test that updating the device bedtime alarm works as expected."""
    devices_response = await load_fixture("account_devices")
    pcs_response = {"json": await load_fixture("device_parental_control_setting")}
    mock_api.async_update_play_timer.return_value = pcs_response
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.players) > 0

    assert device.timer_mode is DeviceTimerMode.DAILY
    assert device.bedtime_alarm == time(0, 0)

    expected_pcs = copy.deepcopy(pcs_response)
    if new_bedtime == time(0, 0):
        ending_time = None
    else:
        ending_time = {"hour": new_bedtime.hour, "minute": new_bedtime.minute}
    expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"][
        "dailyRegulations"
    ]["bedtime"].update(
        {
            "enabled": (new_bedtime != time(0, 0)),
            "endingTime": ending_time,
        }
    )
    mock_api.async_update_play_timer.return_value = expected_pcs

    await device.set_bedtime_alarm(new_bedtime)
    assert f">> Device.set_bedtime_alarm(value={new_bedtime})" in caplog.text
    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"],
    )

    assert device.parental_control_settings["playTimerRegulations"]["dailyRegulations"][
        "bedtime"
    ]["enabled"] == (new_bedtime != time(0, 0))
    assert device.bedtime_alarm == new_bedtime


@pytest.mark.parametrize(
    "side_effect,function_name,expected_log",
    [
        pytest.param(
            BedtimeOutOfRangeError(value=time(4, 0)),
            "set_bedtime_end_time",
            "Bedtime is outside of the allowed range.",
        ),
        pytest.param(
            BedtimeOutOfRangeError(value=time(0, 1)),
            "set_bedtime_end_time",
            "Bedtime is outside of the allowed range.",
        ),
        pytest.param(
            BedtimeOutOfRangeError(value=time(14, 30)),
            "set_bedtime_alarm",
            "Bedtime is outside of the allowed range.",
        ),
    ],
)
async def test_update_device_exceptions(
    mock_api: Api, side_effect: Exception, function_name: str, expected_log: str
):
    """Test that updating the device bedtime end time raises exceptions as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.players) > 0

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
        ),
        pytest.param(
            "async_get_device_monthly_summaries",
            HttpException(404, "test", "test"),
            "Could not retrieve monthly summaries: HTTP 404: test (test)",
        ),
    ],
)
async def test_get_monthly_summary_error(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    mock_api_function: str,
    side_effect: Exception,
    expected_log: str,
):
    """Test that get_monthly_summary calls correctly handle and log HTTP exceptions."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.players) > 0

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
        ),
    ],
)
async def test_set_daily_restrictions(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception | None,
    timer_state: DeviceTimerMode,
    kwargs: dict,
):
    """Test that set_daily_restrictions calls correctly raises exceptions."""
    devices_response = await load_fixture("account_devices")
    pcs_response = await load_fixture("device_parental_control_setting")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    device._parse_parental_control_setting(  # pylint: disable=protected-access
        pcs_response,
        datetime(2023, 10, 30, 12, 0, 0),  # A Monday
    )
    assert len(device.players) > 0

    # Override the device timer mode for testing
    device.timer_mode = timer_state
    mock_api.async_update_play_timer.return_value = {"json": pcs_response}

    if side_effect is None:
        await device.set_daily_restrictions(**kwargs)
        mock_api.async_update_play_timer.assert_called_once()
    else:
        with pytest.raises(side_effect):
            await device.set_daily_restrictions(**kwargs)

    assert ">> Device.set_daily_restrictions" in caplog.text
    assert ">> Device._parse_parental_control_setting" in caplog.text


async def test_set_functional_restriction_level(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
):
    """Test that set_functional_restriction_level calls correctly."""
    devices_response = await load_fixture("account_devices")
    pcs_response = await load_fixture("device_parental_control_setting")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    device._parse_parental_control_setting(  # pylint: disable=protected-access
        pcs_response, datetime(2023, 10, 30, 12, 0, 0)
    )
    assert len(device.players) > 0

    new_level = FunctionalRestrictionLevel.TEEN
    expected_response = copy.deepcopy(pcs_response)
    expected_response["parentalControlSetting"]["functionalRestrictionLevel"] = (
        "OLDER_TEENS"
    )
    mock_api.async_update_restriction_level.return_value = {"json": expected_response}

    await device.set_functional_restriction_level(new_level)
    mock_api.async_update_restriction_level.assert_called_with(
        device.device_id,
        device.parental_control_settings,
    )

    assert ">> Device.set_functional_restriction_level" in caplog.text
    assert ">> Device._parse_parental_control_setting" in caplog.text


async def test_model_map(
    mock_api: Api,
):
    """Test that the model map works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    device.extra["platformGeneration"] = "P01"
    assert device.model == "Switch 2"

    device.extra["platformGeneration"] = "P00"
    assert device.model == "Switch"

    device.extra["platformGeneration"] = "invalid"
    assert device.model == "Unknown"

    device.extra.pop("platformGeneration")
    assert device.model == "Unknown"


async def test_device_callbacks(
    mock_api: Api,
):
    """Test that the device callbacks work as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

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

    # Remove a callback
    sync_callback.reset_mock()
    async_callback.reset_mock()
    device.remove_device_callback(sync_callback)
    device.remove_device_callback(async_callback)
    assert len(device._callbacks) == 0
    await device.update()
    sync_callback.assert_not_called()
    async_callback.assert_not_called()

    # Test removing a non-callable
    with pytest.raises(ValueError, match="Object must be callable."):
        device.remove_device_callback("not a function")

    # Test adding a non-callable
    with pytest.raises(ValueError, match="Object must be callable."):
        device.add_device_callback("not a function")


async def test_internal_callbacks(
    mock_api: Api,
):
    """Test that the internal callbacks work as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

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
async def test_set_new_pin(mock_api: Api, caplog: pytest.LogCaptureFixture, pin):
    """Test that the set_new_pin method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    mock_api.async_update_unlock_code.return_value = {
        "json": await load_fixture("device_parental_control_setting")
    }
    await device.set_new_pin(pin)
    mock_api.async_update_unlock_code.assert_called_with(
        new_code=pin, device_id=device.device_id
    )
    assert ">> Device.set_new_pin(pin=REDACTED)" in caplog.text


@pytest.mark.parametrize(
    "extra_time",
    [
        pytest.param(10),
        pytest.param(0),
    ],
)
async def test_add_extra_time(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    extra_time: int,
):
    """Test that the add_extra_time method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    mock_api.async_update_extra_playing_time.return_value = None

    await device.add_extra_time(extra_time)
    mock_api.async_update_extra_playing_time.assert_called_with(
        device.device_id, extra_time
    )
    assert f">> Device.add_extra_time(minutes={extra_time})" in caplog.text


@pytest.mark.parametrize(
    "restriction_mode,expected_restriction_state_flag",
    [
        pytest.param(RestrictionMode.ALARM, False),
        pytest.param(RestrictionMode.FORCED_TERMINATION, True),
    ],
)
async def test_set_restriction_mode(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    restriction_mode: RestrictionMode,
    expected_restriction_state_flag: bool,
):
    """Test that the set_restriction_mode method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    expected_pcs = await load_fixture("device_parental_control_setting")
    expected_pcs["parentalControlSetting"]["playTimerRegulations"][
        "restrictionMode"
    ] = str(restriction_mode)

    mock_api.async_update_play_timer.return_value = {"json": expected_pcs}

    await device.set_restriction_mode(restriction_mode)
    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        device.parental_control_settings["playTimerRegulations"],
    )
    assert f">> Device.set_restriction_mode(mode={restriction_mode})" in caplog.text
    assert device.forced_termination_mode == expected_restriction_state_flag


@pytest.mark.parametrize(
    "new_mode",
    [
        pytest.param(DeviceTimerMode.DAILY),
        pytest.param(DeviceTimerMode.EACH_DAY_OF_THE_WEEK),
    ],
)
async def test_set_timer_mode(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    new_mode: DeviceTimerMode,
):
    """Test that the set_timer_mode method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    expected_pcs = {"json": await load_fixture("device_parental_control_setting")}
    expected_pcs["json"]["parentalControlSetting"]["playTimerRegulations"][
        "timerMode"
    ] = str(new_mode)
    mock_api.async_update_play_timer.return_value = expected_pcs
    await device.set_timer_mode(new_mode)
    mock_api.async_update_play_timer.assert_called_with(
        device.device_id,
        device.parental_control_settings["playTimerRegulations"],
    )

    assert device.timer_mode == new_mode
    assert f">> Device.set_timer_mode(mode={new_mode})" in caplog.text


@pytest.mark.parametrize(
    "minutes,expected_exception",
    [
        pytest.param(-2, DailyPlaytimeOutOfRangeError),
        pytest.param(-1, None),
        pytest.param(0, None),
        pytest.param(1, None),
        pytest.param(1.5, None),
        pytest.param(360, None),
        pytest.param(361, DailyPlaytimeOutOfRangeError),
    ],
)
async def test_update_max_daily_playtime(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    minutes: int,
    expected_exception: Exception | None,
):
    """Test that the update_max_daily_playtime method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    pcs_response = await load_fixture("device_parental_control_setting")
    ttpiod = pcs_response["parentalControlSetting"]["playTimerRegulations"][
        "dailyRegulations"
    ]["timeToPlayInOneDay"]
    if minutes == -1:
        ttpiod["enabled"] = False
        ttpiod.pop("limitTime")
    else:
        ttpiod["enabled"] = True
        ttpiod["limitTime"] = int(minutes)

    mock_api.async_update_play_timer.return_value = {"json": pcs_response}

    if expected_exception is None:
        await device.update_max_daily_playtime(minutes)
        mock_api.async_update_play_timer.assert_called_with(
            device.device_id,
            pcs_response["parentalControlSetting"]["playTimerRegulations"],
        )

    else:
        with pytest.raises(expected_exception):
            await device.update_max_daily_playtime(minutes)

    assert f">> Device.update_max_daily_playtime(minutes={minutes})" in caplog.text


async def test_parse_with_extra_playing_time(mock_api: Api):
    """Test that the `extra_playing_time` property is correctly set in the PCS parser."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    # Default to None if not set.
    assert device.extra_playing_time is None

    # Now override with extra time.
    pcs_response = await load_fixture("device_parental_control_setting")
    pcs_response["ownedDevice"]["device"]["extraPlayingTime"] = {
        "inOneDay": {"duration": 50}
    }

    # Set the pcs response and call the update method
    mock_api.async_get_device_parental_control_setting.return_value = {
        "json": pcs_response
    }
    await device.update()

    assert device.extra_playing_time == 50


async def test_calculate_times(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
):
    """Test that the `_calculate_times` method works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    dt = datetime(2023, 10, 30, 12, 0, 0)

    daily_summaries = copy.deepcopy(device.daily_summaries)

    caplog.clear()

    # Test with invalid data
    device.daily_summaries = "not a list"
    with caplog.at_level(logging.DEBUG):
        device._calculate_times(dt)
    matching_logs = [
        r for r in caplog.records if r.message == ">> Device._calculate_times()"
    ]
    assert len(matching_logs) == 0

    # Test with empty data
    device.daily_summaries = []
    with caplog.at_level(logging.DEBUG):
        device._calculate_times(dt)
    matching_logs = [
        r for r in caplog.records if r.message == ">> Device._calculate_times()"
    ]
    assert len(matching_logs) == 0

    # Test with null data
    device.daily_summaries = None
    with caplog.at_level(logging.DEBUG):
        device._calculate_times(dt)
    matching_logs = [
        r for r in caplog.records if r.message == ">> Device._calculate_times()"
    ]
    assert len(matching_logs) == 0

    # Test with no current day summary
    device.daily_summaries = daily_summaries
    with caplog.at_level(logging.DEBUG):
        device._calculate_times(dt)
    matching_logs = [
        r for r in caplog.records if r.message == ">> Device._calculate_times()"
    ]
    assert len(matching_logs) == 1
    assert "No daily summary for today, assuming 0 playing time." in caplog.text
    assert device.today_playing_time == 0
    assert device.today_disabled_time == 0
    assert device.today_exceeded_time == 0

    caplog.clear()

    # Test with a daily summary
    dt = datetime(2025, 12, 8, 12, 0, 0)
    device.daily_summaries = daily_summaries
    with caplog.at_level(logging.DEBUG):
        device._calculate_times(dt)
    matching_logs = [
        r for r in caplog.records if r.message == ">> Device._calculate_times()"
    ]
    assert len(matching_logs) == 1
    assert device.today_playing_time == 60
    assert device.today_disabled_time == 15
    assert device.today_exceeded_time == 20

    matching_logs = [
        r
        for r in caplog.records
        if r.message
        == f"Cached playing, disabled and exceeded time for today for device {device.device_id}"
    ]
    assert len(matching_logs) == 1

    assert device.month_playing_time == 75
