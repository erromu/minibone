import time
import unittest
from threading import Lock

from src.minibone.daemon import Daemon


class DaemonSubClass(Daemon):
    value = 0

    def __init__(self):
        super().__init__(interval=1, iter=3)

    def on_process(self):
        self.lock.acquire()
        self.value += 1
        self.lock.release()


class TestDaemon(unittest.TestCase):
    lock = Lock()
    value = 0

    def callback(self):
        self.lock.acquire()
        self.value += 1
        self.lock.release()

    def test_daemon(self):
        """
        Test Daemon is running in the background doing the job
        """
        task1 = Daemon(interval=1, iter=3, callback=self.callback)
        task2 = Daemon(interval=1, iter=3, callback=self.callback)
        task3 = DaemonSubClass()

        task1.start()
        task2.start()
        task3.start()

        time.sleep(5)
        self.assertEqual(self.value, 6)
        self.assertEqual(task3.value, 3)

        task1.stop()
        task2.stop()
        task3.stop()


if __name__ == "__main__":
    unittest.main()
