import asyncio
import logging
import queue
import random
import signal
import time
from enum import Enum
from multiprocessing import Pool

from minibone.daemon import Daemon


class TypeQueue(Enum):
    """Emum to define Type of queues

    FIFO = First in, first out
    LIFO = Last in, first out
    """

    FIFO = "FIFO"
    LIFO = "LIFO"


class PARProcesses(Daemon):
    """Class to run parallel tasks as processes.

    This is suitable for CPU bound tasks such as heavy calculations and maths
    For I/O bounded tasks use PARThreads instead.

    Usage
    -----
    - Create a PARProcesses instance
    - call start()
    - call queue to add all your heavy computation tasks and store the UID
    - call get(UID) to retrieve the callback's result
    - continue your queue / get loop
    - call stop at the end

    Example
    -------
    from minibone.parallel_processes import PARProcesses

    def mypow(x, y):
        return x ** y

    p = PARProcesses()
    p.start()

    # tasks will be run on its own CPU process
    uid1 = p.queue(mypow, x=5, y=8)
    uid2 = p.queue(mypow, x=8, y=16)

    res1 = p.get(uid1)
    res2 = p.get(uid2)

    p.stop()

    print(res1, res2)
    """

    def __init__(self, type_queue: TypeQueue = TypeQueue.FIFO, daemon: bool = True):
        """
        Arguments
        ---------
        type_queue:     TypeQueue       Type of queue desired (FIFO, LIFO)
        daemon:         bool            True to run as a daemon, False otherwise
        """
        assert isinstance(type_queue, TypeQueue)
        assert isinstance(daemon, bool)
        super().__init__(name="PoolThreads", interval=0.01, sleep=0.01, daemon=daemon)

        self._logger = logging.getLogger(__class__.__name__)

        if type_queue == TypeQueue.FIFO:
            self._queue = queue.Queue()
        else:
            self._queue = queue.LifoQueue()

        self._pool = Pool(initializer=self._init_worker)
        self._processing = {}

        random.seed(time.time())
        self._letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def _init_worker(self):
        # https://stackoverflow.com/a/6191991
        signal.signal(signal.SIGINT, signal.SIG_IGN)

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
        resp = self._processing.pop(uid, "_no_in_dict_")
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
            if resp != "_no_in_dict_" and resp.ready:
                return resp.get()

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
            if resp != "_no_in_dict_" and resp.ready:
                return resp.get()

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
        self._queue.put(item)

        self._logger.debug("Task %s queued", uid)
        return uid

    def on_process(self):
        while self._queue.qsize() > 0:
            item = self._queue.get()
            self._logger.debug("Task %s started", item["uid"])

            resp = self._pool.apply_async(func=item["callback"], kwds=item["kwargs"])

            self.lock.acquire()
            self._processing[item["uid"]] = resp
            self.lock.release()

            self._queue.task_done()

    def stop(self):
        super().stop()
        self._pool.close()
        self._pool.terminate()
        self._pool.join()
