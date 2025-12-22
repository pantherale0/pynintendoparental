"""Tests for the API class."""

from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock

import pytest
from aiohttp import ContentTypeError
from pynintendoauth.exceptions import HttpException

from pynintendoparental.api import Api, _check_http_success
from pynintendoparental.authenticator import Authenticator


@pytest.mark.parametrize(
    "status, expected", [(200, True), (204, True), (300, False), (404, False)]
)
def test_check_http_success(status, expected):
    """Test the _check_http_success function."""
    assert _check_http_success(status) == expected


def test_api_init_and_properties(mock_authenticator: Authenticator):
    """Test API initialization and properties."""
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")
    assert api.account_id == "ACCOUNT_ID"
    headers = api._headers
    assert headers["Authorization"] == "ACCESS_TOKEN"
    assert headers["X-Moon-TimeZone"] == "Europe/London"
    assert headers["X-Moon-App-Language"] == "en-GB"


async def test_send_request_invalid_endpoint(mock_authenticator: Authenticator):
    """Test sending a request to an invalid endpoint."""
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")
    with pytest.raises(ValueError, match="Endpoint does not exist"):
        await api.send_request("invalid_endpoint")


async def test_send_request_token_refresh(mock_authenticator: Authenticator):
    """Test that the token is refreshed if it's expired."""
    type(mock_authenticator).access_token_expired = PropertyMock(return_value=True)
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"status": "ok"})
    mock_response.text = AsyncMock(return_value='{"status": "ok"}')

    # Use side_effect to replicate the internal logic of the real method.
    async def mock_auth_request(*args, **kwargs):
        if mock_authenticator.access_token_expired:
            await mock_authenticator._perform_refresh()
        return mock_response

    mock_authenticator.async_authenticated_request.side_effect = mock_auth_request

    await api.send_request("get_account_devices")
    mock_authenticator._perform_refresh.assert_called_once()


async def test_send_request_http_exception(mock_authenticator: Authenticator):
    """Test a generic HttpException is raised on non-2xx response."""
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")

    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.content_type = "text/plain"
    mock_response.text = AsyncMock(return_value="Internal Server Error")
    mock_authenticator.async_authenticated_request = AsyncMock(
        return_value=mock_response
    )

    with pytest.raises(HttpException, match="Internal Server Error"):
        await api.send_request("get_account_devices")


async def test_send_request_http_exception_problem_json(
    mock_authenticator: Authenticator,
):
    """Test that HttpException is raised with details from a problem+json response."""
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")

    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.content_type = "application/problem+json"
    mock_response.json = AsyncMock(
        return_value={"detail": "Bad Request", "errorCode": "E0001"}
    )
    mock_authenticator.async_authenticated_request = AsyncMock(
        return_value=mock_response
    )

    with pytest.raises(HttpException, match="Bad Request"):
        await api.send_request("get_account_devices")


async def test_send_request_http_exception_problem_json_invalid(
    mock_authenticator: Authenticator,
):
    """Test HttpException with a generic message for invalid problem+json."""
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")
    mock_request_info = Mock(real_url="http://mock.url")
    content_type_error = ContentTypeError(mock_request_info, ())

    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.content_type = "application/problem+json"
    mock_response.json = AsyncMock(side_effect=content_type_error)
    mock_response.text = AsyncMock(return_value="Invalid JSON")
    mock_authenticator.async_authenticated_request = AsyncMock(
        return_value=mock_response
    )

    with pytest.raises(HttpException, match="Invalid JSON"):
        await api.send_request("get_account_devices")


async def test_send_request_json_decode_error(mock_authenticator: Authenticator):
    """Test that an empty json dict is returned on a JSON decode error."""
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")
    mock_request_info = Mock(real_url="http://mock.url")
    content_type_error = ContentTypeError(mock_request_info, ())

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(side_effect=content_type_error)
    mock_response.text = AsyncMock(return_value="<not_json>")
    mock_response.url = "http://mock.url"
    mock_authenticator.async_authenticated_request = AsyncMock(
        return_value=mock_response
    )

    result = await api.send_request("get_account_devices")
    assert result["json"] == {}


async def test_api_methods(mock_authenticator: Authenticator):
    """Test that API methods call send_request with correct parameters."""
    api = Api(auth=mock_authenticator, tz="Europe/London", lang="en-GB")
    api.send_request = AsyncMock()

    await api.async_get_account_devices()
    api.send_request.assert_called_with(endpoint="get_account_devices")

    await api.async_get_account_device("DEVICE_ID")
    api.send_request.assert_called_with(
        endpoint="get_account_device", DEVICE_ID="DEVICE_ID"
    )

    await api.async_get_device_daily_summaries("DEVICE_ID")
    api.send_request.assert_called_with(
        endpoint="get_device_daily_summaries", DEVICE_ID="DEVICE_ID"
    )

    await api.async_get_device_monthly_summaries("DEVICE_ID")
    api.send_request.assert_called_with(
        endpoint="get_device_monthly_summaries", DEVICE_ID="DEVICE_ID"
    )

    await api.async_get_device_parental_control_setting("DEVICE_ID")
    api.send_request.assert_called_with(
        endpoint="get_device_parental_control_setting", DEVICE_ID="DEVICE_ID"
    )

    await api.async_get_device_monthly_summary("DEVICE_ID", 2023, 11)
    api.send_request.assert_called_with(
        endpoint="get_device_monthly_summary",
        DEVICE_ID="DEVICE_ID",
        YEAR=2023,
        MONTH="11",
    )

    await api.async_update_restriction_level("DEVICE_ID", {"some": "setting"})
    api.send_request.assert_called_with(
        endpoint="update_restriction_level",
        body={
            "deviceId": "DEVICE_ID",
            "customSettings": {},
            "vrRestrictionEtag": None,
            "whitelistedApplicationList": None,
            "functionalRestrictionLevel": None,
            "parentalControlSettingEtag": None
        },
    )

    await api.async_update_extra_playing_time("DEVICE_ID", -1)
    api.send_request.assert_called_with(
        endpoint="update_extra_playing_time",
        body={"deviceId": "DEVICE_ID", "status": "TO_INFINITY"},
    )

    await api.async_update_extra_playing_time("DEVICE_ID", 60)
    api.send_request.assert_called_with(
        endpoint="update_extra_playing_time",
        body={"deviceId": "DEVICE_ID", "additionalTime": 60, "status": "TO_ADDED"},
    )

    await api.async_update_play_timer("DEVICE_ID", {"some": "setting"})
    api.send_request.assert_called_with(
        endpoint="update_play_timer",
        body={
            "deviceId": "DEVICE_ID",
            "playTimerRegulations": {"some": "setting"},
        },
    )

    await api.async_update_unlock_code("1234", "DEVICE_ID")
    api.send_request.assert_called_with(
        endpoint="update_unlock_code",
        body={"deviceId": "DEVICE_ID", "unlockCode": "1234"},
    )
