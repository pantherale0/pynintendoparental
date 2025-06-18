
import os
import logging
import asyncio
from dotenv import load_dotenv
from pynintendoparental import Authenticator, NintendoParental
from pynintendoparental.exceptions import InvalidSessionTokenException

load_dotenv()

_LOGGER = logging.getLogger(__name__)

async def main():
    """Running function"""
    login = True
    while login:
        try:
            if bool(int(os.environ.get("USE_SESSION_TOKEN", 0))) or input("Should we use a session token? [N/y] ").upper() == "Y":
                auth = await Authenticator.complete_login(None, os.environ.get("SESSION_TOKEN") or input("Token: "), True)
            else:
                auth = Authenticator.generate_login()
                _LOGGER.info("Login using %s", auth.login_url)
                auth = await Authenticator.complete_login(auth, input("Response URL: "), False)
            _LOGGER.info("Logged in, ready.")
            _LOGGER.debug("Access token is: %s", auth.access_token)
            _LOGGER.debug("Session token is: %s", auth.get_session_token)
            control = await NintendoParental.create(auth)
            login = False
        except InvalidSessionTokenException as err:
            _LOGGER.error("Invalid session token provided: %s", err)
        except Exception as err:
            _LOGGER.critical(err)

    while True:
        for device in control.devices.values():
            _LOGGER.debug("Discovered device %s, label %s", device.device_id, device.name)
            _LOGGER.debug("Usage today %s", device.today_playing_time)
            _LOGGER.debug("Usage remaining %s", device.today_time_remaining)

        _LOGGER.debug("ping")
        await asyncio.sleep(15)
        _LOGGER.debug("pong")
        await control.update()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
