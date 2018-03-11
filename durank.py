#!/usr/bin/env python3
"""
This is dirwalk.py,
Matt's very first python code of significance.
"""

# TODO: don't catalog sockets or fifos (see finddup for more weird sys files)

import os
import os.path
import sys
import stat
import datetime
import time
import argparse
import re
import threading

# global flag to show we did/didn't last output a \n to stderr
#SYS_STDERR_CR = True
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
    return "%016d"%(1e15-x[1])+str(x[0])


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
        """Print to stderr, automatically knowing if we need a CR beforehand.
        """
        if text.startswith('\r'):
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

        if prkwargs.get('end', '\n') == '' and not text.endswith('\n'):
            self.need_cr = True
        else:
            self.need_cr = False


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
            size = statinfo.st_blocks*512
        except KeyboardInterrupt:
            # actually stop if ctrl-c
            raise
        except:
            # otherwise use stupid python getsize
            myerr.print("Can't stat "+fullfilename)
            myerr.print("(" + sys.exc_info()[0].__name__ + ")")
            myerr.print("Using os.path.getsize")
            size = os.path.getsize(fullfilename)
    except KeyboardInterrupt:
        # actually stop if ctrl-c
        raise
    except:
        size=0
        myerr.print("Can't read "+fullfilename)
        myerr.print("(" + sys.exc_info()[0].__name__ + ")")
    return size


# convert to string with units
#   use k=1024 for binary (e.g. kB)
#   use k=1000 for non-binary kW
def size2eng(size,k=1024):
    if   size > k**5:
        sizestr = "%.1fP" % (float(size)/k**5)
    elif size > k**4:
        sizestr = "%.1fT" % (float(size)/k**4)
    elif size > k**3:
        sizestr = "%.1fG" % (float(size)/k**3)
    elif size > k**2:
        sizestr = "%.1fM" % (float(size)/k**2)
    elif size > k:
        sizestr = "%.1fk" % (float(size)/k)
    else:
        sizestr = "%.1g" % (float(size))
    return sizestr


def eng2size(numstr):
    if numstr.endswith(("k","K")):
        num = int(numstr[:-1])*1024;
    elif numstr.endswith(("m","M")):
        num = int(numstr[:-1])*1024*1024;
    elif numstr.endswith(("g","G")):
        num = int(numstr[:-1])*1024*1024*1024;
    elif numstr.endswith(("t","T")):
        num = int(numstr[:-1])*1024*1024*1024*1024;
    elif numstr.endswith(("p","P")):
        num = int(numstr[:-1])*1024*1024*1024*1024*1024;
    else:
        num = int(numstr)
    return num


# delete all keys in sizedict that resolve to a number less than filter
# can operate on sizedict because it is a reference
def filter_thresh(sizedict, filter):
    filtered_keys = []
    for key in sizedict.keys():
        if sizedict[key] < filter:
            filtered_keys.append(key)
    for key in filtered_keys:
        sizedict.pop(key)


def process_command_line(argv):
    """
    Return a 2-tuple: (settings object, args list).
    `argv` is a list of arguments, or `None` for ``sys.argv[1:]``.
    """
    script_name = argv[0]
    argv = argv[1:]

    # initialize the parser object:
    parser = argparse.ArgumentParser(
            description="Search a path for the directories and files taking the most space and rank them." )

    # specifying nargs= puts outputs of parser in list (even if nargs=1)

    # required arguments
    parser.add_argument( 'searchpaths', nargs='*',
            help = "Search path(s) (recursively searched)."
            )

    # switches/options:
    parser.add_argument("-t", "--thresh", dest="threshold", action='store',
                help="report only files, directories greater than THRESHOLD bytes.  Can use units, e.g. 2k, 2K, 1m, 1M, 2g, 2G, 1T, etc."
                )
    parser.add_argument("-k", dest="kilobyte", action="store_true",
                help="report sizes in number of kB only"
                )
    parser.add_argument("-x", dest="exclude", action="store",
                help="exclude paths with this string"
                )

    #(settings, args) = parser.parse_args(argv)
    args = parser.parse_args(argv)

    return args


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
    myerr.print("Current dir:  %s" %(CURRENT_ROOT))
    myerr.print("Current file: %s" %(CURRENT_FILE))
    # os._exit better than sys.exit because it forces all threads to die now
    os._exit(1)


