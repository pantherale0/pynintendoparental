"""API handler."""

from datetime import datetime, timedelta

import aiohttp

from .authenticator import Authenticator
from .const import (
    ENDPOINTS,
    BASE_URL,
    USER_AGENT,
    MOBILE_APP_PKG,
    MOBILE_APP_BUILD,
    MOBILE_APP_VERSION,
    OS_VERSION,
    OS_NAME,
    DEVICE_MODEL,
    _LOGGER
)
from .exceptions import HttpException

def _check_http_success(status: int) -> bool:
    return status >= 200 and status < 300

class Api:
    """Nintendo Parental Controls API."""

    def __init__(self, auth, tz, lang):
        """INIT"""
        self._auth: Authenticator = auth
        self._tz = tz
        self._language = lang

    @property
    def _auth_token(self) -> str:
        """Returns the auth token."""
        return f"Bearer {self._auth.access_token}"

    @property
    def account_id(self):
        """Return the account id."""
        return self._auth.account_id

    async def send_request(self, endpoint: str, body: object=None, **kwargs):
        """Sends a request to a given endpoint."""
        _LOGGER.debug("Sending request to %s", endpoint)
        # Get the endpoint from the endpoints map
        e_point = ENDPOINTS.get(endpoint, None)
        if e_point is None:
            raise ValueError("Endpoint does not exist")
        # refresh the token if it has expired.
        if self._auth.expires < (datetime.now()+timedelta(seconds=30)):
            _LOGGER.debug("Access token expired, requesting refresh.")
            await self._auth.perform_refresh()
        # format the URL using the kwargs
        url = e_point.get("url").format(BASE_URL=BASE_URL, **kwargs)
        _LOGGER.debug("Built URL %s", url)
        # now send the HTTP request
        resp: dict = {
            "status": 0,
            "text": "",
            "json": "",
            "headers": ""
        }
        async with aiohttp.ClientSession() as session:
            # Add auth header
            session.headers.add("Authorization", self._auth_token)
            session.headers.add("User-Agent", USER_AGENT)
            session.headers.add("X-Moon-App-Id", MOBILE_APP_PKG)
            session.headers.add("X-Moon-Os", OS_NAME)
            session.headers.add("X-Moon-Os-Version", OS_VERSION)
            session.headers.add("X-Moon-Model", DEVICE_MODEL)
            session.headers.add("X-Moon-TimeZone", self._tz)
            session.headers.add("X-Moon-Os-Language", self._language)
            session.headers.add("X-Moon-App-Language", self._language)
            session.headers.add("X-Moon-App-Display-Version", MOBILE_APP_VERSION)
            session.headers.add("X-Moon-App-Internal-Version", MOBILE_APP_BUILD)
            #session.headers.add("X-Moon-Smart-Device-Id", "190207e4-2f6f-4db7-bc96-fdfe109124f0")
            async with session.request(
                method=e_point.get("method"),
                url=url,
                json=body
            ) as response:
                _LOGGER.debug("Request to %s status code %s", url, response.status)
                if _check_http_success(response.status):
                    resp["status"] = response.status
                    resp["text"] = await response.text()
                    resp["json"] = await response.json()
                    resp["headers"] = response.headers
                else:
                    raise HttpException("HTTP Error", response.status)

        # now return the resp dict
        return resp
