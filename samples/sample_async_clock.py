"""Sample async clock implementation by subclassing AsyncDaemon.

Demonstrates how to create a periodic task by subclassing the AsyncDaemon class.

Features:
- Runs every second to print current time
- Main async loop continues executing other work
- Clean shutdown on keyboard interrupt
"""

import asyncio
import logging
from datetime import datetime
from typing import NoReturn

from minibone.async_daemon import AsyncDaemon


# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AsyncClock(AsyncDaemon):
    """AsyncDaemon subclass that prints current time periodically."""

    def __init__(self):
        """Initialize clock with 1 second interval."""
        super().__init__(name="AsyncClockSubclass", interval=1, sleep=0.01)

    async def on_process(self) -> None:
        """Print current timestamp on each interval."""
        logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


async def main() -> NoReturn:
    """Run the async clock demo with AsyncDaemon subclass."""
    clock = AsyncClock()

    try:
        logger.info("Starting async clock using AsyncDaemon subclass")
        logger.info("Press Ctrl+C to exit")

        await clock.start()

        while True:
            logger.info("Main async loop going to sleep")
            sleep_seconds = 15
            await asyncio.sleep(sleep_seconds)
            logger.info("Main async loop awake after %d seconds", sleep_seconds)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
    finally:
        await clock.stop()
        logger.info("Async clock stopped")


if __name__ == "__main__":
    asyncio.run(main())
