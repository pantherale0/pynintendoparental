"""Tests for the Player class."""

from syrupy.assertion import SnapshotAssertion
import copy

from pynintendoparental.player import Player

from .helpers import load_fixture


async def test_player_parsing(snapshot: SnapshotAssertion):
    """Test that the player class parsing works as expected."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    players = Player.from_device_daily_summary(
        daily_summaries_response["dailySummaries"]
    )
    assert len(players) > 0
    player = players[0]

    assert player == snapshot


async def test_player_update_from_daily_summary(snapshot: SnapshotAssertion):
    """Test that updating a player from a daily summary works."""
    daily_summaries_response = await load_fixture("device_daily_summaries")
    players = Player.from_device_daily_summary(
        daily_summaries_response["dailySummaries"]
    )
    assert len(players) > 0
    player = players[0]

    # Create a deep copy to modify for the update
    updated_summary = copy.deepcopy(daily_summaries_response)

    # Find the corresponding player in the new summary and update their data
    for p_summary in updated_summary["dailySummaries"][0]["players"]:
        if p_summary["profile"]["playerId"] == player.player_id:
            p_summary["playingTime"] = 54321
            p_summary["playedGames"] = [{"app": "new_app"}]
            break

    player.update_from_daily_summary(updated_summary["dailySummaries"])

    assert player.playing_time == 54321
    assert player.apps == [{"app": "new_app"}]
    assert player == snapshot
