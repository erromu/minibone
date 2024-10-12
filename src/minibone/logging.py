import logging
import logging.handlers
import time


def setup_log(file: str = None, level: str | int = logging.INFO):
    """Setup log using handlers to support file rotation

    Arguments
    ---------
    file:   str     Full path and name of the file.  Set to None to log to stderr instead
    level:  str     The log level. [DEBUG, INFO, WARNING, ERROR, CRITICAL]
    """
    assert not file or isinstance(file, str)
    assert isinstance(level, (int, str))

    format = "%(asctime)s UTC [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    if file:
        formatter = logging.Formatter(fmt=format, datefmt=datefmt)
        # date time in GMT/UTC
        formatter.converter = time.gmtime

        log_handler = logging.handlers.WatchedFileHandler(file)
        log_handler.setFormatter(formatter)

        logger = logging.getLogger()
        logger.addHandler(log_handler)
        logger.setLevel(level)

    else:
        # date time in GMT/UTC
        logging.Formatter.converter = time.gmtime
        logging.basicConfig(level=level, format=format, datefmt=datefmt)
