# minibone

[![Check](https://github.com/erromu/minibone/actions/workflows/python-check.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-check.yml)  [![Deploy](https://github.com/erromu/minibone/actions/workflows/python-publish.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-publish.yml) [![PyPI version](https://badge.fury.io/py/minibone.svg)](https://pypi.org/project/minibone)

minbone is a small boiler plate with tools for multithreading and others.

- __Daemon__: for multithreading tasks
- __Config__: To handle configuration setting
- Among others (I will add more later)

It will be deployed to PyPi when a new release is created

## Installation

```shell

pip install minibone

```

## Usage

### Daemon

It is just another python class to do jobs / tasks in the background using threads. It can be used in two modes: subclasing and callback

#### Usage as SubClass mode

- Subclass Daemon
- call super().__init__() in yours
- Overwrite on_process method with yours
- Add logic you want to run inside on_process
- Be sure your methods are safe-thread to avoid race condition
- self.lock is available for lock.acquire / your_logic / lock.release
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

### Config

Allows to handle configuration settings in memory and/or persists them into toml/yaml/json formats

```python

from minibone.config import Config

# Create a new set of settings
cfg = Config(settings={"listen": "localhost", "port": 80}, filepath="config.toml")	
cfg.add("debug", True)	
cfg.to_toml()

# Load settings from a file. Defaults can be set. More information: help(Config.from_toml)
cfg2 = Config.from_toml("config.toml")

```

## Contribution

- Feel free to clone this repository, and send any pull requests.
- Add issues if something is not working as expected.
