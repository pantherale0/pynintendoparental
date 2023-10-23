"""Nintendo Player."""

from .const import _LOGGER

class Player:
    """Defines a single player on a Nintendo device."""
    def __init__(self):
        """Init a player."""
        self.player_image: str = None
        self.nickname: str = None
        self.apps: list = []
        self.player_id: str = None
        self.playing_time: int = None

    def update_from_daily_summary(self, raw: list[dict]):
        """Update the current instance of the player from the daily summery"""
        _LOGGER.debug("Updating player %s daily summary", self.player_id)
        for player in raw[0].get("devicePlayers", []):
            if self.player_id is player.get("playerId"):
                self.player_id = player.get("playerId")
                self.player_image = player.get("imageUri")
                self.nickname = player.get("nickname")
                self.playing_time = player.get("playingTime")
                self.apps = player.get("playedApps")
                break

    @classmethod
    def from_device_daily_summary(cls, raw: list[dict]) -> list['Player']:
        """Converts a daily summary response into a list of players."""
        players = []
        _LOGGER.debug("Building players from device daily summary.")
        for player in raw[0].get("devicePlayers", []):
            parsed = cls()
            parsed.player_id = player.get("playerId")
            parsed.player_image = player.get("imageUri")
            parsed.nickname = player.get("nickname")
            parsed.playing_time = player.get("playingTime")
            parsed.apps = player.get("playedApps")
            players.append(parsed)
            _LOGGER.debug("Built player %s", parsed.player_id)
        return players
