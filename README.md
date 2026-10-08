# minibone

[![Check](https://github.com/erromu/minibone/actions/workflows/python-check.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-check.yml) [![Deploy](https://github.com/erromu/minibone/actions/workflows/python-publish.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-publish.yml) [![PyPI version](https://badge.fury.io/py/minibone.svg)](https://pypi.org/project/minibone)

minibone is an easy-to-use yet powerful boilerplate for multithreading, multiprocessing, and other functionalities:

- **Config**: To handle configuration settings
- **Daemon**: To run a periodic task in another thread
- **AsyncDaemon**: To run a periodic task on the asyncio loop
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

### Layering: defaults, file, overrides

`from_toml`, `from_yaml`, `from_json` (and their `aio*` counterparts) accept three
layers, merged in this order (lowest to highest priority):

```python
cfg = Config.from_toml(
    "config.toml",
    defaults={"listen": "localhost", "port": 80},
    overrides={"port": 9000},  # env vars, CLI args, tests...
)
# listen -> "localhost" (from defaults)
# port   -> 9000        (overrides beat everything)
```

`defaults` is a base the file extends. `overrides` is the opposite: it wins.
Use it to layer values from environment variables, CLI arguments, or test
fixtures without `Config` needing to know where they came from. Both are
optional and merged recursively.

### Subclassing

Usually, configuration files are edited externally and loaded as read-only in
your code. In such cases, you may want to subclass `Config` for easier usage.

```python
from minibone.config import Config


class MyConfig(Config):
    def __init__(self):
        defaults = {"main": {"listen": "localhost", "port": 80}}
        settings = Config.from_toml(
            filepath="config.toml",
            defaults=defaults,
            overrides={"main": {"port": 9000}},  # optional, highest priority
        )
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

### Notes

- Atomic file writes: contents are written to a temp file in the target
  directory, `fsync`'d, then `os.replace`'d into place. A crash mid-write
  never leaves a truncated config behind.
- Deep merge handles nested dicts. Precedence at depth is the same as at the
  top level: `defaults < file < overrides`.
- Keys must match `^[a-z][a-zA-Z0-9_]*$`. Values may be `str`, `int`, `float`,
  `list`, `dict`, `bool`, `datetime`, `date`, `time`, or `None`.
- `sha256` returns a stable hash of the current settings. `sha1` still exists
  but is deprecated and emits a `DeprecationWarning`.

## Daemon

Run a periodic task in another thread. Two modes: subclassing and callback.
The daemon is restartable — call `start()` after `stop()` to run it again.

### Usage as Subclass Mode

- Subclass `Daemon`.
- Call `super().__init__()`.
- Override the `on_process` method with your own.
- Add the logic you want to run inside `on_process`.
- Ensure your methods are thread-safe to avoid race conditions.
- `self.lock` is available for `lock.acquire()` / your logic / `lock.release()`.
- Call `start()` to run `on_process` in a new thread.
- Call `stop()` to finish the thread.

Check [sample_clock.py](https://github.com/erromu/minibone/blob/main/samples/sample_clock.py) for a sample.

### Usage as Callback Mode

- Instantiate `Daemon` by passing a callable.
- Add logic to your callable method.
- Ensure your callable is thread-safe.
- Call `start()` to run the callable in a new thread.
- Call `stop()` to finish the thread.

Check [sample_clock_callback.py](https://github.com/erromu/minibone/blob/main/samples/sample_clock_callback.py) for a sample.

### Behavior

- **First call is immediate.** `start()` runs `on_process` (or the callback)
  right away, then waits at least `interval` seconds between calls.
- **Exceptions do not kill the loop.** Any exception raised inside
  `on_process` is logged with a traceback, and the loop keeps running.
- **`stop()` is graceful and bounded.** It signals the loop and waits up to
  `stop_timeout` seconds (default 10s) for the current iteration to finish.
  This is independent of `interval` — a task with `interval=3600` shuts down
  in seconds, not hours.
- **Restartable.** After `stop()`, call `start()` again on the same instance.
- **`is_running()`** returns whether the worker thread is alive.
- **`sleep`** controls how often the loop wakes to check whether `interval`
  has elapsed. Lower values reduce latency; higher values reduce CPU. It is
  not the task interval.

### Parameters

| Name           | Type               | Default | Notes                                      |
| -------------- | ------------------ | ------- | ------------------------------------------ |
| `name`         | `str \| None`      | `None`  | Thread name, for debugging.                |
| `interval`     | `float`            | `60`    | Minimum seconds between calls. `>= 0`.     |
| `sleep`        | `float`            | `0.5`   | Poll granularity. `> 0`, typically `<= 1`. |
| `callback`     | `Callable \| None` | `None`  | Called instead of `on_process`.            |
| `iter`         | `int`              | `-1`    | Runs `iter` times, or forever if `-1`.     |
| `daemon`       | `bool`             | `True`  | Mark thread as daemon.                     |
| `stop_timeout` | `float`            | `10.0`  | Max seconds `stop()` waits.                |
| `**kwargs`     |                    |         | Forwarded to `on_process` / `callback`.    |

## AsyncDaemon

Same idea as `Daemon`, but runs as an `asyncio.Task` instead of a thread.
Use it when your periodic work is already async (DB, HTTP, etc.) and you
want to avoid a thread hop.

### Usage as Subclass Mode

- Subclass `AsyncDaemon`.
- Call `super().__init__()`.
- Override `on_process` (must be `async def`).
- `self.lock` is an `asyncio.Lock`; use `async with self.lock`.
- Call `await start()` to launch the task.
- Call `await stop()` to stop it.

Check [sample_async_clock.py](https://github.com/erromu/minibone/blob/main/samples/sample_async_clock.py) for a sample.

### Usage as Callback Mode

- Instantiate `AsyncDaemon` with an `async` callable.
- Call `await start()` to launch the task.
- Call `await stop()` to stop it.

Check [sample_async_clock_callback.py](https://github.com/erromu/minibone/blob/main/samples/sample_async_clock_callback.py) for a sample.

### Behavior

Same guarantees as `Daemon`:

- First call is immediate after `start()`.
- Exceptions in `on_process` are logged and do not kill the loop.
- `stop()` signals the loop, waits up to `stop_timeout` seconds for the
  current iteration to complete, then force-cancels if necessary.
- Restartable: `await start()` again after `await stop()`.
- `is_running()` reports whether the task is alive.

### Parameters

Identical to `Daemon`, minus `daemon` (there is no thread flag).

```python
import asyncio
from minibone.async_daemon import AsyncDaemon


async def tick():
    print("tick")


async def main():
    daemon = AsyncDaemon(name="tick", interval=1, callback=tick)
    await daemon.start()
    await asyncio.sleep(5)
    await daemon.stop()


asyncio.run(main())
```

## Emailer

Send emails through an SMTP server with a background queue. Enqueue from
request handlers or any thread; the worker delivers on its own schedule.

### Features

- Frozen, slotted dataclass queue items — no accidental mutation.
- Bounded `deque` with O(1) pop / appendleft for retries.
- Chunked sends over a single SMTP connection per `on_process` call.
- Transient (4xx) vs permanent (5xx) failure classification.
- Bounded retries, then discard. Logs each give-up.
- `Bcc` handled at the SMTP envelope level — never leaks as a header.
- Queue capacity limit to prevent unbounded growth.
- Graceful drain on `stop()` with a deadline.

### Usage

```python
from minibone.emailer import Emailer

emailer = Emailer(
    host="smtp.example.com",
    port=587,
    ssl=False,
    username="user@example.com",
    password="yourpassword",
)

emailer.start()

emailer.queue(
    from_address="me@domain.com",
    to="you@domain.com",
    subject="Notification",
    content_txt="This is a text notification",
    content_html="This is a <b>html</b> notification",
)

# ... your logic ...

emailer.stop()  # stops the worker and drains pending emails
```

### Parameters

| Name                    | Type          | Default  | Notes                           |
| ----------------------- | ------------- | -------- | ------------------------------- |
| `host`                  | `str`         |          | SMTP host.                      |
| `port`                  | `int`         |          | SMTP port.                      |
| `ssl`                   | `bool`        |          | `True` uses `SMTP_SSL`.         |
| `username` / `password` | `str \| None` | `None`   | Login credentials.              |
| `interval`              | `float`       | `1`      | Seconds between batches.        |
| `sleep`                 | `float`       | `0.5`    | Worker poll granularity.        |
| `chunk`                 | `int`         | `10`     | Max emails per batch.           |
| `max_retries`           | `int`         | `3`      | Retries for transient failures. |
| `timeout`               | `float`       | `10.0`   | SMTP socket timeout.            |
| `max_queue_size`        | `int`         | `10_000` | Enqueue fails past this.        |
| `drain_timeout`         | `float`       | `30.0`   | Seconds to drain on `stop()`.   |

## Logging

Set up a logger using UTC time that outputs logs to stdout or to a file.
It is friendly to file rotation (when setting output to a file).

```python
import logging

from minibone.logging import setup_log

if __name__ == "__main__":
    # setup_log must be called only once in your code.
    # You have to choose whether to log to stdout or to a file when calling it.

    setup_log(level="INFO")
    logging.info("This is a log to stdout")

    # Or call the next lines instead if you want to log into a file:
    # setup_log(file="sample.log", level="INFO")
    # logging.info('yay!')
```

## Contribution

- Feel free to clone this repository and send any pull requests.
- Add issues if something is not working as expected.
