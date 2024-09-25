"""This is a simple clock sample.

It prints current time each second using a SubClass of Daemon
"""

import time
from datetime import datetime

from daemon import Daemon


class Clock(Daemon):
    def __init__(self):
        super().__init__(name="Clock", interval=1, sleep=0.01)

    def on_process(self):
        print(datetime.now().strftime("%Y-%m-%d:%H:%M:%S"))


if __name__ == "__main__":
    try:
        print("Sample clock subclassing Daemon")
        print("Press ctrl+c to exit")
        clock = Clock()
        clock.start()

        while True:
            print("I am going to sleep. Do not disturb please")
            sleeping = 15
            time.sleep(sleeping)
            # clock will be running in the background in another thread
            print("I awoke after a long sleep of {%d} seconds in the main thread" % sleeping)

    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")

    except Exception as e:
        print("Error %s" % e)

    finally:
        clock.stop()
        print("Doing Shutdown")
