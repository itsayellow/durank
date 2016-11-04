#!/usr/bin/env python3
"""
This is dirwalk.py,
Matt's very first python code of significance.
"""

import os
import os.path
import sys
import datetime
import time
import argparse
import re
import threading


def watchdog_timeout():
    print(" Timeout.", file=sys.stderr)
    os._exit(1)
    #sys.exit(1)
    #raise Exception("Timeout due to hung file I/O")

# main program
def main( argv=None ):
    watchdog_timeout_sec = 1.0

    # threads can only be started once, so re-instance
    watchdog_timer =  threading.Timer(watchdog_timeout_sec, watchdog_timeout)
    watchdog_timer.start()

    time.sleep(10)

    # we're done, stop watchdog timer
    watchdog_timer.cancel()

if __name__=="__main__":
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        stderr_printf( "Stopped by Keyboard Interrupt\n",
                preserve_prev_line=True )
        status = 130

    sys.exit(status)

# vim: sts=4 et sw=4
