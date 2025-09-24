import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any


class AsyncDaemon:
    """Class to run a periodic task using asyncio instead of threads

    Usage (Subclassing):
    -------------------
    class MyAsyncDaemon(AsyncDaemon):
        def __init__(self):
            super().__init__(name="my_task", interval=10)

        async def on_process(self):
            # Your periodic task logic here
            pass

    Usage (Callback):
    ----------------
    async def my_task():
        # Your periodic task logic here
        pass

    daemon = AsyncDaemon(name="my_task", interval=10, callback=my_task)

    Common Parameters:
    -----------------
    name: str - Name for the task (helpful for debugging)
    interval: int - Seconds between executions (>= 0)
    sleep: float - Seconds to sleep between checks (0 <= sleep <= 1)
    callback: callable - Optional async function to call instead of on_process
    iter: int - Number of iterations (-1 for infinite)
    **kwargs - Additional params you need to pass

    Async Safety:
    -------------
    - Use asyncio locks for async-safe operations:
      async with self.lock:
          # Critical section
    - Avoid shared state between tasks when possible

    Examples:
    --------
    # Using callback
    async def my_callback():
        print("Task executed")

    daemon = AsyncDaemon(name="test", interval=1, callback=my_callback)
    await daemon.start()

    # Using subclassing
    class MyDaemon(AsyncDaemon):
        async def on_process(self):
            print("Task executed")

    daemon = MyDaemon(name="test", interval=1)
    await daemon.start()

    Notes:
    ------
    - start() returns a task that can be awaited or cancelled
    - stop() will wait for current iteration to complete
    - All callback and on_process methods must be async
    """

    def __init__(
        self,
        name: str | None = None,
        interval: float = 60,
        sleep: float = 0.5,
        callback: Callable | None = None,
        iter: int = -1,
        **kwargs: Any,
    ):
        """
        Arguments
        ---------
        name        str         name for this task

        interval    float       Number of interval seconds to run on_process.
                                Must be >= 0

        sleep       float       Number of seconds to sleep between iterations when idle.
                                Must be >= 0 and <= 1. Set to 0 to disable sleeping.
                                Sleep occurs after calling on_process/callback

        callback    callable    [Optional] An async callable object to be called instead of on_process
                                Default None.

        iter        int         How many times to run this task. iter must be >= 1 or -1
                                -1 runs forever until stopped

        kwargs                  Additional params you need to pass

        Notes
        -----
        sleep controls how often the task checks for work:
        - A higher sleep value reduces CPU usage but increases response time
        - A value of 0 will poll continuously (high CPU usage)

        Recommended values:
        - 0.01 - 0.1 for high priority tasks
        - 0.5 - 1.0 for background tasks
        """
        assert not name or isinstance(name, str)
        assert isinstance(interval, float | int) and interval >= 0
        assert isinstance(sleep, float | int) and sleep >= 0 and sleep <= 1
        assert not callback or (callable(callback) and asyncio.iscoroutinefunction(callback))
        assert isinstance(iter, int) and (iter == -1 or iter >= 1)
        self._logger = logging.getLogger(__class__.__name__)

        self.lock = asyncio.Lock()
        self._stopping = False

        self._name = name
        self._interval = max(interval - sleep, 0)
        self._sleep = sleep
        self._check = 0
        self._iter = iter
        self._count = 0

        self._callback = callback
        self._kwargs = kwargs
        self._task: asyncio.Task | None = None

    async def on_process(self) -> None:
        """Async method to be called on each iteration.
        Override this with your logic when not using a callback.

        Note:
        -----
        For async safety:
        - Use async with self.lock context manager:
          async with self.lock:
              # Critical section
        - Avoid modifying shared state without locking

        Example:
        -------
        async def on_process(self):
            async with self.lock:
                # Async-safe operations here
                await self.process_data()
        """
        pass

    async def _do_process(self) -> None:
        """Internal async method that runs the periodic task."""
        try:
            while True:
                if self._stopping:
                    return

                epoch = time.time()
                if epoch > self._check:
                    self._check = epoch + self._interval

                    try:
                        if self._callback:
                            if not asyncio.iscoroutinefunction(self._callback):
                                raise TypeError(f"Callback {self._callback.__name__} must be an async function")
                            await self._callback(**self._kwargs)
                        else:
                            await self.on_process(**self._kwargs)
                    except Exception as e:
                        self._logger.error("Error in %s task: %s", self._name, str(e))
                        # Continue running despite errors

                    if self._iter > 0:
                        self._count += 1
                        if self._count >= self._iter:
                            return

                if self._sleep > 0:
                    await asyncio.sleep(self._sleep)
        except asyncio.CancelledError:
            self._logger.debug("Task %s was cancelled", self._name)
            raise
        except Exception as e:
            self._logger.error("Unexpected error in %s task: %s", self._name, str(e))

    async def start(self) -> asyncio.Task:
        """Start running on_process/callback periodically.

        Returns:
        -------
        asyncio.Task - The task object that can be awaited or cancelled

        Raises:
        ------
        RuntimeError: If task is already running
        """
        if self._task and not self._task.done():
            raise RuntimeError("Task is already running")

        self._stopping = False
        self._task = asyncio.create_task(self._do_process(), name=self._name)

        self._logger.debug(
            "started %s task at interval: %.2f sleep: %.2f iterate: %d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

        return self._task

    async def stop(self) -> None:
        """Stop executing on_process/callback and exit the task.

        Will wait for current iteration to complete.
        """
        async with self.lock:
            self._stopping = True

        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self._logger.debug(
            "stopping %s task at interval: %.2f sleep: %.2f iterate: %d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

    def is_running(self) -> bool:
        """Check if the daemon task is currently running."""
        return self._task is not None and not self._task.done()
