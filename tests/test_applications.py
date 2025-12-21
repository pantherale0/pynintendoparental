"""Unit tests for the Application class."""

from unittest.mock import AsyncMock, Mock

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
