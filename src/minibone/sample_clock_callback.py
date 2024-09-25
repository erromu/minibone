"""This is a simple clock sample.

It prints current time each second using a Daemon callback
"""

import time
from datetime import datetime

from daemon import Daemon


def callback():
    print(datetime.now().strftime("%Y-%m-%d:%H:%M:%S"))


if __name__ == "__main__":
    try:
        print("Sample clock using Daemon callback for the task")
        print("Press ctrl+c to exit")
        clock = Daemon(name="Clock", interval=1, sleep=0.01, callback=callback)
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
