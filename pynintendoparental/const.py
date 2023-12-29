# pylint: disable=line-too-long
"""pynintendoparental"""
__version__ = '0.3.2'

import logging

_LOGGER = logging.getLogger(__package__)
MOBILE_APP_PKG = "com.nintendo.znma"
MOBILE_APP_VERSION = "1.20.0"
MOBILE_APP_BUILD = "282"
OS_NAME = "ANDROID"
OS_VERSION = "33"
OS_STR = f"{OS_NAME} {OS_VERSION}"
DEVICE_MODEL = "Pixel 4 XL"
BASE_URL = "https://api-lp1.pctl.srv.nintendo.net/moon/v1"
USER_AGENT = f"moon_ANDROID/{MOBILE_APP_VERSION} ({MOBILE_APP_PKG}; build:{MOBILE_APP_BUILD}; {OS_STR})"

ENDPOINTS = {
    "get_account_details": {
        "url": "{BASE_URL}/users/{ACCOUNT_ID}",
        "method": "GET"
    },
    "get_account_devices": {
        "url": "{BASE_URL}/users/{ACCOUNT_ID}/devices?filter.device.activated.$eq=true",
        "method": "GET"
    },
    "get_account_device": {
        "url": "{BASE_URL}/users/{ACCOUNT_ID}/devices/{DEVICE_ID}",
        "method": "GET"
    },
    "get_device_daily_summaries": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/daily_summaries",
        "method": "GET"
    },
    "get_device_monthly_summaries": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/monthly_summaries",
        "method": "GET"
    },
    "get_device_parental_control_setting": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/parental_control_setting",
        "method": "GET"
    },
    "update_device_parental_control_setting": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/parental_control_setting",
        "method": "POST"
    },
    "update_device_whitelisted_applications": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/parental_control_setting/whitelisted_applications",
        "method": "POST"
    },
    "get_device_parental_control_setting_state": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/parental_control_setting_state",
        "method": "GET"
    },
    "update_device_alarm_setting_state": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/alarm_setting_state",
        "method": "POST"
    },
    "get_device_alarm_setting_state": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/alarm_setting_state",
        "method": "POST"
    },
    "get_device_monthly_summary": {
        "url": "{BASE_URL}/devices/{DEVICE_ID}/monthly_summaries/{YEAR}-{MONTH}",
        "method": "GET"
    }
}
