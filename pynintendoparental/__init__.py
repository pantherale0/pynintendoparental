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
        self.devices: dict[str, Device] = {}

    async def _get_devices(self):
        """Gets devices from the API and stores in self.devices"""
        async def update_device(dev: Device):
            """Update a device."""
            try:
                await dev.update()
            except Exception as err:
                _LOGGER.exception("Error updating device %s: %s",
                              dev.device_id,
                              err)

        response = await self._api.async_get_account_devices()

        for dev_raw in response["json"]["ownedDevices"]:
            device: Device = Device.from_device_response(dev_raw, self._api)
            if self.devices.get(device.device_id, None) is None:
                _LOGGER.debug("Creating new device %s", device.device_id)
                self.devices[device.device_id] = device
        coros = [update_device(d) for d in self.devices.values()]
        await asyncio.gather(*coros)
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
