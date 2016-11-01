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

# global flag to show we did/didn't last output a \n to stderr
SYS_STDERR_CR = True

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


#   SYS_STDERR_CR is only useful if we are breaking out of the program or
#   something, and want to preserve the last thing printed
#
#def stderr_printf( pr_str, flush=True ):
#    global SYS_STDERR_CR
#
#    if not SYS_STDERR_CR:
#        print( "\b"*80, file=sys.stderr, flush=True, end="" )
#    
#    print( pr_str, file=sys.stderr, flush=flush, end="" )
#
#    SYS_STDERR_CR = pr_str.endswith("\n")


# alternate version with no global
def stderr_printf( pr_str, flush=True, preserve_prev_line=False ):
    if preserve_prev_line:
        print( "\n", file=sys.stderr, flush=True,end="" )
    else:
        print( "\b"*80 + " "*80 + "\b"*80, file=sys.stderr, flush=True,end="" )

    print( pr_str, file=sys.stderr, flush=flush, end="" )


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
            stderr_printf( "Can't stat "+fullfilename+"\n" )
            stderr_printf( "(" + sys.exc_info()[0].__name__ + ")\n" )
            stderr_printf( "Using os.path.getsize\n")
            size = os.path.getsize(fullfilename)
    except KeyboardInterrupt:
        # actually stop if ctrl-c
        raise
    except:
        size=0
        stderr_printf( "Can't read "+fullfilename+"\n" )
        stderr_printf( "(" + sys.exc_info()[0].__name__ + ")\n" )
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


def index_dir( treeroot, exclude_path ):
    # init main dictionary
    sizedict = {}
    filesdone = 0
    if exclude_path:
        exclude_path = re.escape(exclude_path)

    # TODO: a timeout "watchdog timer" thread to see if we have hung on
    #       some crappy nfs problem?
    for (root,dirs,files) in os.walk(treeroot):
        # add in directories to list of files in this dir
        if exclude_path and re.search(exclude_path,root):
            stderr_printf( "skipping root "+root+"\n" )
            continue
        # remove anything matching exclude from dirs, will prevent
        #   os.walk from searching there! (slice or del)
        if exclude_path:
            for thisdir in dirs:
                if re.search(exclude_path, os.path.join(root,thisdir)):
                    stderr_printf( "removing "+thisdir+" from dirs\n" )
                    dirs.remove(thisdir)
        
        files.extend(dirs)

        for filename in files:
            # full path to filename
            fullfilename = os.path.join(root,filename)

            if exclude_path and re.search(exclude_path,fullfilename):
                stderr_printf( "skipping file "+fullfilename+"\n" )
                continue

            size = getfilesize(fullfilename)
            
            # add this file or dir's size to itself and every parent dir
            #   in sizedict, so dirs include total size of files below
            # TODO: this fails if treeroot is /
            while len(fullfilename) >= len(treeroot):
                sizedict[fullfilename] = sizedict.get(fullfilename,0) + size
                (fullfilename,tail) = os.path.split(fullfilename)
            filesdone+=1
            if filesdone % 1000 == 0:
                stderr_printf( str(filesdone)+" files processed." )

    # now add in size of root dir
    sizedict[treeroot] = ( sizedict.get(treeroot,0) + getfilesize(treeroot) )
    filesdone+=1

    # report final tally of files
    stderr_printf( str(filesdone)+" files processed.\n" )
    print( str(filesdone)+" files processed." )

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
        stderr_printf( "filtering by size...\n" )
        filter_thresh(sizedict, filter)
    # take dict and sort
    stderr_printf( "sorting...\n" )
    sort_start_time = time.time()
    fileitems = list(sizedict.items())
    fileitems.sort(key=byitemvalalpha)

    # maximum length in characters of the size string
    if args.kilobyte:
        maxsizelen = 9
    else:
        maxsizelen = 8

    print_start_time = time.time()
    stderr_printf( "printing report...\n" )
    for (filename,filesize) in fileitems:
        if args.kilobyte:
            sizestr = "%.f" % (float(filesize)/1024)
        else:
            sizestr = size2eng(filesize)+"B"
        spacestr = " " * (maxsizelen - len(sizestr) )
        if os.path.isdir(filename):
            # add trailing slash to indicate a dir
            filename = filename + os.sep
        try:
            print( spacestr+sizestr+" "+filename )
        except UnicodeEncodeError:
            # sometimes os.walk will return an non-encodable-in-unicode
            #   string!  default error checking is 'strict' so we specify
            #   our own encoding with 'ignore' and decode back to unicode
            filename = filename.encode('utf-8','ignore').decode('utf-8')
            stderr_printf( "Bad Encoding: "+filename+"\n" )
            print( spacestr+sizestr+" "+filename )
    finish_time = time.time()

    elapsed = finish_time-start_time
    file_catalog_elapsed = file_catalog_done_time - start_time
    filter_elapsed = sort_start_time - file_catalog_done_time
    sort_elapsed = print_start_time - sort_start_time
    print_elapsed = finish_time - print_start_time

    stderr_printf("Elapsed time: %.fs\n" % elapsed )

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
        stderr_printf( "Aborted by Keyboard Interrupt\n",
                preserve_prev_line=True )
        status = 130

    sys.exit(status)

# vim: sts=4 et sw=4
