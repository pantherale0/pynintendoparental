"""Tests for the Device class."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from pynintendoparental.device import Device
from pynintendoparental.api import Api

from .helpers import load_fixture, clean_device_for_snapshot


async def test_device_parsing(mock_api: Api, snapshot: SnapshotAssertion):
    """Test that the device class parsing works as expected."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]

    assert clean_device_for_snapshot(device) == snapshot(
        exclude=props("today_time_remaining")
    )
