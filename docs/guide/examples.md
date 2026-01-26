# Usage Examples

This guide provides comprehensive examples of common tasks using `pynintendoparental`.

## Basic Device Information

Get information about all devices linked to your Nintendo account:

```python
import asyncio
import aiohttp
from pynintendoparental import NintendoParental
from pynintendoparental.authenticator import Authenticator

async def list_devices():
    """List all devices and their information."""
    session_token = "YOUR_SESSION_TOKEN"
    
    async with aiohttp.ClientSession() as session:
        auth = Authenticator(session_token, session)
        await auth.async_complete_login(use_session_token=True)
        nintendo = await NintendoParental.create(auth)
        
        for device in nintendo.devices.values():
            print(f"\nDevice: {device.name}")
            print(f"  ID: {device.device_id}")
            print(f"  Model: {device.model}")
            print(f"  Daily limit: {device.limit_time} minutes")
            print(f"  Today's playtime: {device.today_playing_time} minutes")
            print(f"  Time remaining: {device.today_time_remaining} minutes")
            print(f"  Last sync: {device.last_sync}")

asyncio.run(list_devices())
```

## Managing Playtime Limits

### Set Daily Playtime Limit

```python
async def set_playtime_limit(device, minutes: int):
    """Set daily playtime limit in minutes."""
    await device.update_max_daily_playtime(minutes)
    print(f"Set playtime limit to {minutes} minutes")

# Usage
device = list(nintendo.devices.values())[0]
await set_playtime_limit(device, 180)  # 3 hours
```

### Remove Playtime Limit

```python
async def remove_playtime_limit(device):
    """Remove daily playtime limit."""
    await device.update_max_daily_playtime(-1)
    print("Playtime limit removed")

# Usage
await remove_playtime_limit(device)
```

### Add Extra Time

```python
async def add_extra_time(device, minutes: int):
    """Add extra playing time for today."""
    await device.add_extra_time(minutes)
    print(f"Added {minutes} minutes of extra time")

# Usage
await add_extra_time(device, 30)  # Add 30 minutes
```

## Bedtime Settings

### Set Bedtime Alarm

```python
from datetime import time

async def set_bedtime_alarm(device, alarm_time: time):
    """Set bedtime alarm."""
    await device.set_bedtime_alarm(alarm_time)
    print(f"Bedtime alarm set to {alarm_time}")

# Usage
await set_bedtime_alarm(device, time(21, 0))  # 9:00 PM
```

### Configure Bedtime Restrictions

```python
from datetime import time

async def configure_bedtime(device, start_time: time, end_time: time):
    """Configure bedtime start and end times."""
    await device.set_bedtime_alarm(start_time)
    await device.set_bedtime_end_time(end_time)
    print(f"Bedtime configured: {start_time} to {end_time}")

# Usage
await configure_bedtime(
    device,
    time(21, 0),   # 9:00 PM start
    time(7, 0)     # 7:00 AM end
)
```

### Disable Bedtime

```python
from datetime import time

async def disable_bedtime(device):
    """Disable bedtime restrictions."""
    await device.set_bedtime_end_time(time(0, 0))
    print("Bedtime restrictions disabled")

# Usage
await disable_bedtime(device)
```

## Restriction Modes

### Set Forced Termination Mode

```python
from pynintendoparental.enum import RestrictionMode

async def set_forced_termination(device):
    """Enable forced termination when playtime limit is reached."""
    await device.set_restriction_mode(RestrictionMode.FORCED_TERMINATION)
    print("Forced termination enabled")

# Usage
await set_forced_termination(device)
```

### Set Alarm Mode

```python
from pynintendoparental.enum import RestrictionMode

async def set_alarm_mode(device):
    """Enable alarm mode (no forced termination)."""
    await device.set_restriction_mode(RestrictionMode.ALARM)
    print("Alarm mode enabled (no forced termination)")

# Usage
await set_alarm_mode(device)
```

## Timer Modes

