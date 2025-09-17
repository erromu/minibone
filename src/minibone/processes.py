import asyncio
import logging
import uuid
from collections.abc import Callable
from concurrent.futures import CancelledError
from concurrent.futures import Future
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError
from threading import Lock
from typing import Any


class PARProcesses:
    """
    Async manager for parallel CPU-bound tasks using ProcessPoolExecutor.

    This class provides a simple interface for submitting, tracking, and retrieving results
    from CPU-bound tasks executed in parallel processes. It is designed for use with
    top-level functions (not instance methods or closures) to ensure compatibility with
    Python's multiprocessing pickling requirements.

    Best Practices:
      - Only submit top-level functions (not lambdas, closures, or bound methods).
      - Avoid passing objects that cannot be pickled (e.g., open files, locks, sockets).
      - Use the async methods (`aresult`, `await_all`, `ashutdown`) within an asyncio event loop.
      - Use the sync methods (`result`, `wait_all`, `shutdown`) for blocking, non-async code.
      - Call `ashutdown()` or `shutdown()` to cleanly close the process pool when done.
      - Use `cleanup()` to remove completed tasks and free memory.

    Example:
        >>> import asyncio
        >>> from minibone.processes import PARProcesses
        >>>
        >>> def mypow(x, y):
        ...     return x ** y
        ...
        >>> async def main():
        ...     mgr = PARProcesses()
        ...     tid = mgr.submit(mypow, 2, 8)
        ...     result = await mgr.aresult(tid)
        ...     print(result)
        ...     await mgr.ashutdown()
        >>>
        >>> asyncio.run(main())
        >>> 256
    """

    def __init__(self, max_workers: int | None = None):
        """Initialize the process pool manager.

        Args:
            max_workers: Maximum number of worker processes. If None, uses default.
                        Must be >= 1 if specified.

        Raises:
            ValueError: If max_workers is less than 1
        """
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self._logger = logging.getLogger(self.__class__.__name__)
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        self._futures: dict[str, Future] = {}  # Maps task IDs to Future objects
        self.lock = Lock()  # Protects access to _futures
        self._shutdown = False  # Whether shutdown has been initiated

    def submit(self, fn: Callable, *args, **kwargs) -> str:
        """
        Submit a task to the process pool and return a unique task ID.

        Args:
            fn (Callable): The function to execute in a separate process.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            str: A unique task ID.
        """
        if self._shutdown:
            raise RuntimeError("Cannot submit tasks after shutdown")
        task_id = str(uuid.uuid4())
        future = self._executor.submit(fn, *args, **kwargs)
        with self.lock:
            self._futures[task_id] = future
        self._logger.debug("Submitted task %s", task_id)
        return task_id

    def result(self, task_id: str, timeout: float | None = None, cleanup: bool = True) -> Any:
        """
        Get the result of a task by its ID (blocking, synchronous).
        By default, cleans up the future after retrieval (result cannot be retrieved again).

        Args:
            task_id (str): The task ID.
            timeout (float, optional): Seconds to wait for result.
            cleanup (bool): If True (default), remove the task after retrieval.

        Returns:
            Any: The result of the task.

        Raises:
            TimeoutError: if the result is not ready in time
            CancelledError: if the task was cancelled
            Exception: if the task raised an exception

        Note:
            After calling this method with cleanup=True, the result cannot be retrieved again.
        """
        with self.lock:
            future = self._futures.get(task_id)
        if not future:
            raise KeyError(f"No such task: {task_id}")
        try:
            result = future.result(timeout)
        except TimeoutError:
            self._logger.warning("Task %s timed out", task_id)
            raise
        except CancelledError:
            self._logger.warning("Task %s was cancelled", task_id)
            raise
        except Exception as e:
            self._logger.error("Task %s failed: %s", task_id, str(e))
            raise
        finally:
            if cleanup:
                with self.lock:
                    self._futures.pop(task_id, None)
        return result

    async def aresult(self, task_id: str, timeout: float | None = None, cleanup: bool = True) -> Any:
        """
        Get the result of a task by its ID (async, non-blocking).
        By default, cleans up the future after retrieval (result cannot be retrieved again).

        Args:
            task_id (str): The task ID.
            timeout (float, optional): Seconds to wait for result.
            cleanup (bool): If True (default), remove the task after retrieval.

        Returns:
            Any: The result of the task.

        Raises:
            TimeoutError: if the result is not ready in time
            CancelledError: if the task was cancelled
            Exception: if the task raised an exception

        Note:
            After calling this method with cleanup=True, the result cannot be retrieved again.
        """
        loop = asyncio.get_running_loop()
        with self.lock:
            future = self._futures.get(task_id)
        if not future:
            raise KeyError(f"No such task: {task_id}")

        def _get():  # ← no timeout here
            return future.result()

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _get),
                timeout=timeout,
            )
        except asyncio.TimeoutError:  # ← async-side timeout
            self._logger.warning(f"Task {task_id} timed out")
            raise
        except Exception as e:  # ← worker’s exception
            self._logger.error(f"Task {task_id} raised exception: {e}")
            raise
        finally:
            if cleanup:
                with self.lock:
                    self._futures.pop(task_id, None)

    def wait_all(self, cleanup: bool = True) -> dict[str, Any]:
        """
        Wait for all tasks to complete and return their results as a dict (blocking, synchronous).
        By default, cleans up all completed tasks.

        Args:
            cleanup (bool): If True (default), remove all completed tasks after retrieval.

        Returns:
            dict[str, Any]: Mapping of task IDs to results or exceptions.

        Note:
            If a task raises an exception, the exception object is stored in the results dict.
        """
        with self.lock:
            futures = self._futures.copy()
        results = {}
        for task_id, future in futures.items():
            try:
                results[task_id] = future.result()
            except Exception as e:
                results[task_id] = e
        if cleanup:
            self.cleanup()
        return results

    async def await_all(self, cleanup: bool = True) -> dict[str, Any]:
        """
        Async wait for all tasks to complete and return their results as a dict.
        By default, cleans up all completed tasks.

        Args:
            cleanup (bool): If True (default), remove all completed tasks after retrieval.

        Returns:
            dict[str, Any]: Mapping of task IDs to results or exceptions.

        Note:
            If a task raises an exception, the exception object is stored in the results dict.
        """
        loop = asyncio.get_running_loop()
        with self.lock:
            futures = self._futures.copy()
        results = {}
        for task_id, future in futures.items():
            try:
                results[task_id] = await loop.run_in_executor(None, future.result)
            except Exception as e:
                results[task_id] = e
        if cleanup:
            self.cleanup()
        return results

    def shutdown(self, wait: bool = True):
        """
        Synchronously shut down the process pool.

        Args:
            wait (bool): If True, wait for all running tasks to finish.
        """
        if self._shutdown:
            self._logger.warning("Process pool already shut down")
            return
        self._executor.shutdown(wait)
        self._shutdown = True
        self._logger.debug("Process pool shut down")

    async def ashutdown(self, wait: bool = True):
        """
        Async shutdown of the process pool.

        Args:
            wait (bool): If True, wait for all running tasks to finish.
        """
        if self._shutdown:
            self._logger.warning("Process pool already shut down")
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._executor.shutdown, wait)
        self._shutdown = True
        self._logger.debug("Process pool shut down")

    def status(self, task_id: str) -> str:
        """
        Get the status of a task.

        Args:
            task_id (str): The task ID.

        Returns:
            str: "unknown", "cancelled", "running", "exception", "done", or "pending"
        """
        with self.lock:
            future = self._futures.get(task_id)
        if not future:
            return "unknown"
        if future.cancelled():
            return "cancelled"
        if future.running():
            return "running"
        if future.done():
            if future.exception():
                return "exception"
            return "done"
        return "pending"

    def cleanup(self):
        """
        Remove all completed tasks from the futures dictionary.
        """
        with self.lock:
            done_keys = [k for k, f in self._futures.items() if f.done()]
            for k in done_keys:
                self._futures.pop(k, None)
        if done_keys:
            self._logger.debug("Cleaned up %d completed tasks", len(done_keys))
