
"""
Find all duplicate files. Files are traversed in the order specified.
By default it will only list duplicates.
    
    --delete : DELETE ALL except the first occurance of duplicate files 
    --move : Move dupliates into specified directory
    --hardlink : Replace duplicates with hardlink to first occurance

To keep orginals in named directories and remove from everything else use bash globbing:
    https://www.gnu.org/software/bash/manual/bashref.html#Pattern-Matching
    photorg-deduplicate 2015-07-??_* 2015-07-?? 

To scan a directory on a remote server and delete local files which are also on server:

    ssh user@myserver find ~/photos -type f -exec 'sha1sum {} \;' > server_photo_sha1sums.txt
    photorg-deduplicate --from-file server_photo_sha1sums.txt ~/local_photos --delete

"""

import sys
import os
from common import *


def sha1sums(directories):
    """walk all directories and return a multidict keyed on sha1 digest"""
    md = multidict()
    # for each directory in directories
    for d in directories:
        # list all files and sort
        for path in sorted(ls(d, relative=False, isfile=True)):
            digest = sha1(path)
            # don't add paths to value list more than once
            # this will prevent accidentally deleting files if same dir specified more than once
            if (digest in md) and (path in md[digest]):
                continue
            else:
                # append to multidict
                md[digest] = path
    return md


def find_duplicates(directories):
    """
    scan each dir in directories and return a multidict keyed on digest.
    directories : list of paths to directories to scan
    """
    md = sha1sums(directories)
    # prune multidict, only keep files that are duplicates
    # use list() to iterate first so dict doesnt change size while pop()ing
    for digest,paths in list(md.iteritems()):
        if len(paths) < 2:
            md.pop(digest)
    
    return md


def find_duplicates_with_source(directories, source):
    """
    similar to find_duplicates but consider something a duplicate if the digest is also in "source"
    directories : list of paths to directories to scan
    source : a dictionary keyed on sha1 digest or a list of digests
    """
    # sha1 of all files in listed directories
    md = sha1sums(directories)
    # for digests in both dictionaries (using set operations)
    keys = source.viewkeys() & md.viewkeys()
    return multidict(filter(lambda x: x[0] in keys, md.iteritems()))



def print_duplicates(md):
    """
    print all paths grouped by sha1 digest with blank line between groups.
    """
    for digest,paths in md.iteritems():
        for p in paths:
            print digest, p
        # print blank line between groups
        print ""


def delete_duplicates(md, keep_first=True):
    """
    md : multidict key==digest and values is list of paths. aka md={sha1(path):[paths]}
    if keep_first==True, then preserve the first path in the list (do not delete).
    Warning: if keep_first==False, then ALL FILES WILL BE DELETED.
    """
    for digest,paths in md.iteritems():
        # do not delete the first path on the list
        keep_path = paths[0]
        # use sets to avoid deleting all files if paths occur multiple times in list
        delete_paths = set(paths)
        if keep_first:
            delete_paths.remove(keep_path)
            print "+ {d} {p}".format(d=digest, p=keep_path)
        for p in delete_paths:
            try:
                print "- {d} {p}".format(d=digest, p=p)
                os.unlink(p)
            except OSError as e:
                print "Error:" + str(e) 

        print ""







