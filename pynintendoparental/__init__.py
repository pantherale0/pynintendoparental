# pylint: disable=broad-exception-caught
"""The core Python module."""

import asyncio

from .authenticator import Authenticator
from .api import Api
from .const import _LOGGER
from .device import Device

class NintendoParental:
    """Core Python API."""

    def __init__(self,
                 auth: Authenticator,
                 timezone,
                 lang) -> None:
        self._api: Api = Api(auth=auth, tz=timezone, lang=lang)
        self.account_id = auth.account_id
        self.devices: list[Device] = []
        self._discovered_devices: list[str] = []

    async def _get_devices(self):
        """Gets devices from the API and stores in self.devices"""
        async def update_device(dev: Device):
            """Update a device."""
            await dev.update()

        response = await self._api.send_request(
            endpoint="get_account_devices",
            ACCOUNT_ID=self.account_id
        )

        try:
            for dev_raw in response["json"]["items"]:
                device: Device = Device.from_device_response(dev_raw, self._api)
                if device.device_id not in self._discovered_devices:
                    _LOGGER.debug("Creating new device %s", device.device_id)
                    self.devices.append(device)
                    self._discovered_devices.append(device.device_id)
            coros = [update_device(d) for d in self.devices]
            await asyncio.gather(*coros)
        except Exception as err:
            self.devices = []
            raise RuntimeError(err) from err
        _LOGGER.debug("Found %s device(s)", len(self.devices))

    async def update(self):
        """Update module data."""
        _LOGGER.debug("Received request to update data.")
        await self._get_devices()
        _LOGGER.debug("Update complete.")

    @classmethod
    async def create(cls,
                 auth: Authenticator,
                 timezone: str = "Europe/London",
                 lang: str = "en-GB") -> 'NintendoParental':
        """Create an instance of NintendoParental."""
        self = cls(auth, timezone, lang)
        await self.update()
        return self
