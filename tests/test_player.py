"""Tests for the Player class."""

import copy
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from syrupy.assertion import SnapshotAssertion

from pynintendoparental.application import ApplicationRegistry
from pynintendoparental.player import Player, PlayerRegistry, _is_stale_daily_summary, parse_played_apps

from .conftest import FIXED_NOW
from .helpers import load_fixture

# The day after FIXED_NOW — summary date 2025-12-08 is then not today.
NEXT_DAY = FIXED_NOW + timedelta(days=1)


async def test_player_parsing(
    snapshot: SnapshotAssertion,
    app_registry: ApplicationRegistry,
):
    """Test that the player class parsing works as expected."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    players = Player.from_device_daily_summary(daily_summaries_response["dailySummaries"], app_registry)
    assert len(players) > 0
    player = players[0]
    assert player == snapshot


async def test_player_parsing_with_missing_app(
    caplog: pytest.LogCaptureFixture,
    app_registry: ApplicationRegistry,
):
    """Test that the player class parsing works as expected when an app is missing from the registry."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    daily_summaries_response["dailySummaries"][0]["players"][0]["playedGames"][0]["applicationId"] = "missing_app"
    with caplog.at_level(logging.WARNING):
        players = Player.from_device_daily_summary(daily_summaries_response["dailySummaries"], app_registry)
    assert "Application missing_app not found in registry, skipping." in caplog.text
    assert len(players) == 1
    assert players[0].apps == []


async def test_player_registry(
    app_registry: ApplicationRegistry,
    player_registry: PlayerRegistry,
):
    """Test that the player registry works as expected."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    players = Player.from_device_daily_summary(daily_summaries_response["dailySummaries"], app_registry)
    assert len(players) > 0
    player = players[0]
    player_registry.add_player(player)
    assert player_registry.get_player(player.player_id) == player
    assert len(player_registry) == 1
    player_registry.remove_player(player.player_id)
    assert len(player_registry) == 0


async def test_player_registry_exceptions(
    player_registry: PlayerRegistry,
):
    """Test that the player registry exceptions work as expected."""
    player = Player()
    player.player_id = "player_id"
    # Test exception
    with pytest.raises(ValueError):
        player_registry.remove_player(player.player_id)
    # Test not found
    with pytest.raises(ValueError):
        player_registry.get_player(player.player_id)
    # Test already in registry
    player_registry.add_player(player)
    with pytest.raises(ValueError):
        player_registry.add_player(player)


async def test_player_update_from_daily_summary(
    snapshot: SnapshotAssertion,
    app_registry: ApplicationRegistry,
):
    """Test that updating a player from a daily summary works."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    players = Player.from_device_daily_summary(daily_summaries_response["dailySummaries"], app_registry)
    assert len(players) > 0
    player = players[0]

    # Create a deep copy to modify for the update
    updated_summary = copy.deepcopy(daily_summaries_response)

    # Find the corresponding player in the new summary and update their data
    updated_app_id = "010042D00D900000"
    for p_summary in updated_summary["dailySummaries"][0]["players"]:
        if p_summary["profile"]["playerId"] == player.player_id:
            p_summary["playingTime"] = 54321
            p_summary["playedGames"] = [
                {"applicationId": updated_app_id, "playingTime": 100},
            ]
            break

    player.update_from_daily_summary(updated_summary["dailySummaries"], app_registry)

    assert player.playing_time == 54321
    assert len(player.apps) == 1
    assert player.apps[0].application.application_id == updated_app_id
    assert player.apps[0].playing_time == 100
    assert player == snapshot


async def test_player_from_daily_summary_not_today(
    caplog: pytest.LogCaptureFixture,
    app_registry: ApplicationRegistry,
):
    """When the first summary date is before now, playing time and apps are cleared."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    daily_summaries_response["dailySummaries"][0]["players"][0]["playedGames"][0]["applicationId"] = "missing_app"
    with caplog.at_level(logging.WARNING):
        players = Player.from_device_daily_summary(
            daily_summaries_response["dailySummaries"],
            app_registry,
            now=NEXT_DAY,
        )

    assert len(players) == 1
    assert players[0].playing_time == 0
    assert players[0].apps == []
    assert "Application missing_app not found in registry, skipping." not in caplog.text


@pytest.mark.parametrize("missing_date", [None, ""])
async def test_player_from_daily_summary_missing_date(
    app_registry: ApplicationRegistry,
    missing_date: str | None,
):
    """A missing summary date is treated as not today."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    daily_summaries_response["dailySummaries"][0]["date"] = missing_date
    players = Player.from_device_daily_summary(
        daily_summaries_response["dailySummaries"],
        app_registry,
        now=FIXED_NOW,
    )

    assert len(players) == 1
    assert players[0].playing_time == 0
    assert players[0].apps == []


async def test_player_update_from_daily_summary_not_today(app_registry: ApplicationRegistry):
    """Updating after the summary date clears previously parsed today playtime and apps."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    players = Player.from_device_daily_summary(
        daily_summaries_response["dailySummaries"],
        app_registry,
        now=FIXED_NOW,
    )
    player = players[0]
    assert player.playing_time > 0
    assert player.apps

    player.update_from_daily_summary(
        daily_summaries_response["dailySummaries"],
        app_registry,
        now=NEXT_DAY,
    )

    assert player.playing_time == 0
    assert player.apps == []


async def test_player_parse_played_apps_ignoring_none(
    app_registry: ApplicationRegistry,
):
    """Test the parse_played_apps function ignores apps with a null application id."""
    raw = [
        {"applicationId": "010042D00D900000", "playingTime": 100},
        {"applicationId": None, "playingTime": 200},
    ]
    apps = parse_played_apps(raw, app_registry)
    assert len(apps) == 1
    assert apps[0].application.application_id == "010042D00D900000"
    assert apps[0].playing_time == 100


async def test_player_registry_get(
    player_registry: PlayerRegistry,
):
    """Test the player registry get method works as expected."""
    player = Player()
    player.player_id = "player_id"
    player_registry.add_player(player)
    assert player_registry.get(player.player_id) == player
    assert player_registry.get("missing_player") is None


@pytest.mark.parametrize(
    "now, expected_stale",
    [
        pytest.param(
            datetime(2025, 12, 9, 0, 30, tzinfo=ZoneInfo("Asia/Tokyo")),
            True,
            id="tokyo_after_local_midnight",
        ),
        pytest.param(
            datetime(2025, 12, 8, 23, 30, tzinfo=ZoneInfo("Asia/Tokyo")),
            False,
            id="tokyo_before_local_midnight",
        ),
        pytest.param(
            datetime(2025, 12, 8, 17, 30, tzinfo=ZoneInfo("America/Los_Angeles")),
            False,
            id="la_evening_utc_already_next_day",
        ),
        pytest.param(
            datetime(2025, 12, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
            True,
            id="la_local_midnight",
        ),
        pytest.param(
            datetime(2025, 12, 8, 12, 0, tzinfo=ZoneInfo("Europe/London")),
            False,
            id="london_noon_same_day",
        ),
    ],
)
def test_is_stale_daily_summary_timezone_boundaries(now: datetime, expected_stale: bool):
    """Stale checks use the civil date of ``now``, not a UTC-tagged API date."""
    assert _is_stale_daily_summary({"date": "2025-12-08"}, now) is expected_stale
