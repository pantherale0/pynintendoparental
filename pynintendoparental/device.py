"""Defines a single Nintendo Switch device."""

class Device:
    """A device"""

    def __init__(self):
        """INIT"""
        self.device_id: str = None
        self.name: str = None
        self.sync_state: str = None
        self.extra: dict = None

    @classmethod
    def from_devices_response(cls, raw: dict) -> list['Device']:
        """Parses a device request response body."""
        if "items" not in raw.keys():
            raise ValueError("Invalid response from API.")
        devices = []
        for device in raw.get("items", []):
            parsed = Device()
            parsed.device_id = device["deviceId"]
            parsed.name = device["label"]
            parsed.sync_state = device["parentalControlSettingState"]["updatedAt"]
            parsed.extra = device
            devices.append(parsed)

        return devices
