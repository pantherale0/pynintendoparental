"""Pytest fixtures."""

from datetime import datetime
from unittest.mock import AsyncMock, PropertyMock, create_autospec

import pytest

from pynintendoparental import NintendoParental
from pynintendoparental.api import Api
from pynintendoparental.authenticator import Authenticator
from pynintendoparental.device import Device

from .helpers import load_fixture

# Fixed datetime matching fixture dates (avoids flakiness in snapshots / summaries).
FIXED_NOW = datetime(2025, 12, 8, 12, 0, 0)


@pytest.fixture
def mock_authenticator() -> Authenticator:
    """Mock the Authenticator class."""
    mock = create_autospec(Authenticator)
    mock.access_token = "ACCESS_TOKEN"
    mock.account_id = "ACCOUNT_ID"
    mock._perform_refresh = AsyncMock()
    type(mock).access_token_expired = PropertyMock(return_value=False)
    return mock


@pytest.fixture
async def mock_api(mock_authenticator: Authenticator) -> Api:
    """Fixture for a mocked API."""
    api = create_autospec(Api)
    api._auth = mock_authenticator
    api._tz = "Europe/London"
    api._language = "en-GB"

    # Mock the return value for each API method by loading the corresponding fixture
    api.async_get_account_devices.return_value = {"json": await load_fixture("account_devices")}
    api.async_get_account_device.return_value = {"json": await load_fixture("account_device")}
    api.async_get_device_daily_summaries.return_value = {"json": await load_fixture("device_daily_summaries")}
    api.async_get_device_parental_control_setting.return_value = {
        "json": await load_fixture("device_parental_control_setting")
    }
    api.async_get_device_monthly_summaries.return_value = {"json": await load_fixture("device_monthly_summaries_list")}
    api.async_get_device_monthly_summary.return_value = {"json": await load_fixture("device_monthly_summary")}
    return api


@pytest.fixture
async def device(mock_api: Api) -> Device:
    """A Device loaded from fixtures with a fixed clock."""
    raw = await load_fixture("account_devices")
    return (await Device.from_devices_response(raw, mock_api, now=FIXED_NOW))[0]


@pytest.fixture
async def pcs() -> dict:
    """Parental control setting fixture payload."""
    return await load_fixture("device_parental_control_setting")


@pytest.fixture
def mock_client(mock_api: Api) -> NintendoParental:
    """Fixture for a mocked client."""
    client = create_autospec(NintendoParental)
    client._api = mock_api
    return client
