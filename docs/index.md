# Python Nintendo Parental Controls

A simple, Python API to connect to Nintendo Switch Parental Controls.

[![Test Status](https://github.com/pantherale0/pynintendoparental/actions/workflows/test.yml/badge.svg)](https://github.com/pantherale0/pynintendoparental/actions/workflows/test.yml)
[![Coverage Status](https://codecov.io/gh/pantherale0/pynintendoparental/branch/main/graph/badge.svg?token=SO6VDF7951)](https://codecov.io/gh/pantherale0/pynintendoparental)
[![PyPi](https://img.shields.io/pypi/v/pynintendoparental)](https://pypi.org/project/pynintendoparental)
[![Licence](https://img.shields.io/github/license/pantherale0/pynintendoparental)](https://github.com/pantherale0/pynintendoparental/blob/main/LICENSE)

## Home Assistant Integration

This library powers the Nintendo Parental Controls integration for Home Assistant:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=nintendo_parental_controls)

## Overview

`pynintendoparental` is a Python library that provides an asynchronous API client for interacting with Nintendo Switch Parental Controls. It allows you to:

- Authenticate with Nintendo's servers
- Retrieve and manage device information
- Monitor and control playtime limits
- Set bedtime alarms and restrictions
- View player statistics and application usage
- Configure parental control settings

## Features

- **Async/Await Support**: Built with asyncio for efficient asynchronous operations
- **Complete API Coverage**: Access all major Nintendo Parental Controls features
- **Type Hints**: Full type hint support for better IDE integration
- **Easy Authentication**: Support for both session token and interactive login methods
- **Device Management**: Control multiple Nintendo Switch devices from a single account
- **Real-time Updates**: Monitor device status and player activity

## Quick Start

### Installation

```bash
pip install pynintendoparental
```

### Basic Example

```python
import asyncio
import aiohttp

from pynintendoparental import NintendoParental
from pynintendoparental.authenticator import Authenticator

async def main():
    """Simple example showing basic usage."""
    session_token = "YOUR_SESSION_TOKEN"

    async with aiohttp.ClientSession() as session:
        auth = Authenticator(session_token, session)
        await auth.async_complete_login(use_session_token=True)
        nintendo = await NintendoParental.create(auth)

        # Iterate through all devices
        for device in nintendo.devices.values():
            print(f"Device: {device.name}")
            print(f"  Today's playing time: {device.today_playing_time} minutes")
            print(f"  Time remaining: {device.today_time_remaining} minutes")

if __name__ == "__main__":
    asyncio.run(main())
```

## Documentation Sections

- **[Getting Started](guide/getting-started.md)**: Installation and setup instructions
- **[Authentication](guide/authentication.md)**: How to authenticate with Nintendo's servers
- **[Usage Examples](guide/examples.md)**: Comprehensive usage examples and recipes
- **[API Reference](api/nintendoparental.md)**: Detailed API documentation

## Requirements

- Python 3.8 or higher
- aiohttp for async HTTP requests
- pynintendoauth for Nintendo authentication

## Support

If you find this library helpful, consider supporting the developer:

<a href="https://www.buymeacoffee.com/pantherale0" target="_blank" title="buymeacoffee">
  <img src="https://iili.io/JoQ1MeS.md.png" alt="buymeacoffee-yellow-badge" style="width: 104px;">
</a>

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/pantherale0/pynintendoparental/blob/main/LICENSE) file for details.
