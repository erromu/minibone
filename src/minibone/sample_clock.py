"""Sample clock implementation by subclassing Daemon.

Demonstrates how to create a periodic task by subclassing the Daemon class.

Features:
- Runs every second to print current time
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


class Clock(Daemon):
    """Daemon subclass that prints current time periodically."""

    def __init__(self):
        """Initialize clock with 1 second interval."""
        super().__init__(name="ClockSubclass", interval=1, sleep=0.01)

    def on_process(self) -> None:
        """Print current timestamp on each interval."""
        logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def main() -> NoReturn:
    """Run the clock demo with Daemon subclass."""
    try:
        logger.info("Starting clock using Daemon subclass")
        logger.info("Press Ctrl+C to exit")

        clock = Clock()
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
