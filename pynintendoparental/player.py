"""Nintendo Player."""

from dataclasses import dataclass, field
from typing import Optional, List, Sequence, Mapping, Any, Tuple, Iterator

from .const import _LOGGER

@dataclass(slots=True)
class Player:
    """Defines a single player on a Nintendo device."""
    player_image: Optional[str] = None
    nickname: Optional[str] = None
    apps: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    player_id: Optional[str] = None
    playing_time: Optional[int] = None

    def update_from_daily_summary(self, raw: Sequence[Mapping[str, Any]]) -> None:
        """Update the current instance of the player from the daily summary.
        Stores apps as a tuple to reduce per-instance overhead; extracts only needed fields.
        """
        _LOGGER.debug("Updating player %s daily summary", self.player_id)
        if not raw:
            _LOGGER.debug("Empty daily summary received.")
            return

        # normalize potential keys
        root = raw[0] if raw else {}
        players_list = root.get("devicePlayers") or root.get("players") or []
        for player in players_list:
            profile = player.get("profile", {}) or {}
            pid = profile.get("playerId")
            if pid and self.player_id == pid:
                # extract only what's needed (avoid keeping raw)
                self.player_id = pid
                self.player_image = profile.get("imageUri")
                self.nickname = profile.get("nickname")
                self.playing_time = player.get("playingTime")
                apps_list = player.get("playedApps") or player.get("playedGames") or []
                # store as tuple to reduce overhead and avoid mutations
                self.apps = tuple(apps_list)
                break

    @classmethod
    def from_device_daily_summary(cls, raw: Sequence[Mapping[str, Any]]) -> List['Player']:
        """Converts a daily summary response into a list of players."""
        players: List[Player] = []
        _LOGGER.debug("Building players from device daily summary.")
        if not raw:
            _LOGGER.debug("Empty daily summary for building players")
            return players

        root = raw[0]
        players_list = root.get("players") or root.get("devicePlayers") or []
        for player in players_list:
            profile = player.get("profile", {}) or {}
            parsed = cls(
                player_id=profile.get("playerId"),
                player_image=profile.get("imageUri"),
                nickname=profile.get("nickname"),
                playing_time=player.get("playingTime"),
                apps=tuple(player.get("playedGames") or player.get("playedApps") or ()),
            )
            players.append(parsed)
            _LOGGER.debug("Built player %s", parsed.player_id)
        return players

    @classmethod
    def from_monthly_summary(cls, summary: List[Mapping[str, Any]]) -> List['Player']:
        """Converts a monthly summary response into a list of players."""
        return [
            cls(
                player_id=player["profile"].get("playerId"),
                player_image=player["profile"].get("imageUri"),
                nickname=player["profile"].get("nickname")
            ) for player in summary]

    @classmethod
    def iter_from_device_daily_summary(cls, raw: Sequence[Mapping[str, Any]]) -> Iterator['Player']:
        """Stream players (useful to avoid building large lists)."""
        if not raw:
            return
        root = raw[0]
        players_list = root.get("players") or root.get("devicePlayers") or []
        for player in players_list:
            profile = player.get("profile", {}) or {}
            yield cls(
                player_id=profile.get("playerId"),
                player_image=profile.get("imageUri"),
                nickname=profile.get("nickname"),
                playing_time=player.get("playingTime"),
                apps=tuple(player.get("playedGames") or player.get("playedApps") or ()),
            )
