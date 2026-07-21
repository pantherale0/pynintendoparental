"""Callback registry and API update orchestration for Device."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from ..utils import is_awaitable


class DeviceCallbacksMixin:
    """Mixin providing device callback registration and API update plumbing."""

    def add_device_callback(self, callback: Callable):
        """Add a callback function to be called when device state changes.

        The callback will be invoked whenever the device data is updated.
        Callbacks can be either synchronous or asynchronous functions.

        Args:
            callback: A callable function. Can be sync or async.

        Raises:
            ValueError: If the provided object is not callable.
        """
        if not callable(callback):
            raise ValueError("Object must be callable.")
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_device_callback(self, callback: Callable):
        """Remove a previously registered device callback.

        Args:
            callback: The callback function to remove.

        Raises:
            ValueError: If the provided object is not callable or not found.
        """
        if not callable(callback):
            raise ValueError("Object must be callable.")
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def _execute_callbacks(self):
        """Execute all callbacks."""
        for cb in self._internal_callbacks:
            if is_awaitable(cb):
                await cb(device=self)
            else:
                cb(device=self)

        for cb in self._callbacks:
            if is_awaitable(cb):
                await cb()
            else:
                cb()

    async def _send_api_update(self, api_call: Callable, *args, **kwargs):
        """Sends an update to the API and refreshes local state."""
        now = kwargs.pop("now", datetime.now())
        response = await api_call(*args, **kwargs)
        self._parse_parental_control_setting(response["json"], now)
        self._calculate_times(now)
        await self._execute_callbacks()
