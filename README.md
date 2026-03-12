# minibone

[![Check](https://github.com/erromu/minibone/actions/workflows/python-check.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-check.yml) [![Deploy](https://github.com/erromu/minibone/actions/workflows/python-publish.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-publish.yml) [![PyPI version](https://badge.fury.io/py/minibone.svg)](https://pypi.org/project/minibone)

minibone is an easy-to-use yet powerful boilerplate for multithreading, multiprocessing, and other functionalities:

- **Config**: To handle configuration settings
- **Daemon**: To run a periodic task in another thread
- **Emailer**: To send emails in concurrent threads
- **HTMLBase**: To render HTML using snippets and TOML configuration files in async mode
- **HTTPt**: HTTP client to perform concurrent requests in threads
- **Logging**: To set up a logger friendly to file rotation
- **IOThreads**: To run concurrent tasks in threads
- **PARProcesses**: To run parallel CPU-bound tasks
- **Storing**: To queue and store files periodically in a thread (queue and forget)

It will be deployed to PyPI when a new release is created.

## Installation

```shell
pip install minibone
```

## Config

Handle configuration settings in memory and/or persist them into TOML/YAML/JSON formats.

```python
from minibone.config import Config

# Create a new set of settings and persist them
cfg = Config(settings={"listen": "localhost", "port": 80}, filepath="config.toml")
cfg.add("debug", True)
cfg.to_toml()

# Load settings from a file. Defaults can be set. More information: help(Config.from_toml)
cfg2 = Config.from_toml("config.toml")

# There are also asynchronous counterpart methods
import asyncio

cfg3 = asyncio.run(Config.aiofrom_toml("config.toml"))
```

Usually, configuration files are edited externally and loaded as read-only in your code. In such cases, you may want to subclass Config for easier usage.

```python
from minibone.config import Config

class MyConfig(Config):

    def __init__(self):
        defaults = {"main": {"listen": "localhost", "port": 80}}
        settings = Config.from_toml(filepath="config.toml", defaults=defaults)
        super().__init__(settings=settings)

    @property
    def listen(self) -> str:
        return self["main"]["listen"]

    @property
    def port(self) -> int:
        return self["main"]["port"]

if __name__ == "__main__":
    cfg = MyConfig()
    print(cfg.port)
    # It will print the default port value if no port setting is defined in config.toml
```

## Daemon

It is another Python class designed to run a periodic task in another thread. It can be used in two modes: subclassing and callback.

### Usage as Subclass Mode

- Subclass Daemon.
- Call `super().__init__()`.
- Override the `on_process` method with your own.
- Add the logic you want to run inside `on_process`.
- Ensure your methods are thread-safe to avoid race conditions.
- `self.lock` is available for `lock.acquire()` / your logic / `lock.release()`.
- Call the `start()` method to keep running `on_process` in a new thread.
- Call the `stop()` method to finish the thread.

Check [sample_clock.py](https://github.com/erromu/minibone/blob/main/samples/sample_clock.py) for a sample.

### Usage as Callback Mode

- Instantiate Daemon by passing a callable.
- Add logic to your callable method.
- Ensure your callable is thread-safe to avoid race conditions.
- Call the `start()` method to keep running the callable in a new thread.
- Call the `stop()` method to finish the thread.

Check [sample_clock_callback.py](https://github.com/erromu/minibone/blob/main/samples/sample_clock_callback.py) for a sample.

## AsyncDaemon

It is another Python class designed to run a periodic task using asyncio instead of threads. It can be used in two modes: subclassing and callback.

### Usage as Subclass Mode

- Subclass AsyncDaemon.
- Call `super().__init__()`.
- Override the `on_process` method with your own (must be async).
- Add the logic you want to run inside `on_process`.
- Ensure your methods are async-safe to avoid race conditions.
- `self.lock` is available for use with the `async with self.lock` context manager.
- Call `await start()` to keep running `on_process` as a task.
- Call `await stop()` to finish the task.

Check [sample_async_clock.py](https://github.com/erromu/minibone/blob/main/samples/sample_async_clock.py) for a sample.

### Usage as Callback Mode

- Instantiate AsyncDaemon by passing an async callable.
- Add logic to your callable method (must be async).
- Ensure your callable is async-safe to avoid race conditions.
- Call `await start()` to keep running the callable as a task.
- Call `await stop()` to finish the task.

Check [sample_async_clock_callback.py](https://github.com/erromu/minibone/blob/main/samples/sample_async_clock_callback.py) for a sample.

## Logging

Set up a logger using UTC time that outputs logs to stdout or to a file. It is friendly to file rotation (when setting output to a file).

```python
import logging

from minibone.logging import setup_log

if __name__ == "__main__":

    # setup_log must be called only once in your code.
    # You have to choose whether to log to stdout or to a file when calling it.

    setup_log(level="INFO")
    logging.info('This is a log to stdout')

    # Or call the next lines instead if you want to log into a file:
    # setup_log(file="sample.log", level="INFO")
    # logging.info('yay!')
```

## Contribution

- Feel free to clone this repository and send any pull requests.
- Add issues if something is not working as expected.
