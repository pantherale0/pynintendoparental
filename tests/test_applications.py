"""Unit tests for the Application class."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from pynintendoparental.api import Api
from pynintendoparental.application import Application
from pynintendoparental.device import Device
from pynintendoparental.enum import SafeLaunchSetting

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
        send_api_update=None,
        callbacks=[]
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
        send_api_update=None,
        callbacks=[]
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
    mock_device.parental_control_settings = {"whitelistedApplicationList": []}
    app.image_url = "initial"  # set a value to check it's not overwritten

    await cb_handler(mock_device)
    assert app.image_url == "initial"

    # Scenario 3: Missing whitelistedApplicationList key
    mock_device.parental_control_settings = {}
    app.image_url = "initial_2"

    await cb_handler(mock_device)
    assert app.image_url == "initial_2"
    assert (
        ">> Device DEV123 is missing a application whitelist, unable to update safe launch settings for 01009B90006DC000"
        in caplog.text
    )


@pytest.mark.parametrize(
    "setting",
    [pytest.param(SafeLaunchSetting.ALLOW), pytest.param(SafeLaunchSetting.NONE)],
)
async def test_application_set_safe_launch_setting(
    mock_api: Api, setting: SafeLaunchSetting
):
    """Ensure that the safe launch setting correctly updates."""
    devices_response = await load_fixture("account_devices")
    pcs_response = {"json": await load_fixture("device_parental_control_setting")}
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.applications) > 0

    # Select the first application
    application = list(device.applications.values())[0]
    # Update pcs_response
    pcs_response["json"]["parentalControlSetting"]["whitelistedApplicationList"][0][
        "safeLaunch"
    ] = str(setting)
    mock_api.async_update_restriction_level.return_value = pcs_response
    await application.set_safe_launch_setting(setting)

    mock_api.async_update_restriction_level.assert_called_with(
        device.device_id, pcs_response["json"]["parentalControlSetting"]
    )
    assert application.safe_launch_setting is setting


@pytest.mark.parametrize(
    "setting,exception",
    [
        pytest.param(SafeLaunchSetting.NONE, ValueError),
        pytest.param(SafeLaunchSetting.ALLOW, ValueError),
    ],
)
async def test_application_set_safe_launch_setting_init_errors(
    setting: SafeLaunchSetting, exception: Exception
):
    """Test the application set_safe_launch_setting correctly errors for init."""

    # Test with no device
    application_1 = Application(
        app_id="TESTAPPID",
        name="TESTAPPNAME",
        device_id="TESTDEVICEID",
        api=AsyncMock(),
        send_api_update=None,
        callbacks=[]
    )
    with pytest.raises(exception):
        await application_1.set_safe_launch_setting(setting)

    # Test with no application list
    application_2 = Application(
        app_id="TESTAPPID",
        name="TESTAPPNAME",
        device_id="TESTDEVICEID",
        api=AsyncMock(),
        send_api_update=None,
        callbacks=[]
    )
    setattr(application_2, "_device", True)
    with pytest.raises(exception):
        await application_2.set_safe_launch_setting(setting)


@pytest.mark.parametrize(
    "setting,exception",
    [
        pytest.param(SafeLaunchSetting.NONE, LookupError),
        pytest.param(SafeLaunchSetting.ALLOW, LookupError),
    ],
)
async def test_application_set_safe_launch_setting_whitelist_errors(
    mock_api: Api, setting: SafeLaunchSetting, exception: Exception
):
    """Test the application set_safe_launch_setting correctly errors for whitelist problems."""
    devices_response = await load_fixture("account_devices")
    pcs_response = {"json": await load_fixture("device_parental_control_setting")}
    devices = await Device.from_devices_response(devices_response, mock_api)
    assert len(devices) > 0
    device = devices[0]
    assert len(device.applications) > 0

    # Select the first application
    application = list(device.applications.values())[0]
    # Update pcs_response
    pcs_response["json"]["parentalControlSetting"]["whitelistedApplicationList"][0][
        "safeLaunch"
    ] = str(setting)
    # Override application pcs
    application._parental_control_settings["whitelistedApplicationList"] = (
        application._parental_control_settings["whitelistedApplicationList"][1:-1]
    )
    with pytest.raises(exception):
        await application.set_safe_launch_setting(setting)

    mock_api.async_update_restriction_level.assert_not_called()