### Set Daily Timer Mode

```python
from pynintendoparental.enum import DeviceTimerMode

async def set_daily_timer(device):
    """Set a single playtime limit for all days."""
    await device.set_timer_mode(DeviceTimerMode.DAILY)
    print("Timer mode set to DAILY")

# Usage
await set_daily_timer(device)
```

### Set Weekly Timer Mode

```python
from pynintendoparental.enum import DeviceTimerMode

async def set_weekly_timer(device):
    """Set different playtime limits for each day of the week."""
    await device.set_timer_mode(DeviceTimerMode.EACH_DAY_OF_THE_WEEK)
    print("Timer mode set to EACH_DAY_OF_THE_WEEK")

# Usage
await set_weekly_timer(device)
```

### Configure Day-Specific Restrictions

```python
from datetime import time

async def set_weekday_restrictions(device):
    """Set different restrictions for a specific day."""
    # Example: Monday restrictions
    await device.set_daily_restrictions(
        day=0,  # 0=Monday, 1=Tuesday, etc.
        limit_time=120,  # 2 hours
        bedtime_alarm=time(21, 0),
        bedtime_end=time(7, 0)
    )
    print("Weekday restrictions configured")

# Usage
await set_weekday_restrictions(device)
```

## Player Information

### List All Players

```python
async def list_players(device):
    """List all players on a device."""
    for player in device.players.values():
        print(f"\nPlayer: {player.nickname}")
        print(f"  ID: {player.player_id}")
        print(f"  Today's playtime: {player.playing_time} minutes")
        print(f"  Profile image: {player.player_image}")

# Usage
await list_players(device)
```

### Get Player's Apps

```python
async def show_player_apps(device, player):
    """Show applications played by a specific player."""
    print(f"\nApplications played by {player.nickname}:")
    for app in player.apps:
        app_id = app['applicationId']
        application = device.get_application(app_id)
        print(f"  - {application.name}: {app['playingTime']} minutes")

# Usage
player = list(device.players.values())[0]
await show_player_apps(device, player)
```

## Application Management

### List All Applications

```python
async def list_applications(device):
    """List all applications on a device."""
    print("\nApplications:")
    for app in device.applications.values():
        print(f"  - {app.name}")
        print(f"    ID: {app.application_id}")
        print(f"    Today's playtime: {app.today_time_played} minutes")
        print(f"    Safe launch: {app.safe_launch_setting}")

# Usage
await list_applications(device)
```

### Allow an Application

```python
from pynintendoparental.enum import SafeLaunchSetting

async def allow_application(application):
    """Add application to Allow List (bypasses age restrictions)."""
    await application.set_safe_launch_setting(SafeLaunchSetting.ALLOW)
    print(f"{application.name} added to Allow List")

# Usage
app = list(device.applications.values())[0]
await allow_application(app)
```

### Remove Application from Allow List

```python
from pynintendoparental.enum import SafeLaunchSetting

async def remove_from_allow_list(application):
    """Remove application from Allow List."""
    await application.set_safe_launch_setting(SafeLaunchSetting.NONE)
    print(f"{application.name} removed from Allow List")

# Usage
await remove_from_allow_list(app)
```

## Content Restrictions

### Set Age Restriction Level

```python
from pynintendoparental.enum import FunctionalRestrictionLevel

async def set_age_restrictions(device, level: FunctionalRestrictionLevel):
    """Set content restriction level."""
    await device.set_functional_restriction_level(level)
    print(f"Restriction level set to {level}")

# Usage examples
await set_age_restrictions(device, FunctionalRestrictionLevel.CHILD)
await set_age_restrictions(device, FunctionalRestrictionLevel.TEEN)
await set_age_restrictions(device, FunctionalRestrictionLevel.YOUNG_ADULT)
await set_age_restrictions(device, FunctionalRestrictionLevel.CUSTOM)
```

## Usage Reports

### Get Monthly Summary

