# Authentication

This library requires authentication with Nintendo's servers. The `Authenticator` class handles this process. There are two ways to authenticate:

## Method 1: Using a Session Token

If you already have a `session_token`, you can pass it to the `Authenticator`. This is the recommended method for production use as it's faster and doesn't require user interaction.

```python
import aiohttp
from pynintendoparental.authenticator import Authenticator

async with aiohttp.ClientSession() as session:
    session_token = "YOUR_SESSION_TOKEN"
    auth = Authenticator(session_token, session)
    await auth.async_complete_login(use_session_token=True)
```

### Obtaining a Session Token

Session tokens can be obtained through the interactive login method (see below) or by using external tools that extract the token from the Nintendo mobile app.

!!! warning "Token Security"
    Session tokens are sensitive credentials that grant access to your Nintendo Account. Keep them secure and never share them publicly.

## Method 2: Interactive Login

If you don't have a `session_token`, you can perform an interactive login to obtain one. This method requires user interaction but only needs to be done once.

The library will provide a login URL. You need to:

1. Open this URL in your browser
2. Log in to your Nintendo Account
3. Copy the URL you're redirected to (the "Select this person" button URL)
4. Paste it back into your application

Here's a complete example:

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
    # Save the session token for future use
    session_token = auth.session_token
    # You can now use the 'auth' object with NintendoParental

if __name__ == "__main__":
    asyncio.run(main())
```

### Storing the Session Token

Once you've obtained a session token, you should store it securely for future use. Here's an example of saving it to a file:

```python
import json
import os

def save_session_token(token: str, filename: str = "nintendo_session.json"):
    """Save session token to a file."""
    with open(filename, 'w') as f:
        json.dump({'session_token': token}, f)

def load_session_token(filename: str = "nintendo_session.json") -> str:
    """Load session token from a file."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return data.get('session_token')
    return None

# Usage example
async def main():
    session_token = load_session_token()
    
    if not session_token:
        # Perform interactive login
        auth = await interactive_login()
        save_session_token(auth.session_token)
    else:
        # Use stored token
        async with aiohttp.ClientSession() as session:
            auth = Authenticator(session_token, session)
            await auth.async_complete_login(use_session_token=True)
```

!!! tip "Environment Variables"
    For production applications, consider storing the session token in environment variables or a secure secrets manager rather than in a file.

## Token Expiration and Refresh

Session tokens can expire over time. The `Authenticator` class handles token refresh automatically when making API requests. If a token is expired, it will attempt to refresh it using the refresh token obtained during login.

If you encounter authentication errors:

1. **Check token validity**: Ensure your session token hasn't been revoked
2. **Re-authenticate**: Perform the interactive login process again to obtain a new token
3. **Update stored token**: Replace your stored token with the new one

## Complete Authentication Example

Here's a complete example that combines both methods with error handling:

```python
import asyncio
import aiohttp
from pynintendoparental import NintendoParental
from pynintendoparental.authenticator import Authenticator
from pynintendoauth.exceptions import HttpException

async def authenticate():
    """Authenticate with Nintendo servers."""
    session_token = load_session_token()
    
    async with aiohttp.ClientSession() as session:
        if session_token:
            # Try using stored token
            try:
                auth = Authenticator(session_token, session)
                await auth.async_complete_login(use_session_token=True)
                print("Authenticated using stored token")
                return auth
            except HttpException as e:
                print(f"Stored token is invalid: {e}")
                print("Performing interactive login...")
        
        # Perform interactive login
        auth = Authenticator(client_session=session)
        print("Please open the following URL in your browser:")
        print(auth.login_url)
        
        response_url = input("Please paste the URL you were redirected to: ")
        await auth.async_complete_login(response_url)
        
        # Save the new token
        save_session_token(auth.session_token)
        print("Login successful! Token saved.")
        return auth

async def main():
    auth = await authenticate()
    nintendo = await NintendoParental.create(auth)
    
    # Now you can use the nintendo object
    for device in nintendo.devices.values():
        print(f"Device: {device.name}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Security Best Practices

1. **Never commit tokens**: Add files containing session tokens to `.gitignore`
2. **Use environment variables**: Store tokens in environment variables or secret managers
3. **Restrict file permissions**: If storing tokens in files, ensure they have restrictive permissions (e.g., `chmod 600` on Unix-like systems)
4. **Rotate tokens regularly**: Consider refreshing your session token periodically
5. **Handle errors gracefully**: Always wrap authentication code in try-except blocks

## Next Steps

- Learn more about [Usage Examples](examples.md)
- Read the [Authenticator API Reference](../api/authenticator.md)
- Explore the [NintendoParental API](../api/nintendoparental.md)
