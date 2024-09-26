[![Check](https://github.com/erromu/minibone/actions/workflows/python-check.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-check.yml)  [![Deploy](https://github.com/erromu/minibone/actions/workflows/python-publish.yml/badge.svg)](https://github.com/erromu/minibone/actions/workflows/python-publish.yml)

# minibone
Minibone is a set of common classes for:

- Multithreading
- Among others (I will add more later)

## Deployed on PyPi

A deploy to PyPi will be triggered on each release for minibone package

## Installation

> $ pip install minibone

## Usage

### Daemon

It is just another python class to do jobs / tasks in the background

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

Check [sample_clock.py](https://github.com/erromu/minibone/blob/main/src/minibone/sample_clock.py) for a sample

Usage callback mode
-------------------
- Instance Daemon by passing a callable
- Add logic to your callable method
- Be sure your callable and methods are safe-thread to avoid race condition
- call start() method to keep running callable in a new thread
- call stop() to finish the thread

Check [sample_clock_callback.py](https://github.com/erromu/minibone/blob/main/src/minibone/sample_clock_callback.py) for a sample

## Contribution

- Feel free to clone this repository, and send any pull request.
- Add issues if something is not working as expected.