def index_dir( treeroot, exclude_path ):
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

    for (root,dirs,files) in os.walk(treeroot):
        # for debugging on hang
        CURRENT_ROOT = root

        # add in directories to list of files in this dir
        if exclude_path and re.search(exclude_path,root):
            myerr.print("skipping root "+root)
            continue
        # remove anything matching exclude from dirs, will prevent
        #   os.walk from searching there! (slice or del)
        if exclude_path:
            for thisdir in dirs:
                if re.search(exclude_path, os.path.join(root,thisdir)):
                    myerr.print("excluding: "+root+os.sep+thisdir)
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
            fullfilename = os.path.join(root,filename)

            if bad_filetype(fullfilename):
                myerr.print("Bad filetype: "+fullfilename)
                continue

            if exclude_path and re.search(exclude_path,fullfilename):
                myerr.print("skipping file "+fullfilename)
                continue

            size = getfilesize(fullfilename)
            
            # add this file or dir's size to itself and every parent dir
            #   in sizedict, so dirs include total size of files below
            while len(fullfilename) >= len(treeroot):
                sizedict[fullfilename] = sizedict.get(fullfilename,0) + size
                # if-else is a hack, because os.path.split('/')
                #   returns ('/',''), making an infinite loop
                if fullfilename == os.sep:
                    fullfilename = ''
                else:
                    (fullfilename,tail) = os.path.split(fullfilename)

            filesdone+=1
            if filesdone % 1000 == 0:
                myerr.print("\r"+str(filesdone)+" files processed.",
                        end="", flush=True)
                # reset watchdog timer
                WATCHDOG_TIMER.cancel()
                # threads can only be started once, so re-instance
                WATCHDOG_TIMER =  threading.Timer(
                        watchdog_timeout_sec, watchdog_timeout)
                WATCHDOG_TIMER.start()

    # we're done, stop watchdog timer
    WATCHDOG_TIMER.cancel()

    # now add in size of root dir
    sizedict[treeroot] = ( sizedict.get(treeroot,0) + getfilesize(treeroot) )
    filesdone+=1

    # report final tally of files
    myerr.print("\r"+str(filesdone)+" files processed.")
    print(str(filesdone)+" files processed.")

    return sizedict


# main program
def main( argv=None ):
    args = process_command_line(argv)

    # TODO: search multiple paths if given
    if len(args.searchpaths)< 1:
        treeroot = '.'
    else:
        treeroot = os.path.normpath(args.searchpaths[0])

    # print info to output
    print( os.path.basename(__file__) + " " + " ".join(sys.argv[1:-1]), end="" )
    print( " "+os.path.abspath(treeroot) )
    print( datetime.datetime.now().strftime("%a %b %d %Y   %I:%M%p") )

    # parse threshold if present
    if args.threshold:
        filter = eng2size(args.threshold)
        print( "threshold=%sB" % size2eng(filter))
    else:
        filter = 0

    #-----------------------
    # main program

    start_time = time.time()

    # file crawling recursive sizer
    sizedict = index_dir( treeroot, args.exclude )

    file_catalog_done_time = time.time()

    # filter dict first before converting to list and sorting (efficiency)
    #   filtering is VERY FAST
    if filter>0:
        myerr.print("filtering by size...")
        filter_thresh(sizedict, filter)
    # take dict and sort
    myerr.print("sorting...")
    sort_start_time = time.time()
    fileitems = list(sizedict.items())
    fileitems.sort(key=byitemvalalpha)

    # maximum length in characters of the size string
    if args.kilobyte:
        maxsizelen = 9
    else:
        maxsizelen = 8

    print_start_time = time.time()
    myerr.print("printing report...")
    for (filename,filesize) in fileitems:
        if args.kilobyte:
            sizestr = "%.f" % (float(filesize)/1024)
        else:
            sizestr = size2eng(filesize)+"B"
        spacestr = " " * (maxsizelen - len(sizestr) )
        if os.path.isdir(filename) and filename != os.sep:
            # add trailing slash to indicate a dir
            filename = filename + os.sep
        try:
            print( spacestr+sizestr+" "+filename )
        except UnicodeEncodeError:
            # sometimes os.walk will return an non-encodable-in-unicode
            #   string!  default error checking is 'strict' so we specify
            #   our own encoding with 'ignore' and decode back to unicode
            filename = filename.encode('utf-8','ignore').decode('utf-8')
            myerr.print("Bad Encoding: "+filename)
            print( spacestr+sizestr+" "+filename )
    finish_time = time.time()

    elapsed = finish_time-start_time
    file_catalog_elapsed = file_catalog_done_time - start_time
    filter_elapsed = sort_start_time - file_catalog_done_time
    sort_elapsed = print_start_time - sort_start_time
    print_elapsed = finish_time - print_start_time

    myerr.print("Elapsed time: %.fs" % elapsed )

    print("\nElapsed time: %.fs" % elapsed )
    print("    File Cataloging elapsed time: %.fs" %file_catalog_elapsed)
    if filter>0:
        print("    Filtering elapsed time: %.fs" % filter_elapsed )
    print("    Sorting elapsed time: %.fs" % sort_elapsed )
    print("    Report Printing elapsed time: %.fs" % print_elapsed )


if __name__=="__main__":
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        # stop watchdog timer
        if WATCHDOG_TIMER:
            WATCHDOG_TIMER.cancel()
        myerr.print( "Stopped by Keyboard Interrupt")
        status = 130

    sys.exit(status)

# vim: sts=4 et sw=4
