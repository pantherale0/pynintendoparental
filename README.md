<div align="center">

# Python Nintendo Parental Controls

A simple, Python API to connect to Nintendo Switch Parental Controls.

[![Test Status](https://github.com/pantherale0/pynintendoparental/actions/workflows/test.yml/badge.svg)](https://github.com/pantherale0/pynintendoparental/actions/workflows/test.yml)
[![Coverage Status](https://codecov.io/gh/pantherale0/pynintendoparental/branch/main/graph/badge.svg?token=SO6VDF7951)](https://codecov.io/gh/pantherale0/pynintendoparental)
[![PyPi](https://img.shields.io/pypi/v/pynintendoparental)](https://pypi.org/project/pynintendoparental)
[![Licence](https://img.shields.io/github/license/pantherale0/pynintendoparental)](LICENSE)

<a href="https://www.buymeacoffee.com/pantherale0" target="_blank" title="buymeacoffee">
  <img src="https://iili.io/JoQ1MeS.md.png"  alt="buymeacoffee-yellow-badge" style="width: 104px;">
</a>

</div>

## Install

```bash
# Install tool
pip3 install pynintendoparental

# Install locally
just install
```

## Usage

### Authentication

This library requires authentication with Nintendo's servers. The `pynintendoparental.Authenticator` class handles this. There are two ways to authenticate:

**Method 1: Using a Session Token**

If you already have a `session_token`, you can pass it to the `Authenticator`:

```python
import aiohttp
from pynintendoparental.authenticator import Authenticator

async with aiohttp.ClientSession() as session:
    session_token = "YOUR_SESSION_TOKEN"
    auth = Authenticator(session_token, session)
    await auth.async_complete_login(use_session_token=True)
```

**Method 2: Interactive Login**

If you don't have a `session_token`, you can perform an interactive login to obtain one. The library will provide a login URL. You need to open this URL in your browser, log in to your Nintendo Account, and then copy the URL of the "Select this person" button and paste it back into your application.

Here is an example of how to do this:

```python
import asyncio
import aiohttp
from pynintendoparental.authenticator import Authenticator

async def interactive_login():
    """Performs an interactive login to get a session token."""
    async with aiohttp.ClientSession() as session:
        auth = Authenticator(client_session=session)
        print("Please open the following URL in your browser:")
        print(auth.login_url)
        
        response_url = input("Please paste the URL you were redirected to: ")
        await auth.async_complete_login(response_url)
        
        print(f"Login successful! Your session token is: {auth.session_token}")
        print("You can save this token to avoid logging in next time.")
        return auth

async def main():
    auth = await interactive_login()
    # You can now use the 'auth' object with NintendoParental
    # nintendo = await NintendoParental.create(auth)

if __name__ == "__main__":
    asyncio.run(main())
```

### Basic Usage

Here's a simple example of how to use `pynintendoparental`:

```python
import asyncio
import aiohttp

from pynintendoparental import NintendoParental
from pynintendoparental.authenticator import Authenticator

async def main():
    """The main function."""
    session_token = "YOUR_SESSION_TOKEN"  # Replace with your session token

    async with aiohttp.ClientSession() as session:
        auth = Authenticator(session_token, session)
        await auth.async_complete_login(use_session_token=True)
        nintendo = await NintendoParental.create(auth)

        # Iterate through all devices
        for device in nintendo.devices.values():
            print(f"Device: {device.name}")
            print(f"  ID: {device.device_id}")
            print(f"  Model: {device.model}")
            print(f"  Playtime limit: {device.limit_time} minutes")
            print(f"  Today's playing time: {device.today_playing_time} minutes")
            print(f"  Time remaining: {device.today_time_remaining} minutes")

            # Update the daily playtime limit
            # await device.update_max_daily_playtime(180) # Set to 3 hours

if __name__ == "__main__":
    asyncio.run(main())
```

### The `NintendoParental` object

The main entry point is the `NintendoParental` object. You create it using the asynchronous class method `create`:

```python
nintendo = await NintendoParental.create(auth, timezone="Europe/London", lang="en-GB")
```

- `auth`: An `Authenticator` instance.
- `timezone`: (Optional) The timezone to use for API requests. Defaults to "Europe/London".
- `lang`: (Optional) The language to use for API requests. Defaults to "en-GB".

After creation, the `NintendoParental` object will have a `devices` property, which is a dictionary of `Device` objects, keyed by their device ID.

### The `Device` object

The `Device` object contains information about a specific Nintendo Switch console and allows you to control it.

#### Properties

- `name` (str): The name of the device.
- `device_id` (str): The unique ID of the device.
- `model` (str): The model of the device (e.g., "Switch").
- `limit_time` (int): The daily playtime limit in minutes. `-1` if no limit is set.
- `today_playing_time` (int): The total playing time for the current day in minutes.
- `today_time_remaining` (int): The remaining playtime for the current day in minutes.
- `players` (dict): A dictionary of `Player` objects associated with the device, keyed by player ID.
- `applications` (dict): A dictionary of `Application` objects that have been played on the device.
- `timer_mode` (DeviceTimerMode): The current timer mode (`DAILY` or `EACH_DAY_OF_THE_WEEK`).
- `bedtime_alarm` (datetime.time): The time when the bedtime alarm will sound.
- `bedtime_end` (datetime.time): The time when the bedtime restrictions end. Set to `datetime.time(0, 0)` if disabled.
- `forced_termination_mode` (bool): `True` if the software will be suspended when the playtime limit is reached.
- `alarms_enabled` (bool): `True` if alarms are enabled.
- `last_sync` (float): The timestamp of the last sync with the device.

#### Methods

All methods are asynchronous.

- `update()`: Refreshes the device data from the Nintendo API.
- `add_device_callback(callback)`: Adds a callback that will be called when the device state changes.
- `remove_device_callback(callback)`: Removes a previously added callback.
- `set_new_pin(pin: str)`: Sets a new PIN for the parental controls.
- `add_extra_time(minutes: int)`: Adds extra playing time for the current day.
- `update_max_daily_playtime(minutes: int)`: Sets the daily playtime limit. Use `-1` to remove the limit.
- `set_restriction_mode(mode: RestrictionMode)`: Sets the restriction mode.
    - `RestrictionMode.FORCED_TERMINATION`: The software will be suspended when the playtime limit is reached.
    - `RestrictionMode.ALARM`: An alarm will be shown, but the software will not be suspended.
- `set_bedtime_alarm(value: datetime.time)`: Sets the bedtime alarm.
- `set_bedtime_end_time(value: datetime.time)`: Sets the time when bedtime restrictions end. Pass `datetime.time(0, 0)` to disable.
- `set_timer_mode(mode: DeviceTimerMode)`: Sets the timer mode.
    - `DeviceTimerMode.DAILY`: A single playtime limit for all days.
    - `DeviceTimerMode.EACH_DAY_OF_THE_WEEK`: Different playtime limits for each day of the week.
- `set_daily_restrictions(...)`: Sets the restrictions for a specific day of the week (when `timer_mode` is `EACH_DAY_OF_THE_WEEK`).
- `set_functional_restriction_level(level: FunctionalRestrictionLevel)`: Sets the content restriction level based on age ratings.
    - `FunctionalRestrictionLevel.CHILD`, `TEEN`, `YOUNG_ADULT`, `CUSTOM`.
- `get_monthly_summary(search_date: datetime = None)`: Gets the monthly summary for a given month.
- `get_date_summary(input_date: datetime = datetime.now())`: Gets the usage summary for a given date.
- `get_application(application_id: str)`: Gets an `Application` object by ID.
- `get_player(player_id: str)`: Gets a `Player` object by ID.

### The `Player` object

The `Player` object holds information about a single user on the Nintendo Switch. `Player` objects are accessed via the `players` dictionary on a `Device` object.

#### Properties

- `player_id` (str): The player's unique ID.
- `nickname` (str): The player's nickname.
- `player_image` (str): URL to the player's Mii image.
- `playing_time` (int): The player's total playing time for the current day in minutes.
- `apps` (list): A list of applications that the player has played today. Each entry is a dictionary containing details about the played application, including the `applicationId`.

### The `Application` object

The `Application` object contains information about a specific game or application on the Nintendo Switch. `Application` objects are accessed via the `applications` dictionary on a `Device` object.

#### Properties

- `application_id` (str): The application's unique ID.
- `name` (str): The name of the application.
- `image_url` (str): URL to the application's icon.
- `safe_launch_setting` (SafeLaunchSetting): The application's status on the console's Allow List. This allows an application to bypass general age/content restrictions. (`NONE`, `ALLOW`).
- `today_time_played` (int): The total time the application has been played today by all players in minutes.

#### Methods

All methods are asynchronous.

- `set_safe_launch_setting(safe_launch_setting: SafeLaunchSetting)`: Updates the application's status on the console's Allow List. This allows an application to bypass general age/content restrictions.
- `add_application_callback(callback)`: Adds a callback that will be called when the application's state changes.
- `remove_application_callback(callback)`: Removes a previously added callback.

### Full Example

This example demonstrates how to log in, list devices, and view player and application information.

```python
import asyncio
import aiohttp

from pynintendoparental import NintendoParental
from pynintendoparental.authenticator import Authenticator
from pynintendoparental.enum import RestrictionMode

async def main():
    """The main function."""
    session_token = "YOUR_SESSION_TOKEN"

    async with aiohttp.ClientSession() as session:
        auth = Authenticator(session_token, session)
        await auth.async_complete_login(use_session_token=True)
        nintendo = await NintendoParental.create(auth)

        # Get the first device
        device = list(nintendo.devices.values())[0]
        print(f"Device: {device.name}")

        # Change the restriction mode to suspend the software when playtime is up
        await device.set_restriction_mode(RestrictionMode.FORCED_TERMINATION)
        print("Restriction mode set to forced termination.")

        # Print today's summary for each player
        for player in device.players.values():
            print(f"Player: {player.nickname}")
            print(f"  Playing time: {player.playing_time} minutes")
            
            # Print applications played by the player
            for app in player.apps:
                app_id = app['applicationId']
                # Get the application object from the device
                application = device.get_application(app_id)
                print(f"  - Played {application.name} for {app['playingTime']} minutes")

if __name__ == "__main__":
    asyncio.run(main())

```
