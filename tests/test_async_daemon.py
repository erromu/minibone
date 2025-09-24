import asyncio
import unittest

from minibone.async_daemon import AsyncDaemon


class AsyncDaemonSubClass(AsyncDaemon):
    """Test subclass of AsyncDaemon that increments a counter."""

    def __init__(self):
        super().__init__(
            name="TestAsyncDaemon",
            interval=0.1,  # Faster for testing
            iter=3,
            sleep=0.01,  # Minimal sleep
        )
        self.value = 0

    async def on_process(self) -> None:
        """Increment counter in an async-safe way."""
        async with self.lock:
            self.value += 1


class TestAsyncDaemon(unittest.IsolatedAsyncioTestCase):
    """Test cases for AsyncDaemon class."""

    def setUp(self) -> None:
        """Reset counter before each test."""
        self.value = 0

    async def callback(self) -> None:
        """Test async callback that increments counter."""
        self.value += 1

    async def test_basic_operation(self) -> None:
        """Test async daemon runs callback specified number of times."""
        daemon = AsyncDaemon(
            name="TestAsyncDaemon",
            interval=0.1,  # Faster for testing
            iter=3,
            callback=self.callback,
            sleep=0.01,  # Minimal sleep
        )
        await daemon.start()
        await asyncio.sleep(1)  # Should be enough time for 3 iterations
        await daemon.stop()
        self.assertEqual(self.value, 3)

    async def test_subclass_operation(self) -> None:
        """Test async daemon subclass runs on_process correctly."""
        daemon = AsyncDaemonSubClass()
        await daemon.start()
        await asyncio.sleep(1)  # Should be enough time for 3 iterations
        await daemon.stop()
        self.assertEqual(daemon.value, 3)

    async def test_stop_behavior(self) -> None:
        """Test async daemon stops cleanly."""
        daemon = AsyncDaemon(name="TestStop", interval=0.1, callback=self.callback)
        await daemon.start()
        await asyncio.sleep(0.15)  # Let it run at least once
        await daemon.stop()
        initial_value = self.value
        await asyncio.sleep(0.3)  # Verify it doesn't run after stop
        self.assertEqual(self.value, initial_value)

    async def test_error_handling(self) -> None:
        """Test async daemon handles callback errors."""

        async def faulty_callback():
            raise ValueError("Test error")

        daemon = AsyncDaemon(name="TestError", interval=0.1, callback=faulty_callback, iter=1)
        await daemon.start()
        await asyncio.sleep(0.2)
        await daemon.stop()  # Should not crash

    async def test_is_running(self) -> None:
        """Test is_running method."""
        daemon = AsyncDaemon(name="TestRunning", interval=0.1, callback=self.callback, iter=1)
        self.assertFalse(daemon.is_running())
        await daemon.start()
        self.assertTrue(daemon.is_running())
        await asyncio.sleep(0.2)
        await daemon.stop()
        self.assertFalse(daemon.is_running())

    async def test_double_start_raises_error(self) -> None:
        """Test that starting twice raises RuntimeError."""
        daemon = AsyncDaemon(name="TestDoubleStart", interval=0.1, callback=self.callback)
        await daemon.start()
        with self.assertRaises(RuntimeError):
            await daemon.start()
        await daemon.stop()


if __name__ == "__main__":
    unittest.main()
