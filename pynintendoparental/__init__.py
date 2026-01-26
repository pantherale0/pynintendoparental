# pylint: disable=broad-exception-caught
"""The core Python module."""

import asyncio

from pynintendoauth.exceptions import HttpException

from .api import Api
from .const import _LOGGER
from .device import Device
from .exceptions import NoDevicesFoundException
from .authenticator import Authenticator


class NintendoParental:
    """Core Python API for Nintendo Switch Parental Controls.
    
    This is the main entry point for interacting with Nintendo Switch Parental Controls.
    Use the `create` class method to instantiate this class.
    
    Attributes:
        account_id: The Nintendo account ID.
        devices: Dictionary of Device objects keyed by device ID.
    """

    def __init__(self, auth: Authenticator, timezone, lang) -> None:
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
                _LOGGER.exception("Error updating device %s: %s", dev.device_id, err)

        try:
            response = await self._api.async_get_account_devices()
        except HttpException as err:
            if err.status_code == 404:
                _LOGGER.error("No devices found for account %s", self.account_id)
                raise NoDevicesFoundException("No devices found for account") from err
            _LOGGER.error("Error fetching devices: %s", err)
            raise
        for dev_raw in response["json"]["ownedDevices"]:
            device: Device = Device.from_device_response(dev_raw, self._api)
            if self.devices.get(device.device_id, None) is None:
                _LOGGER.debug("Creating new device %s", device.device_id)
                self.devices[device.device_id] = device
        coros = [update_device(d) for d in self.devices.values()]
        await asyncio.gather(*coros)
        _LOGGER.debug("Found %s device(s)", len(self.devices))

    async def update(self):
        """Update module data.
        
        Refreshes all devices and their associated data from Nintendo's servers.
        This method fetches the latest information about all devices linked to
        the authenticated account.
        """
        _LOGGER.debug("Received request to update data.")
        await self._get_devices()
        _LOGGER.debug("Update complete.")

    @classmethod
    async def create(
        cls, auth: Authenticator, timezone: str = "Europe/London", lang: str = "en-GB"
    ) -> "NintendoParental":
        """Create an instance of NintendoParental.
        
        This is the recommended way to create a NintendoParental instance as it
        handles the asynchronous initialization and fetches initial device data.
        
        Args:
            auth: An authenticated Authenticator instance.
            timezone: The timezone to use for API requests (default: "Europe/London").
                     Use any valid IANA timezone identifier.
            lang: The language code for API responses (default: "en-GB").
                  Use ISO 639-1 language codes with ISO 3166-1 country codes.
        
        Returns:
            A fully initialized NintendoParental instance with device data loaded.
            
        Example:
            ```python
            async with aiohttp.ClientSession() as session:
                auth = Authenticator(session_token, session)
                await auth.async_complete_login(use_session_token=True)
                nintendo = await NintendoParental.create(auth, timezone="America/New_York", lang="en-US")
            ```
        """
        self = cls(auth, timezone, lang)
        await self.update()
        return self
