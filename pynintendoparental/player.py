"""Nintendo Player."""

from collections.abc import Iterator
from datetime import date, datetime, timezone

from .application import ApplicationRegistry, PlayedAppUsage
from .const import _LOGGER


def _is_stale_daily_summary(summary: dict, now: datetime | None = None) -> bool:
    """Return True when the summary date is before today (Switch has not checked in).

    ``now`` must be in the same timezone used for Nintendo API requests
    (``X-Moon-TimeZone``). The API ``date`` field is a civil date in that zone.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = summary.get("date")
    if not date_str:
        return True
    return date.fromisoformat(date_str) < now.date()


def parse_played_apps(raw: list[dict], app_registry: ApplicationRegistry) -> list[PlayedAppUsage]:
    """Parse the played apps from a daily summary response.

    Args:
        raw: List of daily summary dictionaries from the API.
        app_registry: Application registry to use to parse the played apps.
    Returns:
        List of PlayedAppUsage objects parsed from the summary.
    """
    result = []
    for entry in raw:
        # Handle both platform generations
        app_id = entry.get("applicationId") or entry.get("meta", {}).get("applicationId")
        if not app_id:
            continue
        try:
            app = app_registry.get_application(app_id)
        except ValueError:
            _LOGGER.warning("Application %s not found in registry, skipping.", app_id)
            continue
        result.append(
            PlayedAppUsage(
                application=app,
                playing_time=entry.get("playingTime"),
            )
        )
    return result


class Player:
    """A Nintendo Switch user profile.

    Represents a player profile on a Nintendo Switch console with their gaming activity.

    Attributes:
        player_id: Unique identifier for the player.
        nickname: Player's display name.
        player_image: URL to the player's Mii image.
        playing_time: Total playing time for the current day in minutes.
        apps: List of applications played today with playtime details.
        month_summary: Monthly usage summary data for this player.
    """

    def __init__(self):
        """Init a player."""
        self.player_id: str
        self.player_image: str
        self.nickname: str
        self.apps: list[PlayedAppUsage] = []
        self.month_summary: dict = {}
        self.playing_time: int = 0

    def update_from_daily_summary(
        self,
        raw: list[dict],
        app_registry: ApplicationRegistry,
        now: datetime | None = None,
    ):
        """Update player data from a daily summary response.

        Args:
            raw: List of daily summary dictionaries from the API.
            app_registry: Application registry to use to parse the played apps.
            now: Clock used to decide if the first summary is today. Should be in the
                API timezone. Defaults to UTC now.
        """
        _LOGGER.debug("Updating player %s daily summary", self.player_id)
        for player in raw[0].get("players", []):
            if self.player_id == player["profile"].get("playerId"):
                self.player_image = player["profile"].get("imageUri")
                self.nickname = player["profile"].get("nickname")
                # Nintendo omits today when the Switch has not checked in (ha-core/179748).
                if _is_stale_daily_summary(raw[0], now):
                    self.playing_time = 0
                    self.apps.clear()
                else:
                    self.playing_time = player.get("playingTime")
                    self.apps = parse_played_apps(player.get("playedGames"), app_registry)
                break

    @classmethod
    def from_device_daily_summary(
        cls,
        raw: list[dict],
        app_registry: ApplicationRegistry,
        now: datetime | None = None,
    ) -> list["Player"]:
        """Create Player objects from a device daily summary response.

        Args:
            raw: List of daily summary dictionaries from the API.
            app_registry: Application registry to use to parse the played apps.
            now: Clock used to decide if the first summary is today. Should be in the
                API timezone. Defaults to UTC now.

        Returns:
            List of Player objects parsed from the summary.
        """
        players = []
        _LOGGER.debug("Building players from device daily summary.")
        for player in raw[0].get("players", []):
            parsed = cls()
            parsed.player_id = player["profile"].get("playerId")
            parsed.player_image = player["profile"].get("imageUri")
            parsed.nickname = player["profile"].get("nickname")
            if _is_stale_daily_summary(raw[0], now):
                parsed.playing_time = 0
                parsed.apps.clear()
            else:
                parsed.playing_time = player.get("playingTime")
                parsed.apps = parse_played_apps(player.get("playedGames"), app_registry)
            players.append(parsed)
            _LOGGER.debug("Built player %s", parsed.player_id)
        return players

    @classmethod
    def from_profile(cls, raw: dict) -> "Player":
        """Create a Player object from a profile response.

        Args:
            raw: Profile dictionary from the API.

        Returns:
            A Player object parsed from the profile data.
        """
        parsed = cls()
        parsed.player_id = raw["playerId"]
        parsed.player_image = raw["imageUri"]
        parsed.nickname = raw["nickname"]
        return parsed


class PlayerRegistry:
    """Registry of players for a device."""

    def __init__(self):
        """Initialise the player registry."""
        self._players: list[Player] = []
        self._player_ids: set[str] = set()

    def __contains__(self, player_id: str) -> bool:
        """Check if a player is in the registry."""
        return player_id in self._player_ids

    def __len__(self) -> int:
        """Get the number of players in the registry."""
        return len(self._players)

    def __iter__(self) -> Iterator[Player]:
        """Iterate over the players in the registry."""
        yield from self._players

    def get_player(self, player_id: str) -> Player:
        """Get a player by its ID."""
        if player_id not in self._player_ids:
            raise ValueError(f"Player {player_id} not found.")
        for player in self._players:
            if player.player_id == player_id:
                return player

    def get(self, player_id: str) -> Player | None:
        """Compatibility method for getting a player by its ID."""
        try:
            return self.get_player(player_id)
        except ValueError:
            return None

    def add_player(self, player: Player):
        """Add a player to the registry."""
        if player.player_id in self._player_ids:
            raise ValueError(f"Player {player.player_id} already in registry.")
        self._players.append(player)
        self._player_ids.add(player.player_id)

    def remove_player(self, player_id: str):
        """Remove a player from the registry."""
        if player_id not in self._player_ids:
            raise ValueError(f"Player {player_id} not found.")
        self._players.remove(self.get_player(player_id))
        self._player_ids.remove(player_id)
