
"""
common utility functions
"""

import os, hashlib

def sha1(path, blocksize=4096):
    """return the sha1 hex digest of path"""
    with open(path) as f:
        block = f.read(blocksize)
        sha = hashlib.sha1()
        while block:
            sha.update(block)
            block = f.read(blocksize)
        digest = sha.hexdigest()
    return digest


def shasums(path):
    """walk directory and yield (sha1(path), path)"""
    for base,dirs,files in os.walk(source):
        for name in files:
            path = os.path.join(base, name)
            yield (sha1(path), path)


def joinpath(a, *p):
    """
    safer alternative to os.path.join. subpaths will stripped of leading /'s
    resulting path is a proper sub-directory
    """
    path = a.rstrip('/')
    for b in p:
        b = b.strip('./ ')
        path += '/' + b
    return path


def realpath(p):
    """expand user (~/foo) and return real path"""
    return os.path.realpath(os.path.expanduser(p))



def ls(path, relative=True, hidden=False, recursive=True):
    """walk directory and yield paths to files"""
    base = realpath(path) 

    for root, dirs, files in os.walk(base, topdown=True):

        # skip hidden directories
        for dname in dirs:
            if not hidden and dname.startswith('.'):
                dirs.remove(dname)

        for name in files:
            # skip hidden files 
            if not hidden and name.startswith('.'):
                continue
            
            if relative:
                yield os.path.relpath(os.path.join(root, name), base)

            else:
                yield os.path.join(root, name)
        
        # exit after first loop if not recursive
        if not recursive:
            break


class multidict(dict):
    """ a multi-dictionary that appends to a list for each key"""
    def __setitem__(self, key, value):
        self.setdefault(key, []).append(value)

