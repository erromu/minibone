"""Periodic task runner on a background thread.

Runs a callback or subclass-provided ``on_process`` on a fixed interval
inside a dedicated thread. Safe to start, stop, and restart.

Key behaviors:
- First ``on_process`` call happens immediately after ``start()``.
- ``stop()`` signals the loop and joins with a bounded timeout.
- ``on_process`` exceptions are logged and do not kill the loop.
- The same instance can be started again after ``stop()``.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING
from typing import Any


if TYPE_CHECKING:
    from collections.abc import Callable


class Daemon:
    """Run a periodic task in another thread.

    Subclassing:
        class MyDaemon(Daemon):
            def __init__(self):
                super().__init__(name="my_task", interval=10)

            def on_process(self):
                ...

    Callback:
        def my_task():
            ...

        daemon = Daemon(name="my_task", interval=10, callback=my_task)

    Parameters:
        name          str       Thread name for debugging.
        interval      float     Minimum seconds between ``on_process`` calls.
                                Must be >= 0. ``0`` runs as fast as possible
                                (bounded only by ``sleep``).
        sleep         float     Poll granularity in seconds. Must be > 0 and
                                <= 1. Lower values reduce latency at the cost
                                of more wake-ups. This is *not* the task
                                interval; it is how often the loop checks
                                whether the interval has elapsed.
        callback      callable  Optional. Called instead of ``on_process``.
        iter          int       Number of times to run. ``-1`` runs forever.
        daemon        bool      Mark the thread as a daemon thread.
        stop_timeout  float     Max seconds ``stop()`` waits for the thread
                                to finish. Independent of ``interval``.
        **kwargs                Forwarded to ``on_process`` / ``callback``.

    Thread safety:
        The internal ``lock`` is provided for subclasses. Use it around any
        shared mutable state accessed by both ``on_process`` and the caller.

    Notes:
        - ``on_process`` (or ``callback``) must accept the same ``**kwargs``
          passed to the constructor. The base ``on_process`` signature
          already accepts ``**kwargs``.
        - First call is immediate on ``start()``. Subsequent calls wait at
          least ``interval`` seconds between invocations.
    """

    def __init__(
        self,
        name: str | None = None,
        interval: float = 60,
        *,
        sleep: float = 0.5,
        callback: Callable | None = None,
        iter: int = -1,
        daemon: bool = True,
        stop_timeout: float = 10.0,
        **kwargs: Any,
    ):
        assert not name or isinstance(name, str)
        assert isinstance(interval, (int, float)) and interval >= 0
        assert isinstance(sleep, (int, float)) and 0 < sleep <= 1
        assert not callback or callable(callback)
        assert isinstance(iter, int) and (iter == -1 or iter >= 1)
        assert isinstance(daemon, bool)
        assert isinstance(stop_timeout, (int, float)) and stop_timeout > 0

        self._logger = logging.getLogger(self.__class__.__name__)

        self.lock = threading.Lock()

        # threading.Event is the correct primitive for cross-thread signals:
        # atomic, and clearable, which makes restart trivial.
        self._stop_event = threading.Event()

        self._name = name
        self._interval = interval
        self._sleep = sleep
        self._iter = iter
        self._callback = callback
        self._kwargs = kwargs
        self._stop_timeout = stop_timeout
        self._is_daemon = daemon

        # Set in start(). Kept None until then so restart is possible.
        self._process: threading.Thread | None = None

        # Loop state, reset on each start().
        self._check = 0.0
        self._count = 0

    # -- Public API -------------------------------------------------------

    def start(self) -> None:
        """Start the periodic task.

        Raises:
            RuntimeError: if the thread is already running.
        """
        if self._process is not None and self._process.is_alive():
            raise RuntimeError("Thread is already running")

        self._stop_event.clear()
        self._check = 0.0
        self._count = 0

        self._process = threading.Thread(
            name=self._name,
            target=self._do_process,
            daemon=self._is_daemon,
        )
        self._process.start()

        self._logger.debug(
            "started %s interval=%.2f sleep=%.2f iter=%d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

    def stop(self) -> None:
        """Signal the loop to stop and wait for the thread to exit.

        Bounded by ``stop_timeout``. Safe to call when not running.
        """
        self._stop_event.set()

        if self._process is not None:
            self._process.join(timeout=self._stop_timeout)
            if self._process.is_alive():
                self._logger.warning(
                    "Thread %s did not stop within %.1fs",
                    self._name,
                    self._stop_timeout,
                )

        self._logger.debug(
            "stopped %s interval=%.2f sleep=%.2f iter=%d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

    def is_running(self) -> bool:
        """Return True if the worker thread is alive."""
        return self._process is not None and self._process.is_alive()

    # -- Hook for subclasses ---------------------------------------------

    def on_process(self, **kwargs: Any) -> None:
        """Called on each interval.

        Override in subclasses. Use ``self.lock`` around shared state.

        Exceptions raised here are logged and do not stop the loop.
        """
        pass

    # -- Internals --------------------------------------------------------

    def _do_process(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()
            if now >= self._check:
                self._check = now + self._interval

                try:
                    if self._callback:
                        self._callback(**self._kwargs)
                    else:
                        self.on_process(**self._kwargs)
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

            # sleep() on Event returns early if stop() is called, which
            # makes shutdown responsive even with long intervals.
            if self._sleep > 0:
                self._stop_event.wait(self._sleep)
