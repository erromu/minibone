import logging
import threading
import time


class Daemon:
    """This class is to run tasks in the background in another thread

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

    - check minibone.sample_clock.py out if you want to learn how to use it

    Usage callback mode
    -------------------
    - Instance Daemon by passing a callable
    - Add logic to your callable method
    - Be sure your callable and methods are safe-thread to avoid race condition
    - call start() method to keep running callable in a new thread
    - call stop() to finish the thread

    - check minibone.sample_clock_callback.py out if you want to learn how to use it

    Notes:
    ------
    start() must be called once only
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

        daemon      bool        True to set it as a daemon, False otherwise

        kwargs                  Additional params you need to pass

        Notes
        -----
        sleep will block the thread, so if stop is called it will wait until sleep is done.
        sleep is implemented in a convenient way so this does not get resources hungry
        due to an iddle state just iterating in the loop waiting for something to do

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
        """Process to be called on each interation.

        If a callback was added, then it will be called instead.
        When subclasing Daemon, rewrite this method to add your logic to be run
        """
        pass

    def _do_process(self, **kwargs):
        while True:
            if self._stopping:
                return

            epoch = time.time()
            if epoch > self._check:
                self._check = epoch + self._interval

                if not self._callback:
                    self.on_process(**kwargs)
                else:
                    self._callback(**kwargs)

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
        """Stop this thread on_process/calback"""
        self.lock.acquire()
        self._stopping = True
        self.lock.release()

        self._logger.debug(
            "stopping %s task at interval: %.2f sleep: %.2f iterate: %d",
            self._name,
            self._interval,
            self._sleep,
            self._iter,
        )
