"""A Nintendo application."""

from datetime import datetime

from .const import _LOGGER

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
        self.today_time_played: int = None

    def update_today_time_played(self, daily_summary: dict):
        """Updates the today time played for the given application."""
        _LOGGER.debug("Updating today time played for app %s",
                      self.application_id)
        self.today_time_played = daily_summary.get("playingTime", 0)

    def update(self, updated: 'Application'):
        """Updates self with a given application."""
        _LOGGER.debug("Updating application %s", self.application_id)
        self.application_id = updated.application_id
        self.first_played_date = updated.first_played_date
        self.has_ugc = updated.has_ugc
        self.image_url = updated.image_url
        self.playing_days = updated.playing_days
        self.shop_url = updated.shop_url
        self.name = updated.name
        self.today_time_played = updated.today_time_played

    @classmethod
    def from_daily_summary(cls, raw: list) -> list['Application']:
        """Converts a raw daily summary response into a list of applications."""
        built = []
        if "playedApps" in raw:
            return cls.from_monthly_summary(raw.get("playedApps", []))
        for summary in raw:
            for app in cls.from_monthly_summary(summary.get("playedApps", [])):
                if not cls.check_if_app_in_list(built, app):
                    built.append(app)
        return built

    @staticmethod
    def check_if_app_in_list(app_list: list['Application'], app: 'Application') -> bool:
        """Checks if an app is in a list."""
        for app_li in app_list:
            if app_li.application_id == app.application_id:
                return True
        return False

    @staticmethod
    def return_app_from_list(app_list: list['Application'], application_id: str) -> 'Application':
        """Returns a single app from a given list."""
        for app in app_list:
            if app.application_id == application_id:
                return app
        return None

    @classmethod
    def from_whitelist(cls, raw: dict) -> list['Application']:
        """Converts a raw whitelist response into a list of applications."""
        parsed = []
        for app_id in raw:
            _LOGGER.debug("Parsing app %s", app_id)
            internal = cls()
            internal.application_id = raw[app_id]["applicationId"]
            internal.first_played_date = datetime.strptime(raw[app_id]["firstPlayDate"], "%Y-%m-%d")
            internal.image_url = raw[app_id]["imageUri"]
            internal.name = raw[app_id]["title"]
            parsed.append(internal)
        return parsed

    @classmethod
    def from_monthly_summary(cls, raw: list) -> list['Application']:
        """Converts a raw monthly summary response into a list of applications."""
        parsed = []
        for app in raw:
            _LOGGER.debug("Parsing app %s", app)
            internal = cls()
            internal.application_id = app.get("applicationId").capitalize()
            internal.first_played_date = datetime.strptime(app.get("firstPlayDate"), "%Y-%m-%d")
            internal.has_ugc = app.get("hasUgc", False)
            internal.image_url = app.get("imageUri").get("small")
            internal.playing_days = app.get("playingDays", None)
            internal.shop_url = app.get("shopUri")
            internal.name = app.get("title")
            parsed.append(internal)
        return parsed
