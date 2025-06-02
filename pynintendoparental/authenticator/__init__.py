"""Nintendo Authentication."""
from __future__ import annotations

import logging
import base64
import hashlib
import random
import string

from urllib.parse import urlencode, urlparse

from datetime import datetime, timedelta

import aiohttp

from pynintendoparental.exceptions import (
    HttpException,
    InvalidOAuthConfigurationException,
    InvalidSessionTokenException
)
from .const import (
    TOKEN_URL,
    SESSION_TOKEN_URL,
    CLIENT_ID,
    GRANT_TYPE,
    MY_ACCOUNT_ENDPOINT,
    REDIRECT_URI,
    SCOPES,
    AUTHORIZE_URL
)

_LOGGER = logging.getLogger(__name__)

def _parse_response_token(token: str) -> dict:
    """Parses a response token."""
    _LOGGER.debug(">> Parsing response token.")
    try:
        url = urlparse(token)
        params = url.fragment.split('&')
        response = {}
        for param in params:
            response = {
                **response,
                param.split('=')[0]: param.split('=')[1]
            }
        return response
    except Exception as exc:
        raise ValueError("Invalid token provided.") from exc

def _hash(text: str):
    """Hash given text for login."""
    text = hashlib.sha256(text.encode()).digest()
    text = base64.urlsafe_b64encode(text).decode()
    return text.replace("=", "")

def _rand():
    return ''.join(random.choice(string.ascii_letters) for _ in range(50))

class Authenticator:
    """Authentication functions."""

    def __init__(
            self,
            session_token = None,
            auth_code_verifier = None,
            client_session: aiohttp.ClientSession = None
        ):
        """Basic init."""
        _LOGGER.debug(">> Init authenticator.")
        self._at_expiry: datetime = None
        self._access_token: str = None
        self.available_scopes: dict = None
        self.account_id: str = None
        self.account: dict = None
        self._auth_code_verifier: str = auth_code_verifier
        self._refresh_token: str = None
        self._id_token: str = None
        self._session_token: str = session_token
        self.login_url: str = None
        if client_session is None:
            client_session = aiohttp.ClientSession()
        self.client_session: aiohttp.ClientSession = client_session

    @property
    def get_session_token(self) -> str:
        """Return the session token."""
        return self._session_token

    @property
    def access_token(self) -> str:
        """Return the formatted access token."""
        return f"Bearer {self._id_token}" # v2 seems to use ID token for API access?

    @property
    def access_token_expired(self) -> bool:
        """Check if the access token has expired."""
        return self._at_expiry < (datetime.now()+timedelta(minutes=1))

    async def _request_handler(self, method, url, json=None, data=None, headers: dict=None):
        """Send a HTTP request"""
        if headers is None:
            headers = {}
        response: dict = {
            "status": 0,
            "text": "",
            "json": "",
            "headers": ""
        }
        async with self.client_session.request(
            method=method,
            url=url,
            json=json,
            data=data,
            headers=headers
        ) as resp:
            response["status"] = resp.status
            response["text"] = await resp.text()
            response["json"] = await resp.json()
            response["headers"] = resp.headers
        return response

    def _read_tokens(self, tokens: dict):
        """Reads tokens into self."""
        self.available_scopes = tokens.get("scope")
        self._at_expiry = datetime.now() + timedelta(seconds=tokens.get("expires_in"))
        self._id_token = tokens.get("id_token")
        self._access_token = tokens.get("access_token")

    async def perform_login(self, session_token_code):
        """Retrieves initial tokens."""
        _LOGGER.debug("Performing initial login.")
        session_token_form = aiohttp.FormData()
        session_token_form.add_field("client_id", CLIENT_ID)
        session_token_form.add_field("session_token_code", session_token_code)
        session_token_form.add_field("session_token_code_verifier", self._auth_code_verifier)
        session_token_response = await self._request_handler(
            method="POST",
            url=SESSION_TOKEN_URL,
            data=session_token_form
        )

        if session_token_response.get("status") != 200:
            raise HttpException(f"login error {session_token_response.get('status')}")

        self._session_token = session_token_response["json"]["session_token"]

    async def perform_refresh(self):
        """Refresh the access token."""
        _LOGGER.debug("Refreshing access token.")
        token_response = await self._request_handler(
            method="POST",
            url=TOKEN_URL,
            json={
                "client_id": CLIENT_ID,
                "grant_type": GRANT_TYPE,
                "session_token": self.get_session_token
            }
        )

        if token_response["status"] == 400:
            raise InvalidSessionTokenException(token_response["json"]["error"])

        if token_response["status"] == 401:
            raise InvalidOAuthConfigurationException(token_response["json"]["error"])

        if token_response.get("status") != 200:
            raise HttpException(f"login error {token_response.get('status')}")

        self._read_tokens(token_response.get("json"))
        if self.account_id is None:
            # fill account_id
            account = await self._request_handler(
                method="GET",
                url=MY_ACCOUNT_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self._access_token}"
                }
            )
            if account["status"] != 200:
                raise HttpException(f"Unable to get account_id {token_response.get('status')}")
            self.account_id = account["json"]["id"]
            self.account = account["json"]

    @classmethod
    def generate_login(
        cls,
        client_session: aiohttp.ClientSession | None = None) -> 'Authenticator':
        """Starts configuration of the authenticator."""
        verifier = _rand()

        auth = cls(auth_code_verifier=verifier, client_session=client_session)

        query = {
            "client_id": CLIENT_ID,
            # "interacted": 1,
            "redirect_uri": REDIRECT_URI,
            "response_type": "session_token_code",
            "scope": "+".join(SCOPES),
            "session_token_code_challenge": _hash(verifier),
            "session_token_code_challenge_method": "S256",
            "state": _rand(),
            "theme": "login_form"
        }

        auth.login_url = AUTHORIZE_URL.format(urlencode(query)).replace("%2B", "+")
        return auth

    @classmethod
    async def complete_login(cls,
                     auth: Authenticator | None,
                     response_token: str,
                     is_session_token: bool=False,
                     client_session: aiohttp.ClientSession | None = None) -> Authenticator:
        """Creates and logs into Nintendo APIs"""
        if is_session_token:
            auth = cls(session_token=response_token, client_session=client_session)
            await auth.perform_refresh()
        else:
            response_token = _parse_response_token(response_token)
            await auth.perform_login(
                session_token_code=response_token.get("session_token_code")
            )
            await auth.perform_refresh()

        return auth
