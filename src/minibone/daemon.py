import logging
import threading
import time


class Daemon:
    """Class to run a periodical task in another thread

    Usage
    -----
    - Subclass Daemon
    - call super().__init__() in yours
    - Overwrite on_process method with yours
    - Add logic you want to run inside on_process
    - Be sure your methods are safe-thread to avoid race condition
    - self.lock is available for lock.acquire / your_logic / lock.release
    - call start() method to keep running on_process in a new thread
    - call stop() to finish the thread

    - check minibone.sample_clock.py if you want to learn how to use it

    Usage callback mode
    -------------------
    - Instance Daemon by passing a callable
    - Add logic to your callable method
    - Be sure your callable is safe-thread to avoid race condition
    - call start() method to keep running callable in a new thread
    - call stop() to finish the thread

    - check minibone.sample_clock_callback.py if you want to learn how to use it

    Notes:
    ------
    start() must be called only once
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

        sleep       int         Number of seconds to sleep on each interation when iddle.
                                Must be >= 0.01 and <= 1

        callback    callable    [Optional] A callable object to be called instead of on_process
                                Default None.

        iter        int         How many times to run this task. iter must be >= 1 or -1
                                -1 runs forever until stopped

        daemon      bool        True to set the Thread as a daemon, False otherwise

        kwargs                  Additional params you need to pass

        Notes
        -----
        sleep will block the thread, so if stop is called it will wait until sleep is done.
        sleep was implemented as a convenient way to avoid? it does not get resources hungry
        when in iddle state inside the bucle iterating/waiting for something to do

        Thumb of usage for sleep:
        Set to 0.01 if on_process is high priority
        """
        assert not name or isinstance(name, str)
        assert isinstance(interval, (float, int)) and interval >= 0
        assert isinstance(sleep, (float, int)) and sleep >= 0.01 and sleep <= 1
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
        """Method to be called on each interation.
        Overwrite it with your logic if a callback is not set

        Do not forget to make your code safe-thread using lock.acquire and lock.release
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

            time.sleep(self._sleep)

    def start(self):
        """Start running on_process/callback periodically"""

        self._process.start()

        self._logger.debug(
            "started %s task at interval: %.2f sleep: %.2f iterate: %d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )

    def stop(self):
        """Stop interating on on_process/callback and exit this thread"""
        self.lock.acquire()
        self._stopping = True
        self.lock.release()
        self._process.join()

        self._logger.debug(
            "stopping %s task at interval: %.2f sleep: %.2f iterate: %d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )
