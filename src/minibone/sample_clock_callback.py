"""Sample clock implementation using Daemon callback mode.

Demonstrates how to use the Daemon class with a callback function to run
a periodic task in the background while the main thread continues working.

Features:
- Runs callback every second to print current time
- Main thread continues executing other work
- Clean shutdown on keyboard interrupt
"""

import logging
import time
from datetime import datetime
from typing import NoReturn

from minibone.daemon import Daemon


# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def callback() -> None:
    """Callback function that prints current timestamp."""
    logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def main() -> NoReturn:
    """Run the clock demo with background callback."""
    try:
        logger.info("Starting clock with Daemon callback")
        logger.info("Press Ctrl+C to exit")

        clock = Daemon(name="ClockCallback", interval=1, sleep=0.01, callback=callback)
        clock.start()

        while True:
            logger.info("Main thread going to sleep")
            sleep_seconds = 15
            time.sleep(sleep_seconds)
            logger.info("Main thread awake after %d seconds", sleep_seconds)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
    finally:
        clock.stop()
        logger.info("Clock stopped")


if __name__ == "__main__":
    main()
