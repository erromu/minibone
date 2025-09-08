import unittest

from minibone.processes import PARProcesses


def add(x, y):
    return x + y

def fail(x):
    raise ValueError(f"{x} fail!")

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

if __name__ == "__main__":
    unittest.main()
