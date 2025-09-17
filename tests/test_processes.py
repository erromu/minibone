import time
import unittest
import uuid

from minibone.processes import PARProcesses


def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


def fail(x: int) -> None:
    """Operation that always fails for testing."""
    raise ValueError(f"{x} fail!")


def sleep_add(x: int, y: int, seconds: float) -> int:
    """Add two numbers after a delay."""
    time.sleep(seconds)
    return x + y


class TestPARProcesses(unittest.IsolatedAsyncioTestCase):
    """Test cases for PARProcesses parallel process manager."""

    async def test_async_result_and_shutdown(self) -> None:
        """Test async result retrieval and shutdown."""
        mgr = PARProcesses()
        tid = mgr.submit(add, 2, 3)
        result = await mgr.aresult(tid)
        self.assertEqual(result, 5)
        await mgr.ashutdown()

    def test_sync_result_and_shutdown(self) -> None:
        """Test synchronous result retrieval and shutdown."""
        mgr = PARProcesses()
        tid = mgr.submit(add, 10, 20)
        result = mgr.result(tid)
        self.assertEqual(result, 30)
        mgr.shutdown()

    def test_exception_handling(self) -> None:
        """Test exception propagation from worker processes."""
        mgr = PARProcesses()
        tid = mgr.submit(fail, 1)
        with self.assertRaises(ValueError):
            mgr.result(tid)
        mgr.shutdown()

    async def test_await_all_and_cleanup(self) -> None:
        """Test await_all() with multiple concurrent operations."""
        mgr = PARProcesses()
        tids: list[str] = [mgr.submit(add, i, i) for i in range(5)]
        results = await mgr.await_all()
        for i in range(5):
            self.assertEqual(results[tids[i]], i + i)
        await mgr.ashutdown()

    def test_wait_all_and_cleanup(self) -> None:
        """Test wait_all() with multiple operations."""
        mgr = PARProcesses()
        tids: list[str] = [mgr.submit(add, i, i) for i in range(3)]
        results = mgr.wait_all()
        for i in range(3):
            self.assertEqual(results[tids[i]], i + i)
        mgr.shutdown()

    def test_cleanup(self) -> None:
        """Test cleanup functionality."""
        mgr = PARProcesses()
        tid = mgr.submit(add, 1, 2)
        mgr.wait_all(cleanup=False)
        self.assertEqual(mgr.status(tid), "done")
        mgr.cleanup()
        self.assertEqual(mgr.status(tid), "unknown")
        mgr.shutdown()

    def test_status_states(self) -> None:
        """Test various task status states."""
        mgr = PARProcesses()
        tid1 = mgr.submit(sleep_add, 1, 2, 0.1)
        status1 = mgr.status(tid1)
        self.assertIn(status1, ["pending", "running"])
        mgr.wait_all(cleanup=False)
        self.assertEqual(mgr.status(tid1), "done")

        tid2 = mgr.submit(fail, 1)
        mgr.wait_all(cleanup=False)
        self.assertEqual(mgr.status(tid2), "exception")
        mgr.shutdown()

    async def test_aresult_error_cases(self) -> None:
        """Test error cases for aresult()."""
        mgr = PARProcesses()

        # Test KeyError for invalid task ID
        invalid_tid = str(uuid.uuid4())
        with self.assertRaises(KeyError):
            await mgr.aresult(invalid_tid)

        # Test exception propagation
        tid = mgr.submit(fail, 2)
        with self.assertRaises(ValueError):
            await mgr.aresult(tid)

        await mgr.ashutdown()

    async def test_ashutdown(self) -> None:
        """Test async shutdown behavior."""
        mgr = PARProcesses()
        tid = mgr.submit(add, 2, 3)  # noqa: F841

        # Shutdown without waiting
        await mgr.ashutdown(wait=False)

        # Verify we can't submit new tasks
        with self.assertRaises(RuntimeError):
            mgr.submit(add, 4, 5)

        # Verify shutdown state
        self.assertTrue(mgr._shutdown)


if __name__ == "__main__":
    unittest.main()
