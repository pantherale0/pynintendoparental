"""A Nintendo application."""

import logging

from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class Application:
    """Model for an application"""

    def __init__(self) -> None:
        """Initialise a application."""
        self.application_id: str = None
        self.first_played_date: datetime = None
        self.has_ugc: bool = None
        self.image_url: str = None # uses small image from Nintendo
        self.playing_days: int = None
        self.shop_url: str = None
        self.name: str = None

    @classmethod
    def from_monthly_summary(cls, raw: dict) -> list['Application']:
        """Converts a raw monthly summary response into a list of applications."""
        parsed = []
        for app in raw.get("playedApps", []):
            _LOGGER.debug("Parsing app %s", app)
            internal = cls()
            internal.application_id = app.get("applicationId")
            internal.first_played_date = datetime.strptime(app.get("firstPlayDate"), "%Y-%d-%m")
            internal.has_ugc = app.get("hasUgc", False)
            internal.image_url = app.get("imageUri").get("small")
            internal.playing_days = app.get("playingDays")
            internal.shop_url = app.get("shopUri")
            internal.name = app.get("title")
            parsed.append(internal)
        return parsed
