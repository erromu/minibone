"""Sample async clock implementation using AsyncDaemon callback mode.

Demonstrates how to use the AsyncDaemon class with a callback function to run
a periodic task in the background while the main async loop continues working.

Features:
- Runs callback every second to print current time
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


async def callback() -> None:
    """Async callback function that prints current timestamp."""
    logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


async def main() -> NoReturn:
    """Run the async clock demo with background callback."""
    clock = AsyncDaemon(name="AsyncClockCallback", interval=1, sleep=0.01, callback=callback)

    try:
        logger.info("Starting async clock with AsyncDaemon callback")
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
