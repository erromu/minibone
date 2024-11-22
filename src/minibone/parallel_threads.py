import asyncio
import logging
import random
import threading
import time
from collections import deque
from enum import Enum

from minibone.daemon import Daemon


class TypeQueue(Enum):
    """Emum to define Type of queues

    FIFO = First in, first out
    LIFO = Last in, first out
    """

    FIFO = "FIFO"
    LIFO = "LIFO"


class PARThreads(Daemon):
    """Class to run parallel tasks in threads.

     This is suitable for I/O bounded tasks such as working with files or fetching web pages.
     For compute or CPU bounded tasks use PARProcesses instead.

    Usage
     -----
     - Create a PARThreads instance
     - call start()
     - call queue to add all your concurrent tasks and store the UID
     - call get(UID) to retrieve the callback's result
     - continue your queue / get loop
     - call stop at the end

     Example
     -------
     from minibone.parallel_threads import PARThreads
     import time

     def reporter(message: str):
         # to emulate a busy action
         time.sleep(1)
         return message

     t = PARThreads()
     t.start()

     # tasks will be run on its own CPU process
     uid1 = t.queue(reporter, message="Say")
     uid2 = t.queue(reporter, message="something")

     res1 = t.get(uid1)
     res2 = t.get(uid2)

     t.stop()

     print(res1, res2)
    """

    def __init__(self, type_queue: TypeQueue = TypeQueue.FIFO, max_threads=10, daemon: bool = True):
        """
        Arguments
        ---------
        type_queue:     TypeQueue       Type of queue desired (FIFO / LIFO)
        max_threads:    int             Maximum number of threads to run in parallel
        daemon:         bool            True to run as a daemon, False otherwise
        """
        assert isinstance(type_queue, TypeQueue)
        assert isinstance(max_threads, int) and max_threads > 0
        assert isinstance(daemon, bool)
        super().__init__(name="PoolThreads", interval=0.01, sleep=0.01, daemon=daemon)

        self._logger = logging.getLogger(__class__.__name__)

        self.type_queue = type_queue
        self._max_threads = max_threads
        self._current_task = 0

        self._queue = deque()
        self._results = {}

        random.seed(time.time())
        self._letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def _uid(self, cmd: str) -> str:
        """Return an unique UID

        Arguments
        ---------
        cmd:    str     String to prefix UID
        """
        assert isinstance(cmd, str)
        return "{}{}_{}".format(cmd, self._letters[random.randint(0, len(self._letters) - 1)], time.time())

    def _lookfor_result(self, uid: str) -> object:
        """Search for a result"""
        assert isinstance(uid, str)
        self.lock.acquire()
        resp = self._results.pop(uid, "_no_in_dict_")
        self.lock.release()
        return resp

    def get(self, uid: str, timeout=-1) -> object | None:
        """Return the response mapped to UID

        Arguments
        ---------
        uid:        str     Unique identifier of the expected result
        timeout:    int     Set the number of seconds to wait for a result.
                            Set to zero or negative to wait forever
        """
        assert isinstance(uid, str)
        assert isinstance(timeout, (int, float))

        notimeout = True if timeout <= 0 else False
        epoch = time.time()
        future_epoch = time.time() + timeout
        while notimeout or epoch < future_epoch:
            resp = self._lookfor_result(uid)
            if resp != "_no_in_dict_":
                return resp

            time.sleep(0.01)

        return None

    async def aioget(self, uid: str, timeout=-1) -> object | None:
        """Return the response mapped to UID in async mode

        Arguments
        ---------
        uid:        str     Unique identifier of the expected result
        timeout:    int     Set the number of seconds to wait for a result.
                            Set to zero or negative to wait forever
        """
        assert isinstance(uid, str)
        assert isinstance(timeout, (int, float))

        notimeout = True if timeout <= 0 else False
        epoch = time.time()
        future_epoch = time.time() + timeout
        while notimeout or epoch < future_epoch:
            resp = self._lookfor_result(uid)
            if resp != "_no_in_dict_":
                return resp

            asyncio.sleep(0.01)

        return None

    def queue(self, callback, cmd: str = "UID", **kwargs) -> str:
        """Queue a task and return an UID to get the result later

        Arguments
        ---------
        callback:   object  A callable object
        cmd:        str     Any command to prefix the UID to return
        kwargs:     dict    a dick with key/value parameters
        """
        assert callable(callable)
        assert not kwargs or isinstance(kwargs, dict)

        if not kwargs:
            kwargs = dict()

        uid = self._uid(cmd)
        item = {"uid": uid, "callback": callback, "kwargs": kwargs}

        self.lock.acquire()
        if self.type_queue == TypeQueue.LIFO:
            self._queue.appendleft(item)
        else:
            self._queue.append(item)
        self.lock.release()

        self._logger.debug("Task %s queued", uid)
        return uid

    def _process_task(self, uid, callback, kwargs):
        """Create a thread to run a task"""
        data = callback(**kwargs)

        self.lock.acquire()
        self._current_task -= 1
        self._results[uid] = data
        self.lock.release()
        self._logger.debug("Task %s done. Parallel tasks: %d", uid, self._current_task)

    def on_process(self):
        while len(self._queue) > 0 and self._current_task < self._max_threads:
            self.lock.acquire()
            item = self._queue.popleft()
            self._logger.debug("Task %s started", item["uid"])
            task = threading.Thread(target=self._process_task, kwargs=item)
            self._current_task += 1
            self.lock.release()
            task.start()
