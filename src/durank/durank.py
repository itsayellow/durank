"""
This is dirwalk.py,
Matt's very first python code of significance.
"""

# TODO: don't catalog sockets or fifos (see finddup for more weird sys files)

import os
import os.path
import re
import stat
import sys
import threading

# global flag to show we did/didn't last output a \n to stderr
# SYS_STDERR_CR = True
LAST_STDERR_STRLEN = 0
WATCHDOG_TIMER = False
CURRENT_ROOT = ""
CURRENT_FILE = ""

# x[1] is integer: sort decreasing
# then if equal,
# x[0] is string: sort increasing
def byitemvalalpha(x):
    """
    given the tuples from a dict (key,item) pairs
    sort based first on item, and if both items are the same
    sort by key
    """
    return "%016d" % (1e15 - x[1]) + str(x[0])


class StderrPrinter(object):
    r"""Prints to stderr especially for use with \r and same-line updates

    Keeps track of whether an extra \n is needed before printing string,
    especially in cases where the previous print string didn't have
    one and this print string doesn't start with \r

    Allows for easily printing error messages (regular print) amongst
    same-line updates (starting with \r and with no finishing \n).
    """

    def __init__(self):
        self.need_cr = False

    def print(self, text, **prkwargs):
        """Print to stderr, automatically knowing if we need a CR beforehand."""
        if text.startswith("\r"):
            self.need_cr = False
        # we need_cr if last print specifically didn't have a \n,
        #   and this one doesn't start with \r
        # Most likely last one was a progress display and this one is an
        #   error or warning.
        # Instead of printing on the end of the line after the progress
        #   line, it \n to the next line.
        # [It could just as easily be a \r to erase the previous line.]
        if self.need_cr:
            print("", file=sys.stderr)

        print(text, file=sys.stderr, **prkwargs)

        self.need_cr = prkwargs.get("end", "\n") == "" and not text.endswith("\n")


# Global
myerr = StderrPrinter()


# get size on disk (blocks*block_size) via lstat, but if we can't,
#   get size of file data
# TODO: add specific exceptions to except
def getfilesize(fullfilename):
    try:
        statinfo = os.lstat(fullfilename)
        try:
            # use blocks if possible
            # st_blocks is in units of 512-byte blocks
            size = statinfo.st_blocks * 512
        except KeyboardInterrupt:
            # actually stop if ctrl-c
            raise
        except AttributeError:
            # Windows has no st_blocks
            # if not available, use stupid python getsize
            size = os.path.getsize(fullfilename)
    except KeyboardInterrupt:
        # actually stop if ctrl-c
        raise
    except:
        size = 0
        myerr.print("Can't read " + fullfilename)
        myerr.print("(" + sys.exc_info()[0].__name__ + ")")
    return size


# convert to string with units
#   use k=1024 for binary (e.g. kB)
#   use k=1000 for non-binary kW
def size2eng(size, k=1024):
    if size > k ** 5:
        sizestr = "%.1fP" % (float(size) / k ** 5)
    elif size > k ** 4:
        sizestr = "%.1fT" % (float(size) / k ** 4)
    elif size > k ** 3:
        sizestr = "%.1fG" % (float(size) / k ** 3)
    elif size > k ** 2:
        sizestr = "%.1fM" % (float(size) / k ** 2)
    elif size > k:
        sizestr = "%.1fk" % (float(size) / k)
    else:
        sizestr = "%.1g" % (float(size))
    return sizestr


def eng2size(numstr):
    if numstr.endswith(("k", "K")):
        num = int(numstr[:-1]) * 1024
    elif numstr.endswith(("m", "M")):
        num = int(numstr[:-1]) * 1024 * 1024
    elif numstr.endswith(("g", "G")):
        num = int(numstr[:-1]) * 1024 * 1024 * 1024
    elif numstr.endswith(("t", "T")):
        num = int(numstr[:-1]) * 1024 * 1024 * 1024 * 1024
    elif numstr.endswith(("p", "P")):
        num = int(numstr[:-1]) * 1024 * 1024 * 1024 * 1024 * 1024
    else:
        num = int(numstr)
    return num


# delete all keys in sizedict that resolve to a number less than filter_val
# can operate on sizedict because it is a reference
def filter_thresh(sizedict, filter_val):
    filtered_keys = []
    for key in sizedict.keys():
        if sizedict[key] < filter_val:
            filtered_keys.append(key)
    for key in filtered_keys:
        sizedict.pop(key)


