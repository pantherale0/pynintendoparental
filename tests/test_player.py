"""Tests for the Player class."""

import copy
import logging

import pytest
from syrupy.assertion import SnapshotAssertion

from pynintendoparental.application import ApplicationRegistry
from pynintendoparental.player import Player, PlayerRegistry

from .helpers import load_fixture


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
