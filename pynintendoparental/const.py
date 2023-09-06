"""pynintendoparental"""
__version__ = '0.0.3'


BASE_URL = "https://api-lp1.pctl.srv.nintendo.net/moon/v1"
USER_AGENT = "moon_ANDROID/1.18.0 (com.nintendo.znma; build:275; ANDROID 33)"
ENDPOINTS = {
    "get_account_details": {
        "url": "{BASE_URL}/users/{ACCOUNT_ID}",
        "method": "GET"
    },
    "get_account_devices": {
        "url": "{BASE_URL}/users/{ACCOUNT_ID}/devices?filter.device.activated.$eq=true",
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
}
