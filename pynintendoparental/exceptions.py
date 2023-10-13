"""Nintendo Parental exceptions."""

class HttpException(Exception):
    """A HTTP error occured"""

    def __init__(self, *args: object) -> None:
        super().__init__("HTTP Exception", *args)

class InvalidSessionTokenException(HttpException):
    """Provided session token was invalid (invalid_grant)."""

class InvalidOAuthConfigurationException(HttpException):
    """The OAuth scopes are invalid."""
