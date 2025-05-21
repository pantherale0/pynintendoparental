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

    def __init__(self, auth, tz, lang, session: aiohttp.ClientSession=None):
        """INIT"""
        self._auth: Authenticator = auth
        self._tz = tz
        self._language = lang
        if session is None:
            session = aiohttp.ClientSession()
            self._session_created_internally = True
        self._session = session

    @property
    def _auth_token(self) -> str:
        """Returns the auth token."""
        return f"Bearer {self._auth.access_token}"

    @property
    def account_id(self):
        """Return the account id."""
        return self._auth.account_id

    @property
    def _headers(self) -> dict:
        """Return web request headers."""
        return {
            "User-Agent": USER_AGENT,
            "X-Moon-App-Id": MOBILE_APP_PKG,
            "X-Moon-Os": OS_NAME,
            "X-Moon-Os-Version": OS_VERSION,
            "X-Moon-Model": DEVICE_MODEL,
            "X-Moon-App-Display-Version": MOBILE_APP_VERSION,
            "X-Moon-App-Internal-Version": MOBILE_APP_BUILD,
            "X-Moon-TimeZone": self._tz,
            "X-Moon-Os-Language": self._language,
            "X-Moon-App-Language": self._language,
            "Authorization": self._auth_token
        }

    async def async_close(self):
        """Closes the underlying aiohttp.ClientSession if it was created by this instance."""
        if hasattr(self, '_session_created_internally') and self._session_created_internally and self._session and not self._session.closed:
            await self._session.close()
            self._session = None # Optional: clear the session attribute

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
        self._session.headers.update(self._headers)
        async with self._session.request(
            method=e_point.get("method"),
            url=url,
            json=body
        ) as response:
            _LOGGER.debug("%s request to %s status code %s",
                            e_point.get("method"),
                            url,
                            response.status)
            if _check_http_success(response.status):
                resp["status"] = response.status
                resp["text"] = await response.text()
                try:
                    resp["json"] = await response.json()
                except (aiohttp.ContentTypeError, ValueError) as e:
                    _LOGGER.warning(
                        """Failed to decode JSON response from %s.
                        Status: %s, Error: %s.
                        Response text: %s...""",
                        url, response.status, e, resp['text'][:200]
                    )
                    resp["json"] = {}
                resp["headers"] = response.headers
            else:
                raise HttpException("HTTP Error", response.status, await response.text())

        # now return the resp dict
        return resp

    async def async_get_account_details(self) -> dict:
        """Get account details."""
        return await self.send_request(
            endpoint="get_account_details",
            ACCOUNT_ID=self.account_id
        )

    async def async_get_account_devices(self) -> dict:
        """Get account devices."""
        return await self.send_request(
            endpoint="get_account_devices",
            ACCOUNT_ID=self.account_id
        )

    async def async_get_account_device(self, device_id: str) -> dict:
        """Get account device."""
        return await self.send_request(
            endpoint="get_account_device",
            ACCOUNT_ID=self.account_id,
            DEVICE_ID=device_id
        )

    async def async_get_device_daily_summaries(self, device_id: str) -> dict:
        """Get device daily summaries."""
        return await self.send_request(
            endpoint="get_device_daily_summaries",
            DEVICE_ID=device_id
        )

    async def async_get_device_monthly_summaries(self, device_id: str) -> dict:
        """Get device monthly summaries."""
        return await self.send_request(
            endpoint="get_device_monthly_summaries",
            DEVICE_ID=device_id
        )

    async def async_get_device_parental_control_setting(self, device_id: str) -> dict:
        """Get device parental control setting."""
        return await self.send_request(
            endpoint="get_device_parental_control_setting",
            DEVICE_ID=device_id
        )

    async def async_get_device_parental_control_setting_state(self, device_id: str) -> dict:
        """Get device parental control setting state."""
        return await self.send_request(
            endpoint="get_device_parental_control_setting_state",
            DEVICE_ID=device_id
        )

    async def async_get_device_alarm_setting_state(self, device_id: str) -> dict:
        """Get device alarm setting state."""
        return await self.send_request(
            endpoint="get_device_alarm_setting_state",
            DEVICE_ID=device_id
        )

    async def async_get_device_monthly_summary(self, device_id: str, year: int, month: int) -> dict:
        """Get device monthly summary."""
        return await self.send_request(
            endpoint="get_device_monthly_summary",
            DEVICE_ID=device_id,
            YEAR=year,
            MONTH=f"{month:02d}"
        )

    async def async_set_device_parental_control_setting(
            self,
            device_id: str,
            settings: dict
        ) -> dict:
        """Update device parental control setting."""
        return await self.send_request(
            endpoint="update_device_parental_control_setting",
            DEVICE_ID=device_id,
            body=settings
        )

    async def async_set_device_whitelisted_applications(
            self,
            device_id: str,
            applications: dict
        ) -> dict:
        """Update device whitelisted applications."""
        return await self.send_request(
            endpoint="update_device_whitelisted_applications",
            DEVICE_ID=device_id,
            body=applications
        )

    async def async_set_device_alarm_setting_state(
            self,
            device_id: str,
            alarm_state: dict
        ) -> dict:
        """Update device alarm setting state."""
        return await self.send_request(
            endpoint="update_device_alarm_setting_state",
            DEVICE_ID=device_id,
            body=alarm_state
        )
