"""Tests for the pynintendoparental package."""

from unittest.mock import AsyncMock, patch

import pytest
from pynintendoauth.exceptions import HttpException

from pynintendoparental import NintendoParental, NoDevicesFoundException
from pynintendoparental.authenticator import Authenticator

from .helpers import load_fixture


@pytest.fixture(name="mock_api_init")
def fixture_mock_api_init():
    """Fixture to mock the Api class."""
    with patch("pynintendoparental.Api", autospec=True) as mock_api:
        yield mock_api


async def test_create_method(mock_authenticator: Authenticator, mock_api_init: AsyncMock):
    """Test the create class method."""
    devices_fixture = await load_fixture("account_devices")
    device_id = devices_fixture["ownedDevices"][0]["deviceId"]
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.return_value = {"json": devices_fixture}

    parental = await NintendoParental.create(mock_authenticator)

    assert isinstance(parental, NintendoParental)
    assert parental.account_id == mock_authenticator.account_id
    assert len(parental.devices) == 1
    assert device_id in parental.devices
    mock_api_init.assert_called_once()
    mock_api_instance.async_get_account_devices.assert_called_once()


async def test_no_devices_found(mock_authenticator: Authenticator, mock_api_init: AsyncMock):
    """Test the create class method when no devices are found."""
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.side_effect = HttpException(404, "Not Found")

    with pytest.raises(NoDevicesFoundException):
        await NintendoParental.create(mock_authenticator)


async def test_device_fetch_http_exception(mock_authenticator: Authenticator, mock_api_init: AsyncMock):
    """Test an HttpException when fetching devices."""
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.side_effect = HttpException(500, "Internal Server Error")

    with pytest.raises(HttpException):
        await NintendoParental.create(mock_authenticator)


async def test_discover_devices(mock_authenticator: Authenticator, mock_api_init: AsyncMock):
    """Test discover_devices fetches the device list without updating the devices."""
    devices_fixture = await load_fixture("account_devices")
    device_id = devices_fixture["ownedDevices"][0]["deviceId"]
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.return_value = {"json": devices_fixture}
    parental = NintendoParental(mock_authenticator, "Europe/London", "en-GB")

    with patch("pynintendoparental.Device.update", autospec=True) as mock_update:
        devices = await parental.discover_devices()
        assert devices is parental.devices
        assert list(devices) == [device_id]
        device = devices[device_id]

        assert (await parental.discover_devices())[device_id] is device

    mock_update.assert_not_called()
    assert mock_api_instance.async_get_account_devices.call_count == 2


async def test_discover_devices_errors(mock_authenticator: Authenticator, mock_api_init: AsyncMock):
    """Test discover_devices raises when the device list can't be fetched."""
    mock_api_instance = mock_api_init.return_value
    parental = NintendoParental(mock_authenticator, "Europe/London", "en-GB")

    mock_api_instance.async_get_account_devices.side_effect = HttpException(404, "Not Found")
    with pytest.raises(NoDevicesFoundException):
        await parental.discover_devices()

    mock_api_instance.async_get_account_devices.side_effect = HttpException(500, "Internal Server Error")
    with pytest.raises(HttpException):
        await parental.discover_devices()
    assert parental.devices == {}


async def test_device_update_exception(mock_authenticator: Authenticator, mock_api_init: AsyncMock):
    """Test an exception during device update doesn't stop creation."""
    devices_fixture = await load_fixture("account_devices")
    device_id = devices_fixture["ownedDevices"][0]["deviceId"]
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.return_value = {"json": devices_fixture}
    with patch(
        "pynintendoparental.device.Device.update",
        new=AsyncMock(side_effect=Exception("Update Failed")),
    ):
        parental = await NintendoParental.create(mock_authenticator)
        assert len(parental.devices) == 1
        assert device_id in parental.devices


async def test_update_monthly_summary(mock_authenticator: Authenticator, mock_api_init: AsyncMock):
    """Test that update(monthly_summary=False) is passed on, except for devices without a summary."""
    devices_fixture = await load_fixture("account_devices")
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.return_value = {"json": devices_fixture}

    with patch("pynintendoparental.Device.update", autospec=True) as mock_update:
        parental = await NintendoParental.create(mock_authenticator)
        device = next(iter(parental.devices.values()))
        assert mock_update.call_args.kwargs == {"monthly_summary": True}

        device.last_month_summary = {"players": []}
        await parental.update(monthly_summary=False)
        assert mock_update.call_args.kwargs == {"monthly_summary": False}

        device.last_month_summary = {}
        await parental.update(monthly_summary=False)
        assert mock_update.call_args.kwargs == {"monthly_summary": True}
