#!/usr/bin/env python3
"""
This is dirwalk.py,
Matt's very first python code of significance.
"""

# TODO: don't catalog sockets or fifos (see finddup for more weird sys files)

import argparse
import datetime
import os
import os.path
import sys
import time

from durank import durank
from durank.durank import byitemvalalpha, eng2size, filter_thresh, index_dir, size2eng


def process_command_line(argv):
    """
    Return a 2-tuple: (settings object, args list).
    `argv` is a list of arguments, or `None` for ``sys.argv[1:]``.
    """
    argv = argv[1:]

    # initialize the parser object:
    parser = argparse.ArgumentParser(
        description="Search a path for the directories and files taking "
        "the most space and rank them."
    )

    # specifying nargs= puts outputs of parser in list (even if nargs=1)

    # required arguments
    parser.add_argument(
        "searchpaths", nargs="*", help="Search path(s) (recursively searched)."
    )

    # switches/options:
    parser.add_argument(
        "-t",
        "--thresh",
        dest="threshold",
        action="store",
        help="report only files, directories greater than THRESHOLD "
        "bytes.  Can use units, e.g. 2k, 2K, 1m, 1M, 2g, 2G, "
        "1T, etc.",
    )
    parser.add_argument(
        "-k",
        dest="kilobyte",
        action="store_true",
        help="report sizes in number of kB only",
    )
    parser.add_argument(
        "-x", dest="exclude", action="store", help="exclude paths with this string"
    )

    # (settings, args) = parser.parse_args(argv)
    args = parser.parse_args(argv)

    return args


# main program
def main(argv=None):
    args = process_command_line(argv)

    # TODO: search multiple paths if given
    #   1. normpath all paths
    #   2. eliminate paths that are children of any other path
    #   3. just run index_dir multiple times, and merge all resulting
    #       dicts into one with no post-processing
    if len(args.searchpaths) < 1:
        treeroot = "."
    else:
        treeroot = os.path.normpath(args.searchpaths[0])

    # print info to output
    print(os.path.basename(__file__) + " " + " ".join(sys.argv[1:-1]), end="")
    print(" " + os.path.abspath(treeroot))
    print(datetime.datetime.now().strftime("%a %b %d %Y   %I:%M%p"))

    # parse threshold if present
    if args.threshold:
        filter_val = eng2size(args.threshold)
        print("threshold=%sB" % size2eng(filter_val))
    else:
        filter_val = 0

    # -----------------------
    # main program

    start_time = time.time()

    # file crawling recursive sizer
    sizedict = index_dir(treeroot, args.exclude)

    file_catalog_done_time = time.time()

    # filter dict first before converting to list and sorting (efficiency)
    #   filtering is VERY FAST
    if filter_val > 0:
        durank.myerr.print("filtering by size...")
        filter_thresh(sizedict, filter_val)
    # take dict and sort
    durank.myerr.print("sorting...")
    sort_start_time = time.time()
    fileitems = list(sizedict.items())
    fileitems.sort(key=byitemvalalpha)

    # maximum length in characters of the size string
    if args.kilobyte:
        maxsizelen = 9
    else:
        maxsizelen = 8

    print_start_time = time.time()
    durank.myerr.print("printing report...")
    for filename, filesize in fileitems:
        if args.kilobyte:
            sizestr = "%.f" % (float(filesize) / 1024)
        else:
            sizestr = size2eng(filesize) + "B"
        spacestr = " " * (maxsizelen - len(sizestr))
        if os.path.isdir(filename) and filename != os.sep:
            # add trailing slash to indicate a dir
            filename = filename + os.sep
        try:
            print(spacestr + sizestr + " " + filename)
        except UnicodeEncodeError:
            # sometimes os.walk will return an non-encodable-in-unicode
            #   string!  default error checking is 'strict' so we specify
            #   our own encoding with 'ignore' and decode back to unicode
            filename = filename.encode(sys.stdout.encoding, "ignore").decode(
                sys.stdout.encoding
            )
            durank.myerr.print("Bad Encoding: " + filename)
            print(spacestr + sizestr + " " + filename)
    finish_time = time.time()

    elapsed = finish_time - start_time
    file_catalog_elapsed = file_catalog_done_time - start_time
    filter_elapsed = sort_start_time - file_catalog_done_time
    sort_elapsed = print_start_time - sort_start_time
    print_elapsed = finish_time - print_start_time

    durank.myerr.print("Elapsed time: %.fs" % elapsed)

    print("\nElapsed time: %.fs" % elapsed)
    print("    File Cataloging elapsed time: %.fs" % file_catalog_elapsed)
    if filter_val > 0:
        print("    Filtering elapsed time: %.fs" % filter_elapsed)
    print("    Sorting elapsed time: %.fs" % sort_elapsed)
    print("    Report Printing elapsed time: %.fs" % print_elapsed)

    # status OK
    return 0


def cli():
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        # stop watchdog timer
        if durank.WATCHDOG_TIMER:
            durank.WATCHDOG_TIMER.cancel()
        durank.myerr.print("Stopped by Keyboard Interrupt")
        status = 130
    except BrokenPipeError:
        # stop watchdog timer
        if durank.WATCHDOG_TIMER:
            durank.WATCHDOG_TIMER.cancel()
        durank.myerr.print("Broken Pipe")
        status = 1

    sys.exit(status)


if __name__ == "__main__":
    cli()

# vim: sts=4 et sw=4
