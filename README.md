[![Check](https://github.com/erromu/minibone/actions/workflows/python-check.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-check.yml)  [![Deploy](https://github.com/erromu/minibone/actions/workflows/python-publish.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-publish.yml)

# minibone
Small boiler plate with tools for multithreading.

Minibone is a set of valuable classes for:

- __Daemon__: for multithreading tasks
- __Config__: To handle configuration setting
- Among others (I will add more later)

It will be deployed to PyPi when a new release is created

## Installation

> $ pip install minibone

## Usage

### Daemon

It is just another python class to do jobs / tasks in the background

#### Usage as SubClass

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

Allows to handle configuration settings in memory and persists them into toml/yaml/json format

> from minibone.config import Config
>
> cfg = Config(settings={"listen": "localhost", "port": 80}, filepath="config.toml")
> 
> cfg.add("debug", True)
>
> cfg.to_toml()
>
> cfg2 = Config.from_toml("config.toml")

## Contribution

- Feel free to clone this repository, and send any pull requests.
- Add issues if something is not working as expected.
