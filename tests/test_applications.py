"""Unit tests for the Application class."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from pynintendoparental.api import Api
from pynintendoparental.application import Application
from pynintendoparental.device import Device

from .helpers import load_fixture


async def test_application_callback(mock_api: Api):
    """Test that application callbacks are called on update."""
    devices_response = await load_fixture("account_devices")
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.applications) > 0
    app = list(device.applications.values())[0]

    sync_callback = Mock()
    async_callback = AsyncMock()

    app.add_application_callback(sync_callback)
    app.add_application_callback(async_callback)

    await device.update()

    sync_callback.assert_called_once_with(app)
    async_callback.assert_called_once_with(app)

    # Test removing a callback
    sync_callback.reset_mock()
    async_callback.reset_mock()
    app.remove_application_callback(sync_callback)
    await device.update()
    sync_callback.assert_not_called()
    async_callback.assert_called_once_with(app)

    # Test removing invalid callback
    with pytest.raises(ValueError, match="Callback not found."):
        app.remove_application_callback(sync_callback)

    # Test adding non-callable
    with pytest.raises(ValueError, match="Object must be callable."):
        app.add_application_callback("not a function")


async def test_application_callback_no_device():
    """Test that the application simply returns if no device is passed to the internal callback handler."""
    app = Application(
        app_id="test_app_id",
        name="Test App",
        device_id="test_device_id",
        api=AsyncMock(),
    )

    cb_handler = getattr(app, "_internal_update_callback")
    response = await cb_handler(None)
    assert response is None


async def test_application_update_scenarios(
    caplog: pytest.LogCaptureFixture,
):
    """Test application update callback with various data scenarios for coverage."""
    app = Application(
        app_id="01009B90006DC000",
        name="Super Mario Bros. Wonder",
        device_id="DEV123",
        api=AsyncMock(),
    )
    cb_handler = getattr(app, "_internal_update_callback")

    # Scenario 1: Empty daily summary
    mock_device = MagicMock(spec=Device)
    mock_device.device_id = "DEV123"
    mock_device.parental_control_settings = {"whitelistedApplicationList": []}
    mock_device.last_month_summary = {}
    mock_device.daily_summaries = []  # This is the key part for this test

    await cb_handler(mock_device)
    assert app.today_time_played == 0

    # Scenario 2: Empty whitelistedApplicationList
    mock_device.daily_summaries = [{"players": []}]
    mock_device.parental_control_settings = {
        "whitelistedApplicationList": []
    }
    app.image_url = "initial"  # set a value to check it's not overwritten

    await cb_handler(mock_device)
    assert app.image_url == "initial"

    # Scenario 3: Missing whitelistedApplicationList key
    mock_device.parental_control_settings = {}
    app.image_url = "initial_2"

    await cb_handler(mock_device)
    assert app.image_url == "initial_2"
    assert ">> Device DEV123 is missing a application whitelist, unable to update safe launch settings for 01009B90006DC000" in caplog.text
