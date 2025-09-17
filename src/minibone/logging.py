import logging
import logging.handlers
import time


def setup_log(
    file: str = None, level: str | int = logging.INFO, log_format: str = None, date_format: str = None
) -> None:
    """Configure logging with file rotation or stderr output.

    Args:
        file: Path to log file. If None, logs to stderr.
        level: Logging level as string or int (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string. Default includes timestamp, level, name and message.
        date_format: Custom date format string. Default is "%Y-%m-%d %H:%M:%S".

    Raises:
        ValueError: If invalid log level is provided

    Example:
        >>> # Log to file with DEBUG level
        >>> setup_log("app.log", "DEBUG")
        >>>
        >>> # Log to stderr with custom format
        >>> setup_log(None, logging.INFO,
        ...          "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    """
    if not isinstance(level, int | str):
        raise TypeError("level must be str or int")

    if isinstance(level, str):
        level = level.upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {level}")
        level = getattr(logging, level)

    format = log_format or "%(asctime)s UTC [%(levelname)s] %(name)s: %(message)s"
    datefmt = date_format or "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=format, datefmt=datefmt)
    formatter.converter = time.gmtime  # Use UTC/GMT time

    if file:
        try:
            log_handler = logging.handlers.WatchedFileHandler(file)
            log_handler.setFormatter(formatter)

            logger = logging.getLogger()
            # Remove any existing handlers to avoid duplicates
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            logger.addHandler(log_handler)
            logger.setLevel(level)
        except Exception as e:
            logging.basicConfig(level=level, format=format, datefmt=datefmt)
            logging.error("Failed to setup file logging: %s", e)
    else:
        logging.basicConfig(level=level, format=format, datefmt=datefmt)
