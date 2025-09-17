import tempfile
import time
import unittest
import uuid

from minibone.io_threads import IOThreads


def read_file(filename: str) -> str:
    """Read content from a file."""
    with open(filename) as f:
        return f.read()


def write_file(filename: str, content: str) -> str:
    """Write content to a file and return status message."""
    with open(filename, "w") as f:
        f.write(content)
    return f"Written {len(content)} characters to {filename}"


def fail_operation(x: int) -> None:
    """Operation that always fails for testing."""
    raise ValueError(f"{x} fail!")


def network_simulation(delay: float) -> str:
    """Simulate network operation with delay."""
    time.sleep(delay)
    return f"Network response after {delay} seconds"


class TestIOThreads(unittest.IsolatedAsyncioTestCase):
    """Test cases for IOThreads parallel I/O manager."""

    async def test_async_result_and_shutdown(self) -> None:
        """Test async result retrieval and shutdown."""
        mgr = IOThreads()

        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("Hello, World!")
            temp_filename = f.name

        tid = mgr.submit(read_file, temp_filename)
        result = await mgr.aresult(tid)
        self.assertEqual(result, "Hello, World!")
        await mgr.ashutdown()

    def test_sync_result_and_shutdown(self) -> None:
        """Test synchronous result retrieval and shutdown."""
        mgr = IOThreads()

        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("Test content")
            temp_filename = f.name

        tid = mgr.submit(read_file, temp_filename)
        result = mgr.result(tid)
        self.assertEqual(result, "Test content")
        mgr.shutdown()

    def test_exception_handling(self) -> None:
        """Test exception propagation from worker threads."""
        mgr = IOThreads()
        tid = mgr.submit(fail_operation, 1)
        with self.assertRaises(ValueError):
            mgr.result(tid)
        mgr.shutdown()

    async def test_await_all_and_cleanup(self) -> None:
        """Test await_all() with multiple concurrent operations."""
        mgr = IOThreads()

        # Create temporary files for testing
        temp_files: list[str] = []
        tids: list[str] = []
        file_contents: list[str] = []
        for i in range(5):
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
                content = f"Content {i}"
                f.write(content)
                temp_files.append(f.name)
                file_contents.append(content)

        # Submit read tasks after all files are closed
        for file_path in temp_files:
            tid = mgr.submit(read_file, file_path)
            tids.append(tid)

        results = await mgr.await_all()

        for i in range(len(tids)):
            self.assertEqual(results[tids[i]], file_contents[i])
        await mgr.ashutdown()

    def test_wait_all_and_cleanup(self) -> None:
        """Test wait_all() with multiple operations."""
        mgr = IOThreads()

        # Create temporary files for testing
        temp_files: list[str] = []
        tids: list[str] = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
                f.write(f"Data {i}")
                # Sleep to ensure file is properly saved
                time.sleep(0.1)
                temp_files.append(f.name)
                tid = mgr.submit(read_file, f.name)
                tids.append(tid)

        results = mgr.wait_all()
        for i in range(3):
            self.assertEqual(results[tids[i]], f"Data {i}")
        mgr.shutdown()

    def test_cleanup(self) -> None:
        """Test cleanup functionality."""
        mgr = IOThreads()

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("Test")
            temp_filename = f.name

        tid = mgr.submit(read_file, temp_filename)
        mgr.wait_all(cleanup=False)
        self.assertEqual(mgr.status(tid), "done")
        mgr.cleanup()
        self.assertEqual(mgr.status(tid), "unknown")
        mgr.shutdown()

    def test_status_states(self) -> None:
        """Test various task status states."""
        mgr = IOThreads()
        tid1 = mgr.submit(network_simulation, 0.1)
        status1 = mgr.status(tid1)
        self.assertIn(status1, ["pending", "running"])
        mgr.wait_all(cleanup=False)
        self.assertEqual(mgr.status(tid1), "done")

        tid2 = mgr.submit(fail_operation, 1)
        mgr.wait_all(cleanup=False)
        self.assertEqual(mgr.status(tid2), "exception")
        mgr.shutdown()

    async def test_aresult_error_cases(self) -> None:
        """Test error cases for aresult()."""
        mgr = IOThreads()

        # Test KeyError for invalid task ID
        invalid_tid = str(uuid.uuid4())
        with self.assertRaises(KeyError):
            await mgr.aresult(invalid_tid)

        # Test exception propagation
        tid = mgr.submit(fail_operation, 2)
        with self.assertRaises(ValueError):
            await mgr.aresult(tid)

        await mgr.ashutdown()

    async def test_ashutdown(self) -> None:
        """Test async shutdown behavior."""
        mgr = IOThreads()

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("Test")
            temp_filename = f.name

        tid = mgr.submit(read_file, temp_filename)  # noqa: F841

        # Shutdown without waiting
        await mgr.ashutdown(wait=False)

        # Verify we can't submit new tasks
        with self.assertRaises(RuntimeError):
            mgr.submit(read_file, temp_filename)

        # Verify shutdown state
        self.assertTrue(mgr._shutdown)

    def test_write_operation(self) -> None:
        """Test write file operation."""
        mgr = IOThreads()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_filename = f.name

        content = "This is test content for writing"
        tid = mgr.submit(write_file, temp_filename, content)
        result = mgr.result(tid)
        self.assertEqual(result, f"Written {len(content)} characters to {temp_filename}")

        # Verify the content was actually written
        with open(temp_filename) as f:
            written_content = f.read()
        self.assertEqual(written_content, content)

        mgr.shutdown()


if __name__ == "__main__":
    unittest.main()
