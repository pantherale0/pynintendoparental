"""Test helpers."""

from __future__ import annotations

import copy
import json
from datetime import time
from pathlib import Path

import aiofiles

from pynintendoparental.device import Device


async def load_fixture(filename: str) -> dict:
    """Load a fixture from the fixtures directory."""
    path = Path(__file__).parent / "fixtures" / f"{filename}.json"
    async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
        contents = await f.read()
    return json.loads(contents)


def clean_device_for_snapshot(device: Device) -> dict:
    """Clean a device object to a dict for snapshot testing."""
    cleaned = {}
    for key, value in device.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            cleaned[key] = [clean_device_for_snapshot(v) if hasattr(v, "__dict__") else v for v in value]
        elif hasattr(value, "__dict__"):
            cleaned[key] = clean_device_for_snapshot(value)
        else:
            cleaned[key] = value
    return cleaned


def _daily_regulations(pcs: dict) -> dict:
    """Return the daily regulations dict from a PCS payload."""
    return pcs["parentalControlSetting"]["playTimerRegulations"]["dailyRegulations"]


def pcs_with_bedtime(
    pcs: dict,
    *,
    enabled: bool,
    start: time | None = None,
    end: time | None = None,
) -> dict:
    """Return a deep-copied PCS with daily bedtime settings applied."""
    result = copy.deepcopy(pcs)
    bedtime: dict = {"enabled": enabled}
    if start is not None:
        bedtime["startingTime"] = {"hour": start.hour, "minute": start.minute}
    else:
        bedtime["startingTime"] = {"hour": 6, "minute": 0}
    if enabled and end is not None:
        bedtime["endingTime"] = {"hour": end.hour, "minute": end.minute}
    else:
        bedtime["endingTime"] = None
    _daily_regulations(result)["bedtime"] = bedtime
    return result


def pcs_with_extra_in_one_day(
    pcs: dict,
    duration: int | None = None,
    *,
    is_infinity: bool = False,
) -> dict:
    """Return a deep-copied PCS with inOneDay extra playing time."""
    result = copy.deepcopy(pcs)
    in_one_day: dict = {"isInfinity": is_infinity}
    if is_infinity:
        in_one_day["duration"] = None
    elif duration is not None:
        in_one_day["duration"] = duration
    result.setdefault("ownedDevice", {}).setdefault("device", {})["extraPlayingTime"] = {
        "inOneDay": in_one_day,
        "bedtime": None,
        "expiresAt": 1770335999,
    }
    return result


def pcs_with_extra_bedtime(pcs: dict, end_time: time) -> dict:
    """Return a deep-copied PCS with bedtime-extension extra playing time."""
    result = copy.deepcopy(pcs)
    result.setdefault("ownedDevice", {}).setdefault("device", {})["extraPlayingTime"] = {
        "bedtime": {"endTime": {"hour": end_time.hour, "minute": end_time.minute}},
        "inOneDay": None,
        "expiresAt": 1770335999,
    }
    return result


def pcs_with_play_limit(pcs: dict, limit_time: int) -> dict:
    """Return a deep-copied PCS with a daily playtime limit."""
    result = copy.deepcopy(pcs)
    _daily_regulations(result)["timeToPlayInOneDay"] = {
        "enabled": True,
        "limitTime": limit_time,
    }
    return result


def daily_summaries_for(summaries: dict, date: str, playing_time: int) -> dict:
    """Return a deep-copied daily summaries payload with today's date/playtime set."""
    result = copy.deepcopy(summaries)
    result["dailySummaries"][0]["date"] = date
    result["dailySummaries"][0]["playingTime"] = playing_time
    return result
