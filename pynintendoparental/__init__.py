"""The core Python module."""

from .authenticator import Authenticator
from .api import Api
from .device import Device

class NintendoParental(Api):
    """Core Python API."""

    def __init__(self, auth: Authenticator) -> None:
        super().__init__(
            auth=auth
        )
        self.devices: list[Device] = None

    async def _get_devices(self):
        """Gets devices from the API and stores in self.devices"""
        response = await self.send_request(
            endpoint="get_account_devices",
            ACCOUNT_ID=self._auth.account_id
        )
        self.devices = Device.from_devices_response(response["json"])

    async def update(self):
        """Update module data."""
        await self._get_devices()
