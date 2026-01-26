# Getting Started

This guide will help you get started with `pynintendoparental`.

## Installation

You can install `pynintendoparental` from PyPI using pip:

```bash
pip install pynintendoparental
```

For local development, you can clone the repository and install it with development dependencies:

```bash
git clone https://github.com/pantherale0/pynintendoparental.git
cd pynintendoparental
just install
```

## Prerequisites

Before using `pynintendoparental`, you'll need:

1. **Python 3.8 or higher**: The library requires Python 3.8 or newer.
2. **Nintendo Account**: You need a Nintendo Account with parental controls set up.
3. **Session Token or Login Credentials**: You'll need to authenticate with Nintendo's servers (see [Authentication](authentication.md)).

## System Requirements

The library has minimal dependencies:

- `pynintendoauth==1.0.2` - For Nintendo authentication
- Python standard library for most operations

For development, additional dependencies are required (see `setup.py` for the full list).

## First Steps

Once installed, you can start using the library. Here's a minimal example:

```python
import asyncio
import aiohttp

from pynintendoparental import NintendoParental
from pynintendoparental.authenticator import Authenticator

async def main():
    """Basic usage example."""
    session_token = "YOUR_SESSION_TOKEN"
    
    async with aiohttp.ClientSession() as session:
        # Create authenticator
        auth = Authenticator(session_token, session)
        await auth.async_complete_login(use_session_token=True)
        
        # Create NintendoParental instance
        nintendo = await NintendoParental.create(auth)
        
        # Access devices
        print(f"Found {len(nintendo.devices)} device(s)")
        for device in nintendo.devices.values():
            print(f"- {device.name}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration Options

When creating a `NintendoParental` instance, you can customize the timezone and language:

```python
nintendo = await NintendoParental.create(
    auth,
    timezone="Europe/London",  # Default
    lang="en-GB"               # Default
)
```

### Supported Timezones

Use any valid timezone identifier from the IANA Time Zone Database, for example:

- `"America/New_York"`
- `"Europe/London"`
- `"Asia/Tokyo"`
- `"Australia/Sydney"`

### Supported Languages

The language parameter should match Nintendo's supported language codes, for example:

- `"en-US"` - English (United States)
- `"en-GB"` - English (United Kingdom)
- `"ja-JP"` - Japanese
- `"de-DE"` - German
- `"fr-FR"` - French
- `"es-ES"` - Spanish
- `"it-IT"` - Italian

## Next Steps

- Learn about [Authentication](authentication.md) methods
- Explore [Usage Examples](examples.md) for common tasks
- Read the [API Reference](../api/nintendoparental.md) for detailed documentation

## Troubleshooting

### Common Issues

**Import Error**: If you get an import error, make sure you've installed the package correctly:
```bash
pip install pynintendoparental
```

**Authentication Error**: If authentication fails, verify your session token is valid. Session tokens can expire and need to be refreshed.

**No Devices Found**: If no devices are found, make sure:
- You have parental controls set up on your Nintendo Account
- You're using the correct account credentials
- Your Nintendo Switch is linked to your account

For more help, please open an issue on [GitHub](https://github.com/pantherale0/pynintendoparental/issues).