```python
from datetime import datetime

async def get_monthly_summary(device, year: int = None, month: int = None):
    """Get monthly usage summary."""
    if year and month:
        search_date = datetime(year, month, 1)
    else:
        search_date = datetime.now()
    
    summary = await device.get_monthly_summary(search_date)
    print(f"\nMonthly summary for {search_date.strftime('%B %Y')}:")
    print(summary)

# Usage
await get_monthly_summary(device, 2024, 1)  # January 2024
```

### Get Daily Summary

```python
from datetime import datetime, timedelta

async def get_daily_summary(device, date: datetime = None):
    """Get usage summary for a specific date."""
    if date is None:
        date = datetime.now()
    
    summary = await device.get_date_summary(date)
    print(f"\nDaily summary for {date.strftime('%Y-%m-%d')}:")
    print(summary)

# Usage
await get_daily_summary(device)  # Today
await get_daily_summary(device, datetime.now() - timedelta(days=1))  # Yesterday
```

## Callbacks and Real-time Updates

### Device State Change Callbacks

```python
async def on_device_update(device):
    """Callback for device state changes."""
    print(f"Device {device.name} was updated")
    print(f"  Playing time: {device.today_playing_time} minutes")

# Add callback
device.add_device_callback(on_device_update)

# Update device to trigger callback
await device.update()

# Remove callback when done
device.remove_device_callback(on_device_update)
```

### Application State Change Callbacks

```python
async def on_app_update(application):
    """Callback for application state changes."""
    print(f"Application {application.name} was updated")
    print(f"  Playtime today: {application.today_time_played} minutes")

# Add callback
app = list(device.applications.values())[0]
app.add_application_callback(on_app_update)

# Changes to the app will trigger the callback
await app.set_safe_launch_setting(SafeLaunchSetting.ALLOW)

# Remove callback when done
app.remove_application_callback(on_app_update)
```

## PIN Management

### Set a New PIN

```python
async def change_pin(device, new_pin: str):
    """Change the parental controls PIN."""
    await device.set_new_pin(new_pin)
    print("PIN updated successfully")

# Usage
await change_pin(device, "1234")
```

!!! warning "PIN Security"
    Always use a secure PIN and keep it confidential. Never hardcode PINs in your source code.

## Complete Example

Here's a comprehensive example that combines multiple features:

```python
import asyncio
import aiohttp
from datetime import time
from pynintendoparental import NintendoParental
from pynintendoparental.authenticator import Authenticator
from pynintendoparental.enum import RestrictionMode, DeviceTimerMode

async def main():
    """Complete example demonstrating multiple features."""
    session_token = "YOUR_SESSION_TOKEN"
    
    async with aiohttp.ClientSession() as session:
        # Authenticate
        auth = Authenticator(session_token, session)
        await auth.async_complete_login(use_session_token=True)
        nintendo = await NintendoParental.create(auth)
        
        # Get the first device
        device = list(nintendo.devices.values())[0]
        print(f"Managing device: {device.name}")
        
        # Set daily playtime limit to 3 hours
        await device.update_max_daily_playtime(180)
        
        # Configure bedtime from 9 PM to 7 AM
        await device.set_bedtime_alarm(time(21, 0))
        await device.set_bedtime_end_time(time(7, 0))
        
        # Enable forced termination
        await device.set_restriction_mode(RestrictionMode.FORCED_TERMINATION)
        
        # List all players and their playtime
        print("\nPlayers:")
        for player in device.players.values():
            print(f"  {player.nickname}: {player.playing_time} minutes today")
        
        # List all applications
        print("\nApplications:")
        for app in device.applications.values():
            print(f"  {app.name}: {app.today_time_played} minutes today")
        
        print("\nConfiguration complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

## Next Steps

- Explore the [API Reference](../api/nintendoparental.md) for detailed documentation
- Check the [Device API](../api/device.md) for all available device methods
- Learn about [Enums](../api/enums.md) for configuration options
