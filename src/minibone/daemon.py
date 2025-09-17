import logging
import threading
import time


class Daemon:
    """Class to run a periodic task in another thread

    Usage (Subclassing):
    -------------------
    class MyDaemon(Daemon):
        def __init__(self):
            super().__init__(name="my_task", interval=10)

        def on_process(self):
            # Your periodic task logic here
            pass

    Usage (Callback):
    ----------------
    def my_task():
        # Your periodic task logic here
        pass

    daemon = Daemon(name="my_task", interval=10, callback=my_task)

    Common Parameters:
    -----------------
    name: str - Name for the thread (helpful for debugging)
    interval: int - Seconds between executions (>= 0)
    sleep: float - Seconds to sleep between checks (0 <= sleep <= 1)
    callback: callable - Optional function to call instead of on_process
    iter: int - Number of iterations (-1 for infinite)
    daemon: bool - Whether thread should be a daemon thread

    Thread Safety:
    -------------
    - Use self.lock for thread-safe operations:
      with self.lock:
          # Critical section
    - Avoid shared state between threads when possible

    Examples:
    --------
    See minibone/sample_clock.py and minibone/sample_clock_callback.py

    Notes:
    ------
    - start() must be called only once
    - stop() will wait for current iteration to complete
    """

    def __init__(
        self,
        name: str = None,
        interval: int = 60,
        sleep: float = 0.5,
        callback=None,
        iter: int = -1,
        daemon: bool = True,
        **kwargs,
    ):
        """
        Arguments
        ---------
        name        str         name for this thread

        interval    int         Number of interval seconds to run on_process.
                                Must be >= 0

        sleep       float       Number of seconds to sleep between iterations when idle.
                                Must be >= 0 and <= 1. Set to 0 to disable sleeping.
                                Sleep occurs after calling on_process/callback

        callback    callable    [Optional] A callable object to be called instead of on_process
                                Default None.

        iter        int         How many times to run this task. iter must be >= 1 or -1
                                -1 runs forever until stopped

        daemon      bool        True to set the Thread as a daemon, False otherwise

        kwargs                  Additional params you need to pass

        Notes
        -----
        sleep controls how often the thread checks for work:
        - A higher sleep value reduces CPU usage but increases response time
        - A value of 0 will poll continuously (high CPU usage)
        - stop() will wait for current sleep interval to complete

        Recommended values:
        - 0.01 - 0.1 for high priority tasks
        - 0.5 - 1.0 for background tasks
        """
        assert not name or isinstance(name, str)
        assert isinstance(interval, float | int) and interval >= 0
        assert isinstance(sleep, float | int) and sleep >= 0 and sleep <= 1
        assert not callback or callable(callback)
        assert isinstance(iter, int) and (iter == -1 or iter >= 1)
        assert isinstance(daemon, bool)
        self._logger = logging.getLogger(__class__.__name__)

        self.lock = threading.Lock()
        self._stopping = False

        self._name = name
        self._interval = interval
        self._sleep = sleep
        self._check = 0
        self._iter = iter
        self._count = 0

        self._callback = callback

        self._process = threading.Thread(
            name=self._name, target=self._do_process, kwargs=kwargs, daemon=True if daemon else None
        )

    def on_process(self):
        """Method to be called on each iteration.
        Override this with your logic when not using a callback.

        Note:
        -----
        For thread safety:
        - Use self.lock context manager:
          with self.lock:
              # Critical section
        - Avoid modifying shared state without locking

        Example:
        -------
        def on_process(self):
            with self.lock:
                # Thread-safe operations here
                self.process_data()
        """
        pass

    def _do_process(self, **kwargs):
        while True:
            if self._stopping:
                return

            epoch = time.time()
            if epoch > self._check:
                self._check = epoch + self._interval

                if self._callback:
                    self._callback(**kwargs)
                else:
                    self.on_process(**kwargs)

                if self._iter > 0:
                    self._count += 1
                    if self._count >= self._iter:
                        return

            if self._sleep > 0:
                time.sleep(self._sleep)

    def start(self) -> None:
        """Start running on_process/callback periodically.

        Raises:
        ------
        RuntimeError: If thread is already running
        """
        if self._process.is_alive():
            raise RuntimeError("Thread is already running")

        self._process.start()

        self._logger.debug(
            "started %s task at interval: %.2f sleep: %.2f iterate: %d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

    def stop(self) -> None:
        """Stop executing on_process/callback and exit the thread.

        Will wait for current iteration to complete.
        """
        with self.lock:
            self._stopping = True
        self._process.join(timeout=self._interval * 2)

        if self._process.is_alive():
            self._logger.warning("Thread did not stop gracefully")

        self._logger.debug(
            "stopping %s task at interval: %.2f sleep: %.2f iterate: %d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )
