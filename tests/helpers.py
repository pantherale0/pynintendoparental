"""Test helpers."""

import aiofiles
import json
from pathlib import Path

from pynintendoparental.device import Device


async def load_fixture(filename: str) -> dict:
    """Load a fixture from the fixtures directory."""
    path = Path(__file__).parent / "fixtures" / f"{filename}.json"
    async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
        contents = await f.read()
    return json.loads(contents)

def clean_device_for_snapshot(device: Device) -> dict:
    """
    Cleans the device object to a dict for snapshot testing,
    removing non-serializable or irrelevant attributes.
    """
    cleaned = {}
    for key, value in device.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            cleaned[key] = [
                clean_device_for_snapshot(v) if hasattr(v, "__dict__") else v
                for v in value
            ]
        elif hasattr(value, "__dict__"):
            cleaned[key] = clean_device_for_snapshot(value)
        else:
            cleaned[key] = value
    return cleaned
