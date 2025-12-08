"""Generates fixture files for pytest."""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker
from pynintendoauth.exceptions import InvalidSessionTokenException

from pynintendoparental import Authenticator
from pynintendoparental.api import Api

_LOGGER = logging.getLogger(__name__)
faker = Faker()

# This map will store original values and their fake counterparts
# to ensure consistency across all fixture files.
ANONYMIZATION_MAP = {}

# Define keys that should be anonymized
ANONYMIZE_KEYS = [
    "deviceId",
    "label",
    "nickname",
    "playerId",
    "title",
    "serialNumber",
    "code",
    "synchronizedUnlockCode",
    "synchronizedEtag",
    "externalNickname",
    "nintendoAccountId",
    "targetEtag",
    "notificationToken",
    "id",
]


def _save_fixture(data: dict, filename: str):
    """Saves fixture data to a file."""
    fixture_dir = Path("tests/fixtures")
    fixture_dir.mkdir(parents=True, exist_ok=True)
    filepath = fixture_dir / f"{filename}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    _LOGGER.info("Wrote fixture to %s", filepath)


def _anonymize_data(data):
    """Recursively anonymizes sensitive data in a dictionary or list."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ANONYMIZE_KEYS and isinstance(value, str):
                if value not in ANONYMIZATION_MAP:
                    if "id" in key.lower():
                        ANONYMIZATION_MAP[value] = faker.hexify(
                            text="^" * (len(value) if len(value) > 0 else 16)
                        ).upper()
                    elif "name" in key.lower() or "nickname" in key.lower():
                        ANONYMIZATION_MAP[value] = faker.user_name()
                    elif "token" in key.lower():
                        ANONYMIZATION_MAP[value] = faker.pystr_format(
                            string_format="?#?#?#?#?#?#?#?#"
                        )
                    elif "serial" in key.lower() or "etag" in key.lower():
                        ANONYMIZATION_MAP[value] = faker.ean(length=13)
                    elif "code" in key.lower():
                        ANONYMIZATION_MAP[value] = str(faker.random_number(digits=4, fix_len=True))
                    else:
                        ANONYMIZATION_MAP[value] = faker.word()
                data[key] = ANONYMIZATION_MAP[value]
            elif key == "imageUri" and isinstance(value, str):
                data[key] = faker.image_url()
            else:
                _anonymize_data(value)
    elif isinstance(data, list):
        for item in data:
            _anonymize_data(item)
    return data


async def _authenticate() -> Authenticator | None:
    """Handles authentication."""
    try:
        if (
            bool(int(os.environ.get("USE_SESSION_TOKEN", 0)))
            or input("Should we use a session token? [N/y] ").upper() == "Y"
        ):
            auth = Authenticator(
                session_token=os.environ.get("SESSION_TOKEN") or input("Token: ")
            )
            await auth.async_complete_login(use_session_token=True)
        else:
            auth = Authenticator()
            _LOGGER.info("Login using %s", auth.login_url)
            await auth.async_complete_login(input("Response URL: "))
        _LOGGER.info("Logged in, ready.")
        _LOGGER.info("Your session token is: %s", auth.session_token)
        _LOGGER.info(
            "You can save this in your .env file as SESSION_TOKEN to skip login next time."
        )
        return auth
    except InvalidSessionTokenException as err:
        _LOGGER.error("Invalid session token provided: %s", err)
    except Exception as err:
        _LOGGER.critical(err)
    return None


async def main():
    """Main function to generate fixtures."""
    load_dotenv()

    auth = await _authenticate()
    if not auth:
        return

    api = Api(auth=auth, tz="Europe/London", lang="en-GB")

    # 1. Get account devices
    account_devices = await api.async_get_account_devices()

    # Get the real device ID before we anonymize the data
    devices = account_devices.get("json", {}).get("ownedDevices", [])
    if not devices:
        _LOGGER.warning("No devices found on this account.")
        # Still save the (empty) fixture
        _save_fixture(_anonymize_data(account_devices.get("json", {})), "account_devices")
        return

    device_id = devices[0]["deviceId"]
    _LOGGER.info("Using device with ID %s for device-specific fixtures.", device_id)

    # Now save the anonymized fixture
    _save_fixture(_anonymize_data(account_devices["json"]), "account_devices")

    # 2. Get single account device
    account_device = await api.async_get_account_device(device_id=device_id)
    _save_fixture(_anonymize_data(account_device["json"]), "account_device")

    # 3. Get daily summaries
    daily_summaries = await api.async_get_device_daily_summaries(device_id=device_id)
    _save_fixture(_anonymize_data(daily_summaries["json"]), "device_daily_summaries")

    # 4. Get parental control settings
    parental_control_settings = await api.async_get_device_parental_control_setting(
        device_id=device_id
    )
    _save_fixture(
        _anonymize_data(parental_control_settings["json"]),
        "device_parental_control_setting",
    )

    # 5. Get available monthly summaries
    monthly_summaries_list = await api.async_get_device_monthly_summaries(
        device_id=device_id
    )
    _save_fixture(
        _anonymize_data(monthly_summaries_list["json"]), "device_monthly_summaries_list"
    )

    # 6. Get a specific monthly summary
    available = monthly_summaries_list["json"].get("available", [])
    if available:
        latest_summary_info = available[0]
        year = int(latest_summary_info["year"])
        month = int(latest_summary_info["month"])
        _LOGGER.info("Fetching monthly summary for %s-%s", year, month)
        monthly_summary = await api.async_get_device_monthly_summary(
            device_id=device_id, year=year, month=month
        )
        _save_fixture(_anonymize_data(monthly_summary["json"]), "device_monthly_summary")
    else:
        _LOGGER.warning("No monthly summaries available to fetch.")

    await auth.client_session.close()
    _LOGGER.info("Fixture generation and anonymization complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _LOGGER.info("Exiting.")
