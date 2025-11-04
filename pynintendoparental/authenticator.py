"""Nintendo Authentication."""

from __future__ import annotations

from pynintendoauth import NintendoAuth

from .const import CLIENT_ID


class Authenticator(NintendoAuth):
    """Authentication functions."""

    def __init__(self, session_token=None, client_session=None):
        super().__init__(
            client_id=CLIENT_ID,
            session_token=session_token,
            client_session=client_session,
        )
