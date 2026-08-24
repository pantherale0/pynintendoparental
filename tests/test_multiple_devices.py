"""Tests that parse the multi-device dump into Device / Player / Application dataclasses."""

import pytest

from pynintendoparental.api import Api
from pynintendoparental.application import Application, PlayedAppUsage
from pynintendoparental.device import Device
from pynintendoparental.player import Player

from .helpers import (
    daily_summary_on,
    device_from_dump,
    load_fixture,
    unique_played_games,
)

DUMP_KEYS = (
    "Device 1 (P01)",
    "Device 2 (P00)",
    "Device 3 (P00)",
    "Device 4 (P00)",
)

MINECRAFT_ID = "0100D71004694000"
FC26_ID = "01004FF021942000"


@pytest.fixture
async def dump() -> dict:
    """The anonymised four-device dump."""
    return await load_fixture("multiple_devices")


async def _load_device(dump: dict, dump_key: str, mock_api: Api, pcs: dict) -> tuple[dict, Device]:
    """Load one dump entry into a Device via mocked API responses."""
    entry = dump[dump_key]
    device = await device_from_dump(entry, mock_api, pcs)
    return entry, device


def _monthly_profiles(entry: dict) -> list[dict]:
    """Return monthly-summary player profiles that include a playerId."""
    profiles = []
    for player in entry["last_month_summary"].get("players", []):
        profile = player.get("profile") or {}
        if profile.get("playerId"):
            profiles.append(profile)
    return profiles


@pytest.mark.parametrize("dump_key", DUMP_KEYS)
async def test_dump_device_parsing(dump_key: str, dump: dict, mock_api: Api, pcs: dict):
    """Each dump device loads into Device, Player, and Application dataclasses."""
    entry, device = await _load_device(dump, dump_key, mock_api, pcs)
    today = entry["daily_summaries"][0]

    assert isinstance(device, Device)
    assert device.name == entry["name"]
    assert device.generation == entry["generation"]
    assert device.model == entry["model"]
    assert device.daily_summaries == entry["daily_summaries"]
    assert device.last_month_summary == entry["last_month_summary"]
    assert device.today_playing_time == (today.get("playingTime") or 0)
    assert device.today_exceeded_time == (today.get("exceededTime") or 0)

    for profile in _monthly_profiles(entry):
        player = device.get_player(profile["playerId"])
        assert isinstance(player, Player)
        assert player.player_id == profile["playerId"]
        assert player.nickname == profile["nickname"]
        assert player.month_summary == next(
            p["summary"]
            for p in entry["last_month_summary"]["players"]
            if p.get("profile", {}).get("playerId") == profile["playerId"]
        )

    for game in unique_played_games(entry["daily_summaries"]):
        application = device.get_application(game["applicationId"])
        assert isinstance(application, Application)
        assert application.application_id == game["applicationId"]
        assert application.name == game["title"]


async def test_calculating_empty_today(dump: dict, mock_api: Api, pcs: dict):
    """Device 1 today is CALCULATING with no players; monthly players keep empty apps."""
    entry, device = await _load_device(dump, "Device 1 (P01)", mock_api, pcs)
    today = entry["daily_summaries"][0]

    assert today["date"] == "2026-08-17"
    assert today["result"] == "CALCULATING"
    assert today["players"] == []
    assert device.today_playing_time == 0
    assert _monthly_profiles(entry)
    for player in device.players:
        assert isinstance(player, Player)
        assert player.apps == []


async def test_shared_play_same_game_same_time(dump: dict, mock_api: Api, pcs: dict):
    """Device 1 on 2026-08-16: two players, each Minecraft 70 against a device total of 70."""
    entry, device = await _load_device(dump, "Device 1 (P01)", mock_api, pcs)
    day = daily_summary_on(entry, "2026-08-16")
    players = Player.from_device_daily_summary([day], device.applications)

    assert day["playingTime"] == 70
    assert len(players) == 2
    for player in players:
        assert isinstance(player, Player)
        assert player.playing_time == 70
        assert len(player.apps) == 1
        usage = player.apps[0]
        assert isinstance(usage, PlayedAppUsage)
        assert usage.playing_time == 70
        assert usage.application.application_id == MINECRAFT_ID
        assert usage.application is device.get_application(MINECRAFT_ID)


async def test_uneven_shared_play_cumulative_application_time(dump: dict, mock_api: Api, pcs: dict):
    """Device 1 on 2026-08-10: Minecraft 75+15 is summed on Application.today_time_played."""
    entry, device = await _load_device(dump, "Device 1 (P01)", mock_api, pcs)
    day = daily_summary_on(entry, "2026-08-10")
    players = {p.player_id: p for p in Player.from_device_daily_summary([day], device.applications)}

    assert day["playingTime"] == 115
    assert players["player-1"].playing_time == 75
    assert players["player-1"].apps[0].playing_time == 75
    assert players["player-1"].apps[0].application.application_id == MINECRAFT_ID
    assert players["player-2"].playing_time == 15
    assert players["player-2"].apps[0].playing_time == 15
    assert players["player-2"].apps[0].application.application_id == MINECRAFT_ID
    assert players["player-3"].playing_time == 35
    assert players["player-3"].apps[0].playing_time == 35
    assert players["player-3"].apps[0].application.application_id == FC26_ID

    device.daily_summaries = [day]
    minecraft = device.get_application(MINECRAFT_ID)
    await minecraft._internal_update_callback(device)  # pylint: disable=protected-access
    assert minecraft.today_time_played == 90


async def test_two_games_one_player(dump: dict, mock_api: Api, pcs: dict):
    """Device 4 today has one player with two PlayedAppUsage entries (30 + 30 vs 65)."""
    entry, device = await _load_device(dump, "Device 4 (P00)", mock_api, pcs)
    today = entry["daily_summaries"][0]
    player = device.get_player("player-9")

    assert today["date"] == "2026-07-26"
    assert today["playingTime"] == 65
    assert device.today_playing_time == 65
    assert isinstance(player, Player)
    assert player.playing_time == 65
    assert len(player.apps) == 2
    by_id = {usage.application.application_id: usage for usage in player.apps}
    assert set(by_id) == {MINECRAFT_ID, FC26_ID}
    assert all(isinstance(usage, PlayedAppUsage) for usage in player.apps)
    assert by_id[MINECRAFT_ID].playing_time == 30
    assert by_id[FC26_ID].playing_time == 30
    assert by_id[MINECRAFT_ID].application is device.get_application(MINECRAFT_ID)
    assert by_id[FC26_ID].application is device.get_application(FC26_ID)


async def test_unachieved_extra_playing_time_event(dump: dict, mock_api: Api, pcs: dict):
    """Device 2 on 2026-07-26 is UNACHIEVED with extra playing time and Minecraft 65."""
    entry, device = await _load_device(dump, "Device 2 (P00)", mock_api, pcs)
    day = daily_summary_on(entry, "2026-07-26")
    players = Player.from_device_daily_summary([day], device.applications)

    assert day["result"] == "UNACHIEVED"
    assert day["exceededTime"] == 70
    assert day["events"]["addedExtraPlayingTime"] is True
    assert len(players) == 1
    player = players[0]
    assert player.player_id == "player-7"
    assert isinstance(player, Player)
    assert player.playing_time == 65
    assert len(player.apps) == 1
    usage = player.apps[0]
    assert isinstance(usage, PlayedAppUsage)
    assert usage.playing_time == 65
    assert usage.application.application_id == MINECRAFT_ID
    assert usage.application is device.get_application(MINECRAFT_ID)
