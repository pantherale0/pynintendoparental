"""Test helpers."""

from __future__ import annotations

import copy
import json
from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles

from pynintendoparental.application import ApplicationRegistry
from pynintendoparental.device import Device
from pynintendoparental.player import PlayerRegistry

if TYPE_CHECKING:
    from pynintendoparental.api import Api


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
        if isinstance(value, ApplicationRegistry):
            cleaned[key] = {app.application_id: app for app in value}
        elif isinstance(value, PlayerRegistry):
            cleaned[key] = {player.player_id: player for player in value}
        elif isinstance(value, list):
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


def unique_played_games(daily_summaries: list[dict]) -> list[dict]:
    """Return unique whitelist-shaped entries from daily-summary playedGames meta."""
    seen: dict[str, dict] = {}
    for summary in daily_summaries:
        for player in summary.get("players", []):
            for game in player.get("playedGames") or []:
                meta = game.get("meta") or {}
                app_id = meta.get("applicationId")
                if not app_id or app_id in seen:
                    continue
                image = meta.get("imageUri")
                if isinstance(image, dict):
                    image = image.get("small")
                seen[app_id] = {
                    "applicationId": app_id,
                    "title": meta.get("title"),
                    "imageUri": image,
                    "safeLaunch": "NONE",
                }
    return list(seen.values())


def pcs_with_dump_whitelist(pcs: dict, daily_summaries: list[dict]) -> dict:
    """Return a deep-copied PCS whose whitelist is the dump's played games."""
    result = copy.deepcopy(pcs)
    result["parentalControlSetting"]["whitelistedApplicationList"] = unique_played_games(daily_summaries)
    return result


def daily_summary_on(entry: dict, date: str) -> dict:
    """Return the daily summary for a dump entry date."""
    for summary in entry["daily_summaries"]:
        if summary["date"] == date:
            return summary
    raise KeyError(f"No daily summary for {date}")


def _dump_device_id(entry: dict) -> str:
    """Synthetic device id for a dump entry that has none."""
    return f"dump-{entry['name'].replace(' ', '-').lower()}"


def configure_mock_api_for_dump(
    mock_api: Api,
    entry: dict,
    pcs: dict,
    account_device: dict,
) -> None:
    """Wire API mocks so Device.update() consumes a multiple-devices dump entry."""
    extra = copy.deepcopy(account_device)
    extra["ownedDevice"]["device"]["platformGeneration"] = entry["generation"]
    first_month_date = entry["last_month_summary"]["overall"]["dailyStats"][0]["date"]
    year, month, _day = first_month_date.split("-")

    mock_api.async_get_device_daily_summaries.return_value = {"json": {"dailySummaries": entry["daily_summaries"]}}
    mock_api.async_get_device_monthly_summaries.return_value = {
        "json": {"available": [{"year": int(year), "month": int(month)}]}
    }
    mock_api.async_get_device_monthly_summary.return_value = {"json": {"summary": entry["last_month_summary"]}}
    mock_api.async_get_device_parental_control_setting.return_value = {"json": pcs}
    mock_api.async_get_account_device.return_value = {"json": extra}


async def device_from_dump(
    entry: dict,
    mock_api: Api,
    pcs: dict,
    account_device: dict | None = None,
) -> Device:
    """Build a Device from a multiple-devices dump entry and run update()."""
    if account_device is None:
        account_device = await load_fixture("account_device")
    dump_pcs = pcs_with_dump_whitelist(pcs, entry["daily_summaries"])
    configure_mock_api_for_dump(mock_api, entry, dump_pcs, account_device)
    raw = {
        "deviceId": _dump_device_id(entry),
        "label": entry["name"],
        "parentalControlSettingState": {"updatedAt": 0},
        "platformGeneration": entry["generation"],
        "alarmSetting": {"visibility": "VISIBLE"},
    }
    device = Device.from_device_response(raw, mock_api)
    first_date = datetime.strptime(entry["daily_summaries"][0]["date"], "%Y-%m-%d").replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    await device.update(now=first_date)
    return device
