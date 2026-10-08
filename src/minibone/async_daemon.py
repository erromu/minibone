"""Periodic task runner built on asyncio.

Runs a coroutine callback or subclass-provided ``on_process`` on a fixed
interval as an asyncio task. Safe to start, stop, and restart.

Key behaviors:
- First ``on_process`` call happens immediately after ``start()``.
- ``stop()`` signals the loop, waits for the current iteration to finish
  gracefully, and force-cancels only if the graceful window expires.
- ``on_process`` exceptions are logged and do not kill the loop.
- The same instance can be started again after ``stop()``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING
from typing import Any


if TYPE_CHECKING:
    from collections.abc import Callable


class AsyncDaemon:
    """Run a periodic task as an asyncio task.

    Subclassing:
        class MyDaemon(AsyncDaemon):
            def __init__(self):
                super().__init__(name="my_task", interval=10)

            async def on_process(self):
                ...

    Callback:
        async def my_task():
            ...

        daemon = AsyncDaemon(name="my_task", interval=10, callback=my_task)

    Parameters:
        name          str       Task name for debugging.
        interval      float     Minimum seconds between ``on_process`` calls.
                                Must be >= 0. ``0`` runs as fast as possible
                                (bounded only by ``sleep``).
        sleep         float     Poll granularity in seconds. Must be in
                                ``[0, 1]``. Lower values reduce latency at
                                the cost of more wake-ups. This is *not* the
                                task interval; it is how often the loop
                                checks whether the interval has elapsed.
                                Set to 0 to disable sleeping (high CPU).
        callback      async     Optional. Awaited instead of ``on_process``.
        iter          int       Number of times to run. ``-1`` runs forever.
        stop_timeout  float     Graceful shutdown budget in seconds. After
                                this elapses, the task is force-cancelled.
        **kwargs                Forwarded to ``on_process`` / ``callback``.

    Async safety:
        The internal ``lock`` is provided for subclasses. Use it around any
        shared mutable state accessed by both ``on_process`` and the caller.

    Notes:
        - ``on_process`` (or ``callback``) must accept the same ``**kwargs``
          passed to the constructor. The base ``on_process`` signature
          already accepts ``**kwargs``.
        - First call is immediate on ``start()``. Subsequent calls wait at
          least ``interval`` seconds between invocations.
        - ``asyncio.Lock`` / ``asyncio.Event`` are constructed lazily on
          the running loop in modern Python (3.10+); creating an
          ``AsyncDaemon`` outside a running loop is fine as long as
          ``start()`` is awaited inside one.
    """

    def __init__(
        self,
        name: str | None = None,
        interval: float = 60,
        sleep: float = 0.5,
        callback: Callable | None = None,
        iter: int = -1,
        stop_timeout: float = 10.0,
        **kwargs: Any,
    ):
        assert not name or isinstance(name, str)
        assert isinstance(interval, (int, float)) and interval >= 0
        assert isinstance(sleep, (int, float)) and 0 <= sleep <= 1
        assert not callback or (callable(callback) and asyncio.iscoroutinefunction(callback))
        assert isinstance(iter, int) and (iter == -1 or iter >= 1)
        assert isinstance(stop_timeout, (int, float)) and stop_timeout > 0

        self._logger = logging.getLogger(self.__class__.__name__)

        self.lock = asyncio.Lock()

        # asyncio.Event is the correct primitive for cross-task signalling:
        # atomic, awaitable, and clearable (so restart is trivial).
        self._stop_event = asyncio.Event()

        self._name = name
        self._interval = interval
        self._sleep = sleep
        self._iter = iter
        self._callback = callback
        self._kwargs = kwargs
        self._stop_timeout = stop_timeout

        # Set in start(). Kept None until then so restart is possible.
        self._task: asyncio.Task | None = None

        # Loop state, reset on each start().
        self._check = 0.0
        self._count = 0

    # -- Public API -------------------------------------------------------

    async def start(self) -> asyncio.Task:
        """Start the periodic task.

        Returns:
            The asyncio Task that runs the loop.

        Raises:
            RuntimeError: if the task is already running.
        """
        if self._task is not None and not self._task.done():
            raise RuntimeError("Task is already running")

        self._stop_event.clear()
        self._check = 0.0
        self._count = 0

        self._task = asyncio.create_task(self._do_process(), name=self._name)

        self._logger.debug(
            "started %s interval=%.2f sleep=%.2f iter=%d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

        return self._task

    async def stop(self, timeout: float | None = None) -> None:
        """Signal the loop to stop and wait for it to exit.

        Waits up to ``timeout`` seconds (default: ``stop_timeout`` from the
        constructor) for the current iteration to complete. If the task
        does not exit in time, it is force-cancelled.

        Safe to call when not running.
        """
        timeout = self._stop_timeout if timeout is None else timeout

        # Signal graceful stop. The loop checks this at the top of each
        # iteration, so a long-running on_process finishes naturally.
        self._stop_event.set()

        if self._task is None or self._task.done():
            self._logger.debug("stopped %s (not running)", self._name)
            return

        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning(
                "Task %s did not stop within %.1fs, cancelling",
                self._name,
                timeout,
            )
            # wait_for already requested cancellation. Await to reap.
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        except asyncio.CancelledError:
            # If we ourselves are being cancelled, propagate.
            raise

        self._logger.debug(
            "stopped %s interval=%.2f sleep=%.2f iter=%d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

    def is_running(self) -> bool:
        """Return True if the task is currently running."""
        return self._task is not None and not self._task.done()

    # -- Hook for subclasses ---------------------------------------------

    async def on_process(self, **kwargs: Any) -> None:
        """Called on each interval.

        Override in subclasses. Use ``async with self.lock`` around shared
        state.

        Exceptions raised here are logged and do not stop the loop.
        """
        pass

    # -- Internals --------------------------------------------------------

    async def _do_process(self) -> None:
        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                if now >= self._check:
                    self._check = now + self._interval

                    try:
                        if self._callback:
                            await self._callback(**self._kwargs)
                        else:
                            await self.on_process(**self._kwargs)
                    except asyncio.CancelledError:
                        # Never swallow cancellation.
                        raise
                    except Exception as e:
                        # Keep the loop alive across a single bad iteration.
                        # Includes traceback for diagnosis.
                        self._logger.exception(
                            "%s raised on iteration %d: %s",
                            self._name,
                            self._count,
                            e,
                        )

                    if self._iter > 0:
                        self._count += 1
                        if self._count >= self._iter:
                            return

                if self._sleep > 0:
                    await asyncio.sleep(self._sleep)
        except asyncio.CancelledError:
            self._logger.debug("Task %s was cancelled", self._name)
            raise
