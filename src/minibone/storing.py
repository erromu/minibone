import json
import logging
from collections import deque

from minibone.config import FORMAT
from minibone.config import Config
from minibone.daemon import Daemon


class Storing(Daemon):
    """Background task for periodically saving objects to files.

    Features:
    - Queue-based asynchronous file saving
    - Supports JSON format (with potential for other formats)
    - Configurable batch processing
    - Thread-safe operations

    Basic Usage:
    -----------
    from minibone.storing import Storing

    # Initialize with default settings (process 5 items every 30 seconds)
    storer = Storing()
    storer.start()

    # Queue data to be saved
    storer.to_json("/data/path", "file.json", {"key": "value"})

    # When done
    storer.stop()

    Advanced Usage:
    --------------
    # Customize processing parameters
    storer = Storing(chunks=10, interval=60)  # Process 10 items every minute
    """

    @classmethod
    def json_from_file(cls, pathfile: str) -> dict:
        """Deprecated alias for from_json()."""
        _logger = logging.getLogger(__class__.__name__)
        _logger.warning("Use from_json() instead - will be deprecated")
        return cls.from_json(pathfile)

    @classmethod
    def from_json(cls, filepath: str) -> dict:
        """Load JSON data from a file.

        Args:
            filepath: Path to JSON file to load

        Returns:
            dict: Parsed JSON data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file contains invalid JSON
        """
        try:
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise
        except Exception as e:
            _logger = logging.getLogger(__class__.__name__)
            _logger.error("from_json error loading %s. %s", filepath, e)
            return None

    def __init__(self, chunks: int = 5, interval: int = 30):
        """Initialize the file storer.

        Args:
            chunks: Maximum items to process per batch (default: 5)
            interval: Seconds between processing batches (default: 30)

        Raises:
            ValueError: If chunks or interval are invalid
        """
        if not isinstance(chunks, int) or chunks < 1:
            raise ValueError("chunks must be positive integer")
        if not isinstance(interval, int) or interval < 1:
            raise ValueError("interval must be positive integer")
        super().__init__(name="storing", interval=interval)
        self._logger = logging.getLogger(__class__.__name__)

        # maximum number of items to process from the queue
        self._chunks = chunks
        self._queue = deque()

    def json_to_file(self, path: str, filename: str, data: dict | list) -> None:
        """Deprecated alias for to_json()."""
        self._logger.warning("Use to_json() instead - will be deprecated")
        self.to_json(path, filename, data)

    def to_json(self, path: str, filename: str, data: dict | list) -> None:
        """Queue JSON data to be saved to a file.

        Args:
            path: Directory path (without trailing slash)
            filename: Name of file to save
            data: JSON-serializable dict or list

        Raises:
            ValueError: If path/filename are invalid or data isn't JSON-serializable
        """
        if not isinstance(path, str) or not path:
            raise ValueError("path must be non-empty string")
        if not isinstance(filename, str) or not filename:
            raise ValueError("filename must be non-empty string")
        if not isinstance(data, dict | list):
            raise ValueError("data must be dict or list")

        item = {
            "format": FORMAT.JSON,
            "path": path,
            "file": filename,
            "data": data,
        }
        self._queue.append(item)
        self._logger.info("Queued %s/%s for saving", path, filename)

    def on_process(self) -> None:
        """Process queued items up to the chunk limit."""
        if not self._queue:
            return

        processed = 0
        while self._queue and processed < self._chunks:
            try:
                item = self._queue.popleft()
                # Handle path correctly, especially for "./" paths
                filepath = f"./{item['file']}" if item["path"] == "./" else f"{item['path']}/{item['file']}"
                Config.to_file(format=item["format"], filepath=filepath, data=item["data"])
                processed += 1
                self._logger.debug("Saved %s", filepath)
            except Exception as e:
                self._logger.error("Failed to save %s: %s", filepath, str(e))
