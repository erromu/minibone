import logging
from collections import deque

from minibone.config import FORMAT, Config
from minibone.daemon import Daemon


class Storing(Daemon):
    """Periodical background task to save objects to file

    This is a queue and forget task to save files

    Usage
    -----
    - create an instance of this class
    - call start()
    - add objects to queue
    - call stop() to stop this thread

    Example
    --------
    from minibone.storing import Storing
    task = Storing()
    task.start()
    data = {"key1": "val1", "key2": "val2"}
    task.to_json(data)
    # data will be saved to json format in another thread
    # another code
    # call stop at the end of your program
    task.stop()
    """

    @classmethod
    def json_from_file(cls, pathfile: str) -> dict:
        """This is an alias to Storing.from_json"""
        _logger = logging.getLogger(__class__.__name__)
        _logger.warning("Use from_json instead.  This method will be deprecated at future")
        return cls.from_json(pathfile)

    @classmethod
    def from_json(cls, filepath: str) -> dict:
        """Return a JSON object from a file"""
        return Config.from_file(format=FORMAT.JSON, filepath=filepath)

    def __init__(self, chunks: int = 5, interval: int = 30):
        """
        Arguments
        ---------
        chunks:     int     Max number of objects to process per iteration
        """
        assert isinstance(chunks, int)
        assert isinstance(interval, int)
        super().__init__(name="storing", interval=interval)
        self._logger = logging.getLogger(__class__.__name__)

        # maximum number of items to process from the queue
        self._chunks = chunks
        self._queue = deque()

    def json_to_file(self, path: str, filename: str, data: dict | list):
        """This is an alias to Storing.to_json"""
        self._logger.warning("Use to_json instead.  This method will be deprecated at future")
        self.to_json(path, filename, data)

    def to_json(self, path: str, filename: str, data: dict | list):
        """Queue a JSON object to be stored in path

        Arguments
        ---------
        path        str         The directory to store json into. Do not add trailing slash /
        filename:   str         The filename to use for saving data
        data:       dict|list   A JSON dict or list to be stored
        """
        assert isinstance(path, str)
        assert isinstance(filename, str)
        assert isinstance(data, (dict, list))

        item = {"format": FORMAT.JSON, "path": path, "file": filename, "data": data}
        self._queue.append(item)
        self._logger.info("{}/{} aded to queue".format(path, filename))

    def on_process(self):
        if len(self._queue) == 0:
            return

        for i in range(min(len(self._queue), self._chunks)):
            d = self._queue.popleft()
            filepath = "{}/{}".format(d["path"], d["file"])
            Config.to_file(format=FORMAT.JSON, filepath=filepath, data=d["data"])
