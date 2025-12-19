# pylint: disable=line-too-long
"""pynintendoparental"""

import logging

_LOGGER = logging.getLogger(__package__)
CLIENT_ID = "54789befb391a838"
MOBILE_APP_PKG = "com.nintendo.znma"
MOBILE_APP_VERSION = "2.3.1"
MOBILE_APP_BUILD = "620"
OS_NAME = "ANDROID"
OS_VERSION = "34"
OS_STR = f"{OS_NAME} {OS_VERSION}"
DEVICE_MODEL = "Pixel 4 XL"
BASE_URL = "https://app.lp1.znma.srv.nintendo.net"
USER_AGENT = f"moon_ANDROID/{MOBILE_APP_VERSION} ({MOBILE_APP_PKG}; build:{MOBILE_APP_BUILD}; {OS_STR})"

DAYS_OF_WEEK = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

ENDPOINTS = {
    "get_account_devices": {
        "url": "{BASE_URL}/v2/actions/user/fetchOwnedDevices",
        "method": "GET",
    },
    "get_account_device": {
        "url": "{BASE_URL}/v2/actions/user/fetchOwnedDevice?deviceId={DEVICE_ID}",
        "method": "GET",
    },
    "get_device_daily_summaries": {
        "url": "{BASE_URL}/v2/actions/playSummary/fetchDailySummaries?deviceId={DEVICE_ID}",
        "method": "GET",
    },
    "get_device_monthly_summaries": {
        "url": "{BASE_URL}/v2/actions/playSummary/fetchLatestMonthlySummary?deviceId={DEVICE_ID}",
        "method": "GET",
    },
    "get_device_parental_control_setting": {
        "url": "{BASE_URL}/v2/actions/parentalControlSetting/fetchParentalControlSetting?deviceId={DEVICE_ID}",
        "method": "GET",
    },
    "update_restriction_level": {
        "url": "{BASE_URL}/v2/actions/parentalControlSetting/updateRestrictionLevel",
        "method": "POST",
    },
    "update_play_timer": {
        "url": "{BASE_URL}/v3/actions/parentalControlSetting/updatePlayTimer",
        "method": "POST",
    },
    "update_unlock_code": {
        "url": "{BASE_URL}/v2/actions/parentalControlSetting/updateUnlockCode",
        "method": "POST",
    },
    "get_device_monthly_summary": {
        "url": "{BASE_URL}/v2/actions/playSummary/fetchMonthlySummary?deviceId={DEVICE_ID}&year={YEAR}&month={MONTH}&containLatest=false",
        "method": "GET",
    },
    "update_extra_playing_time": {
        "url": "{BASE_URL}/v2/actions/device/updateExtraPlayingTime",
        "method": "POST",
    },
}
