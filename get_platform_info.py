import logging
import asyncio
from pynintendoparental import Authenticator, NintendoParental
from pynintendoparental.exceptions import InvalidSessionTokenException

_LOGGER = logging.getLogger(__name__)


async def main():
    """Running function"""
    login = True
    while login:
        try:
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

    for device in control.devices.values():
        _LOGGER.info("Discovered device %s, label %s", device.device_id, device.name)
        _LOGGER.info("Generation: %s", device.extra.get("platformGeneration", "Unknown"))
        _LOGGER.debug("Device Data: %s", device.extra)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
