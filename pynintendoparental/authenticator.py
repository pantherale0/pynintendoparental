"""Nintendo Authentication."""

from __future__ import annotations

from pynintendoauth import NintendoAuth

from .const import CLIENT_ID


class Authenticator(NintendoAuth):
    """Nintendo authentication handler.

    Handles authentication with Nintendo's servers for accessing Parental Controls API.
    Supports both session token and interactive login methods.

    Attributes:
        session_token: The session token for authentication.
        account_id: The authenticated Nintendo account ID.
        login_url: URL for interactive login (when session_token not provided).

    Example:
        Using a session token:
        ```python
        async with aiohttp.ClientSession() as session:
            auth = Authenticator(session_token="YOUR_TOKEN", client_session=session)
            await auth.async_complete_login(use_session_token=True)
        ```

        Interactive login:
        ```python
        async with aiohttp.ClientSession() as session:
            auth = Authenticator(client_session=session)
            print(f"Visit: {auth.login_url}")
            response_url = input("Paste redirect URL: ")
            await auth.async_complete_login(response_url)
        ```
    """

    def __init__(self, session_token=None, client_session=None):
        super().__init__(
            client_id=CLIENT_ID,
            session_token=session_token,
            client_session=client_session,
        )
