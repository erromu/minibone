# minibone
Minibone is a set of common classes for:

- Multithreading
- Among others (I will add more later)

## Multithreading

It is Just another python class to do background jobs / tasks

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

Check clock.py for a sample

Usage callback mode
-------------------
- Instance Daemon by passing a callable
- Add logic to your callable method
- Be sure your callable and methods are safe-thread to avoid race condition
- call start() method to keep running callable in a new thread
- call stop() to finish the thread
"""

