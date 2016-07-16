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
SYS_STDERR_RETURN = True

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

# get size on disk (blocks*512) but if we can't,
#   get size of file data
def getfilesize(fullfilename):
    global SYS_STDERR_RETURN
    try:
        statinfo = os.lstat(fullfilename)
        try:
            # use blocks if possible
            size = statinfo.st_blocks*512
        except:
            # otherwise use stupid python getsize
            size = os.path.getsize(fullfilename)
    except:
        size=0
        if not SYS_STDERR_RETURN:
            print( "\b"*40, file=sys.stderr, flush=True, end="" )
        print( "Can't read "+fullfilename, file=sys.stderr, flush=True )
        SYS_STDERR_RETURN = True
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
                help="report only files, directories greater than THRESHOLD B.  Can use units, e.g. 2k, 2K, 1m, 1M, 2g, 2G, 1T, etc."
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

# main program
def main( argv=None ):
    global SYS_STDERR_RETURN
    args = process_command_line(argv)

    # TODO: search multiple paths if given
    if len(args.searchpaths)< 1:
        treeroot = '.'
    else:
        treeroot = os.path.normpath(args.searchpaths[0])

    # parse threshold if present
    if args.threshold:
        filter = eng2size(args.threshold)
        print( "threshold=%sB" % size2eng(filter))
    else:
        filter = 0

    # print info to output
    print( sys.argv[0]+" "+os.path.abspath(treeroot) )
    print( datetime.datetime.now().strftime("%a %b %d %Y   %I:%M%p") )

    #-----------------------
    # main program

    start = time.time()

    # init main dictionary
    sizedict = {}
    filesdone = 0

    for (root,dirs,files) in os.walk(treeroot):
        # add in directories to list of files in this dir
        if args.exclude and re.search(args.exclude,root):
            if not SYS_STDERR_RETURN:
                print( "\b"*40, file=sys.stderr, flush=True, end="" )
            print( "skipping root "+root, file=sys.stderr, flush=True )
            SYS_STDERR_RETURN = True
            continue
        # remove anything matching exclude from dirs, will prevent
        #   os.walk from searching there! (slice or del)
        if args.exclude:
            for thisdir in dirs:
                if re.search(args.exclude, os.path.join(root,thisdir)):
                    if not SYS_STDERR_RETURN:
                        print( "\b"*40, file=sys.stderr, flush=True, end="" )
                    print( "removing "+thisdir+" from dirs",
                            file=sys.stderr, flush=True )
                    SYS_STDERR_RETURN = True
                    dirs.remove(thisdir)
        
        files.extend(dirs)

        for filename in files:
            # full path to filename
            fullfilename = os.path.join(root,filename)
            if args.exclude and re.search(args.exclude,fullfilename):
                if not SYS_STDERR_RETURN:
                    print( "\b"*40, file=sys.stderr, flush=True, end="" )
                print( "skipping file "+fullfilename,
                        file=sys.stderr, flush=True )
                SYS_STDERR_RETURN = True
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
                print( "\b"*40+str(filesdone)+" files processed.",
                        file=sys.stderr, flush=True, end="" )
                SYS_STDERR_RETURN = False

    # now add in size of root dir
    sizedict[treeroot] = sizedict.get(treeroot,0) + getfilesize(treeroot)
    filesdone+=1

    # report final tally of files
    print( "\b"*40+str(filesdone)+" files processed.", file=sys.stderr )
    print( str(filesdone)+" files processed." )

    # take dict and display sorted tally
    fileitems = list(sizedict.items())
    fileitems.sort(key=byitemvalalpha)

    # maximum length in characters of the size string
    if args.kilobyte:
        maxsizelen = 9
    else:
        maxsizelen = 8

    for (filename,filesize) in fileitems:
        if filesize >= filter:
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
                print( "Bad Encoding: "+filename, file=sys.stderr )
                print( spacestr+sizestr+" "+filename )

    elapsed = time.time()-start
    print("Elapsed time: %.fs" % elapsed, file=sys.stderr )
    print("Elapsed time: %.fs\n" % elapsed )

if __name__=="__main__":
    status = main(sys.argv)
    sys.exit(status)

# vim: sts=4 et sw=4
