"""The core Python module."""

from .authenticator import Authenticator
from .api import Api
from .const import _LOGGER
from .device import Device

class NintendoParental:
    """Core Python API."""

    def __init__(self,
                 auth: Authenticator,
                 timezone: str = "Europe/London",
                 lang: str = "en-GB") -> None:
        self._api: Api = Api(auth=auth, tz=timezone, lang=lang)
        self.account_id = auth.account_id
        self.devices: list[Device] = None

    async def _get_devices(self):
        """Gets devices from the API and stores in self.devices"""
        response = await self._api.send_request(
            endpoint="get_account_devices",
            ACCOUNT_ID=self.account_id
        )
        self.devices = await Device.from_devices_response(response["json"], self._api)
        _LOGGER.debug("Found %s device(s)", len(self.devices))

    async def update(self):
        """Update module data."""
        _LOGGER.debug("Received request to update data.")
        await self._get_devices()
        _LOGGER.debug("Update complete.")
