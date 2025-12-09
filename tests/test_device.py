"""Tests for the Device class."""

import copy
import pytest

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from pynintendoauth.exceptions import HttpException
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

    test_device = copy.deepcopy(device)
    assert test_device.last_sync is not None
    assert test_device.last_sync == device.extra["synchronizedParentalControlSetting"][
        "synchronizedAt"
    ]
    del test_device.extra["synchronizedParentalControlSetting"]["synchronizedAt"]
    assert test_device.last_sync is None
    del test_device.extra["synchronizedParentalControlSetting"]
    assert test_device.last_sync is None

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

@pytest.mark.parametrize(
    "mock_api_function,side_effect,expected_log",
    [
        pytest.param(
            "async_get_device_monthly_summary",
            HttpException(404, "test", "test"),
            "HTTP Exception raised while getting monthly summary for device {DEVICE_ID}: HTTP 404: test (test)"
        ),
        pytest.param(
            "async_get_device_monthly_summaries",
            HttpException(404, "test", "test"),
            "Could not retrieve monthly summaries: HTTP 404: test (test)"
        )
    ]
)
async def test_get_monthly_summary_error(
    mock_api: Api,
    caplog: pytest.LogCaptureFixture,
    mock_api_function: str,
    side_effect: Exception,
    expected_log: str
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
