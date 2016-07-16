#!/usr/bin/env python
"""
This is dirwalk.py,
Matt's very first python code of significance.
"""

import os
import os.path
import sys
import datetime
import time
from optparse import OptionParser

# main program
def main():
    #-----------------------
    # parse options
    usage = "usage: %prog [options] dir"
    parser = OptionParser(usage=usage)
    # defaults to using argv
    (options,args) = parser.parse_args()

    if len(args)< 1:
        treeroot = '.'
    else:
        treeroot = os.path.normpath(args[0])

    # parse threshold if present

    # print info to output
    print sys.argv[0]+" "+os.path.abspath(treeroot)
    print datetime.datetime.now().strftime("%a %b %d %Y   %I:%M%p")

    #-----------------------
    # main program

    start = time.time()

    # init main dictionary
    exists = {}
    dup = {}
    filesdone = 0

    for (root,dirs,files) in os.walk(treeroot):
        # add in directories to list of files in this dir
        files.extend(dirs)

        for filename in files:
            # full path to filename
            fullfilename = os.path.join(root,filename)
            fullfilename=fullfilename.lower()
            #print fullfilename
            if exists.get(fullfilename,0):
                dup[fullfilename]=1;
            exists[fullfilename] = 1
            
            filesdone+=1
            if filesdone % 1000 == 0:
                sys.stderr.write("\b"*40+str(filesdone)+" files processed.")

    filesdone+=1

    # report final tally of files
    sys.stderr.write("\b"*40+str(filesdone)+" files processed.\n")
    sys.stdout.write(str(filesdone)+" files processed.\n")

    for filename in dup.keys():
        print filename
    

    elapsed = time.time()-start
    sys.stderr.write("Elapsed time: %.fs\n" % elapsed)
    sys.stdout.write("Elapsed time: %.fs\n" % elapsed)

if __name__=="__main__":
    main()

# vim: sts=4 et sw=4
