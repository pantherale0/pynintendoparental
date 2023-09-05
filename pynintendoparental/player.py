"""Nintendo Player."""

class Player:
    def __init__(self):
        """Init a player."""
        self.player_image: str = None
        self.nickname: str = None
        self.apps: list = []
        self.player_id: str = None
        self.playing_time: int = None

    @classmethod
    def from_device_daily_summary(cls, raw: list[dict]) -> list['Player']:
        """Converts a daily summary response into a list of players."""
        players = []
        for player in raw[0].get("devicePlayers", []):
            parsed = cls()
            parsed.player_id = player.get("playerId")
            parsed.player_image = player.get("imageUri")
            parsed.nickname = player.get("nickname")
            parsed.playing_time = player.get("playingTime")
            parsed.apps = player.get("playedApps")
            players.append(parsed)
        return players
