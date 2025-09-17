import time
import unittest
from threading import Lock

from minibone.daemon import Daemon


class DaemonSubClass(Daemon):
    """Test subclass of Daemon that increments a counter."""

    value = 0

    def __init__(self):
        super().__init__(
            name="TestDaemon",
            interval=0.1,  # Faster for testing
            iter=3,
            sleep=0.01,  # Minimal sleep
        )

    def on_process(self) -> None:
        """Increment counter in a thread-safe way."""
        with self.lock:
            self.value += 1


class TestDaemon(unittest.TestCase):
    """Test cases for Daemon class."""

    lock = Lock()
    value = 0

    def setUp(self) -> None:
        """Reset counter before each test."""
        self.value = 0

    def callback(self) -> None:
        """Test callback that increments counter."""
        with self.lock:
            self.value += 1

    def test_basic_operation(self) -> None:
        """Test daemon runs callback specified number of times."""
        daemon = Daemon(
            name="TestDaemon",
            interval=0.1,  # Faster for testing
            iter=3,
            callback=self.callback,
            sleep=0.01,  # Minimal sleep
        )
        daemon.start()
        time.sleep(1)  # Should be enough time for 3 iterations
        daemon.stop()
        self.assertEqual(self.value, 3)

    def test_subclass_operation(self) -> None:
        """Test daemon subclass runs on_process correctly."""
        daemon = DaemonSubClass()
        daemon.start()
        time.sleep(1)  # Should be enough time for 3 iterations
        daemon.stop()
        self.assertEqual(daemon.value, 3)

    def test_stop_behavior(self) -> None:
        """Test daemon stops cleanly."""
        daemon = Daemon(name="TestStop", interval=0.1, callback=self.callback)
        daemon.start()
        time.sleep(0.15)  # Let it run at least once
        daemon.stop()
        initial_value = self.value
        time.sleep(0.3)  # Verify it doesn't run after stop
        self.assertEqual(self.value, initial_value)

    def test_error_handling(self) -> None:
        """Test daemon handles callback errors."""

        def faulty_callback():
            raise ValueError("Test error")

        daemon = Daemon(name="TestError", interval=0.1, callback=faulty_callback, iter=1)
        daemon.start()
        time.sleep(0.2)
        daemon.stop()  # Should not crash


if __name__ == "__main__":
    unittest.main()