def bad_filetype(fullfilename):
    returnval = False
    try:
        # don't follow symlinks, just treat them like a regular file
        this_filestat = os.stat(fullfilename, follow_symlinks=False)
    except:
        myerr.print("Can't stat: " + fullfilename)
        return True

    if stat.S_ISFIFO(this_filestat.st_mode):
        # skip FIFOs
        returnval = True
    if stat.S_ISSOCK(this_filestat.st_mode):
        # skip sockets
        returnval = True

    return returnval


# TODO: print which dir we were hung on before exiting
def watchdog_timeout():
    myerr.print("Timeout due to hung file I/O")
    myerr.print("Current dir:  %s" % (CURRENT_ROOT))
    myerr.print("Current file: %s" % (CURRENT_FILE))
    # os._exit better than sys.exit because it forces all threads to die now
    os._exit(1)


def index_dir(treeroot, exclude_path):
    # use global so we can cancel thread for keyboard interrupt in __main__
    global WATCHDOG_TIMER
    global CURRENT_ROOT
    global CURRENT_FILE

    # init main dictionary
    sizedict = {}
    filesdone = 0
    # timeout for 1000 files processed in seconds
    watchdog_timeout_sec = 20.0

    if exclude_path:
        exclude_path = re.escape(exclude_path)

    # watchdog timer that unless canceled will raise Exception after sec
    #   to guard against file system hangs
    WATCHDOG_TIMER = threading.Timer(watchdog_timeout_sec, watchdog_timeout)
    WATCHDOG_TIMER.start()

    for (root, dirs, files) in os.walk(treeroot):
        # for debugging on hang
        CURRENT_ROOT = root

        # add in directories to list of files in this dir
        if exclude_path and re.search(exclude_path, root):
            myerr.print("skipping root " + root)
            continue
        # remove anything matching exclude from dirs, will prevent
        #   os.walk from searching there! (slice or del)
        if exclude_path:
            for thisdir in dirs:
                if re.search(exclude_path, os.path.join(root, thisdir)):
                    myerr.print("excluding: " + root + os.sep + thisdir)
                    dirs.remove(thisdir)
        # let's not index remote mounts (MacOS only...)
        #   TODO: check for mount points and skip those
        if root == os.sep and "Volumes" in dirs:
            myerr.print("excluding: " + os.sep + "Volumes")
            dirs.remove("Volumes")

        # Presumably we add dirs so we can get size of actual dir descriptor
        files.extend(dirs)

        for filename in files:
            # for debugging on hang
            CURRENT_FILE = filename

            # full path to filename
            fullfilename = os.path.join(root, filename)

            if bad_filetype(fullfilename):
                myerr.print("Bad filetype: " + fullfilename)
                continue

            if exclude_path and re.search(exclude_path, fullfilename):
                myerr.print("skipping file " + fullfilename)
                continue

            size = getfilesize(fullfilename)

            # add this file or dir's size to itself and every parent dir
            #   in sizedict, so dirs include total size of files below
            while len(fullfilename) >= len(treeroot):
                sizedict[fullfilename] = sizedict.get(fullfilename, 0) + size
                # if-else is a hack, because os.path.split('/')
                #   returns ('/',''), making an infinite loop
                if fullfilename == os.sep:
                    fullfilename = ""
                else:
                    (fullfilename, _) = os.path.split(fullfilename)

            filesdone += 1
            if filesdone % 1000 == 0:
                myerr.print(
                    "\r" + str(filesdone) + " files processed.", end="", flush=True
                )
                # reset watchdog timer
                WATCHDOG_TIMER.cancel()
                # threads can only be started once, so re-instance
                WATCHDOG_TIMER = threading.Timer(watchdog_timeout_sec, watchdog_timeout)
                WATCHDOG_TIMER.start()

    # we're done, stop watchdog timer
    WATCHDOG_TIMER.cancel()

    # now add in size of root dir
    sizedict[treeroot] = sizedict.get(treeroot, 0) + getfilesize(treeroot)
    filesdone += 1

    # report final tally of files
    myerr.print("\r" + str(filesdone) + " files processed.")
    print(str(filesdone) + " files processed.")

    return sizedict


# vim: sts=4 et sw=4
