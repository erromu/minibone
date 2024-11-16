# minibone

[![Check](https://github.com/erromu/minibone/actions/workflows/python-check.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-check.yml)  [![Deploy](https://github.com/erromu/minibone/actions/workflows/python-publish.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-publish.yml) [![PyPI version](https://badge.fury.io/py/minibone.svg)](https://pypi.org/project/minibone)

minbone is a small boiler plate with tools for multithreading and others.

- __Config__: To handle configuration setting
- __Daemon__: For multithreading tasks
- __Logging__: To setup a logger friendly with filerotation 
- Among others (I will add more later)

It will be deployed to PyPi when a new release is created

## Installation

```shell

pip install minibone

```

## Config

Allows to handle configuration settings in memory and/or persist them into toml/yaml/json formats

```python

from minibone.config import Config

# Create a new set of settings and persist them
cfg = Config(settings={"listen": "localhost", "port": 80}, filepath="config.toml")	
cfg.add("debug", True)	
cfg.to_toml()

# Load settings from a file. Defaults can be set. More information: help(Config.from_toml)
cfg2 = Config.from_toml("config.toml")

# also there are async counter part methods
import asyncio

cfg3 = asyncio.run(Config.aiofrom_toml("config.toml"))
```


Usually config files are editted externaly then loaded as read only on your code, so in such case, you may want to subclass Config for easier usage


```python

from minibone.config import Config

class MyConfig(Config):

    def __init__(self):
        defaults = {"main": {"listen": "localhost", "port": 80}}
        settings = Config.from_toml(filepath="config.toml", defaults=defaults)
        super().__init__(settings=settings)

    def listen(self) -> str:
        return self["main"]["listen"]

    def port(self) -> int:
        return self["main"]["port"]

if __name__ == "__main__":
    cfg = MyConfig()
    print(cfg.port())
    # it will print the default port value if not port setting was defined in config.toml

```

## Logging

It allows to setup a logger using UTC time that outputs to stderr or to a file.
It is friendly to filerotation when setting output to a file

```python

import logging

from minibone.logging import setup_log

if __name__ == "__main__":

    # setup_log must be called only once in your code.
    # So you have to choice if logging to stderr or to a file when calling it

    setup_log(level="INFO")
    logging.info('This is a log to the stderr')

    # or call the next lines instead if you want to log into a file
    # setup_log(file="sample.log", level="INFO")
    # logging.info('yay!')

```

## Daemon

It is just another python class to do jobs / tasks in the background using threads. It can be used in two modes: subclasing and callback

#### Usage as SubClass mode

- Subclass Daemon
- call super().__init__() in yours
- Overwrite on_process method with yours
- Add logic you want to run inside on_process
- Be sure your methods are safe-thread to avoid race condition
- self.lock is available for { lock.acquire => your_logic => lock.release }
- call start() method to keep running on_process in a new thread
- call stop() to finish the thread

Check [sample_clock.py](https://github.com/erromu/minibone/blob/main/src/minibone/sample_clock.py) for a sample

#### Usage as callback mode

- Instance Daemon by passing a callable
- Add logic to your callable method
- Be sure your callable and methods are safe-thread to avoid race condition
- call start() method to keep running callable in a new thread
- call stop() to finish the thread

Check [sample_clock_callback.py](https://github.com/erromu/minibone/blob/main/src/minibone/sample_clock_callback.py) for a sample



## Contribution

- Feel free to clone this repository, and send any pull requests.
- Add issues if something is not working as expected.
