import time
import unittest
import uuid

from minibone.processes import PARProcesses


def add(x, y):
    return x + y


def fail(x):
    raise ValueError(f"{x} fail!")


def sleep_add(x, y, seconds):
    time.sleep(seconds)
    return x + y


class TestPARProcesses(unittest.IsolatedAsyncioTestCase):
    async def test_async_result_and_shutdown(self):
        mgr = PARProcesses()
        tid = mgr.submit(add, 2, 3)
        result = await mgr.aresult(tid)
        self.assertEqual(result, 5)
        await mgr.ashutdown()

    def test_sync_result_and_shutdown(self):
        mgr = PARProcesses()
        tid = mgr.submit(add, 10, 20)
        result = mgr.result(tid)
        self.assertEqual(result, 30)
        mgr.shutdown()

    def test_exception_handling(self):
        mgr = PARProcesses()
        tid = mgr.submit(fail, 1)
        with self.assertRaises(ValueError):
            mgr.result(tid)
        mgr.shutdown()

    async def test_await_all_and_cleanup(self):
        mgr = PARProcesses()
        tids = [mgr.submit(add, i, i) for i in range(5)]
        results = await mgr.await_all()
        for i in range(5):
            self.assertEqual(results[tids[i]], i + i)
        await mgr.ashutdown()

    def test_wait_all_and_cleanup(self):
        mgr = PARProcesses()
        tids = [mgr.submit(add, i, i) for i in range(3)]
        results = mgr.wait_all()
        for i in range(3):
            self.assertEqual(results[tids[i]], i + i)
        mgr.shutdown()

    def test_cleanup(self):
        mgr = PARProcesses()
        tid = mgr.submit(add, 1, 2)
        mgr.wait_all(cleanup=False)
        self.assertEqual(mgr.status(tid), "done")
        mgr.cleanup()
        self.assertEqual(mgr.status(tid), "unknown")
        mgr.shutdown()

    def test_status_states(self):
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

    async def test_aresult_error_cases(self):
        mgr = PARProcesses()

        # Test KeyError for invalid task ID
        invalid_tid = str(uuid.uuid4())
        with self.assertRaises(KeyError):
            await mgr.aresult(invalid_tid)

        # Test TimeoutError
        tid = mgr.submit(sleep_add, 1, 2, 0.15)
        with self.assertRaises(TimeoutError):
            await mgr.aresult(tid, timeout=0.1)

        # Test exception propagation
        tid = mgr.submit(fail, 2)
        with self.assertRaises(ValueError):
            await mgr.aresult(tid)

        await mgr.ashutdown()

    async def test_ashutdown(self):
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
