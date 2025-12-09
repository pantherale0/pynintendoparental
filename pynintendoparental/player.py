"""Nintendo Player."""

from .const import _LOGGER


class Player:
    """Defines a single player on a Nintendo device."""

    def __init__(self):
        """Init a player."""
        self.player_image: str | None = None
        self.nickname: str | None = None
        self.apps: list = []
        self.month_summary: dict = {}
        self.player_id: str | None = None
        self.playing_time: int = 0

    def update_from_daily_summary(self, raw: list[dict]):
        """Update the current instance of the player from the daily summery"""
        _LOGGER.debug("Updating player %s daily summary", self.player_id)
        for player in raw[0].get("players", []):
            if self.player_id == player["profile"].get("playerId"):
                self.player_image = player["profile"].get("imageUri")
                self.nickname = player["profile"].get("nickname")
                self.playing_time = player.get("playingTime")
                self.apps = player.get("playedGames")
                break

    @classmethod
    def from_device_daily_summary(cls, raw: list[dict]) -> list["Player"]:
        """Converts a daily summary response into a list of players."""
        players = []
        _LOGGER.debug("Building players from device daily summary.")
        for player in raw[0].get("players", []):
            parsed = cls()
            parsed.player_id = player["profile"].get("playerId")
            parsed.player_image = player["profile"].get("imageUri")
            parsed.nickname = player["profile"].get("nickname")
            parsed.playing_time = player.get("playingTime")
            parsed.apps = player.get("playedGames")
            players.append(parsed)
            _LOGGER.debug("Built player %s", parsed.player_id)
        return players

    @classmethod
    def from_profile(cls, raw: dict) -> "Player":
        """Converts a profile response into a player."""
        parsed = cls()
        parsed.player_id = raw.get("playerId")
        parsed.player_image = raw.get("imageUri")
        parsed.nickname = raw.get("nickname")
        return parsed
