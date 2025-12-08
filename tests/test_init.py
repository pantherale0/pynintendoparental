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


async def test_create_method(
    mock_authenticator: Authenticator, mock_api_init: AsyncMock
):
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


async def test_no_devices_found(
    mock_authenticator: Authenticator, mock_api_init: AsyncMock
):
    """Test the create class method when no devices are found."""
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.side_effect = HttpException(
        404, "Not Found"
    )

    with pytest.raises(NoDevicesFoundException):
        await NintendoParental.create(mock_authenticator)


async def test_device_fetch_http_exception(
    mock_authenticator: Authenticator, mock_api_init: AsyncMock
):
    """Test an HttpException when fetching devices."""
    mock_api_instance = mock_api_init.return_value
    mock_api_instance.async_get_account_devices.side_effect = HttpException(
        500, "Internal Server Error"
    )

    with pytest.raises(HttpException):
        await NintendoParental.create(mock_authenticator)


async def test_device_update_exception(
    mock_authenticator: Authenticator, mock_api_init: AsyncMock
):
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
