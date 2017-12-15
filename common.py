
"""
common utility functions
"""

import os, hashlib
from shutil import copyfile




def sha1sum(path, blocksize=4096):
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



def ls(path, relative=True, hidden=False, recursive=True, isfile=False):
    """
    walk directory and yield paths to files
    files : only include regular files, ignore symlinks, etc.
    recursive : decend into children directories
    hidden : whether or not to include hidden files

    """
    base = realpath(path) 

    for root, dirs, files in os.walk(base, topdown=True):

        # skip hidden directories
        for dname in dirs:
            if not hidden and dname.startswith('.'):
                dirs.remove(dname)

        for name in files:
            path = os.path.join(root,name)

            # skip hidden files 
            if not hidden and name.startswith('.'):
                continue

            # skop non-regular files
            if isfile and not os.path.isfile(path):
                continue

            if relative:
                yield os.path.relpath(path, base)

            else:
                yield path

        # exit after first loop if not recursive
        if not recursive:
            break


class multidict(dict):
    """ a multi-dictionary that appends to a list for each key"""
    def __setitem__(self, key, value):
        self.setdefault(key, []).append(value)





class FileCollisionError(Exception):
    pass



def copy_file(source, target, target_is_dir=False, verbose=False):
    """
    Copy source file to target directory. 
    On unix, first try to hard-link. If that fails, perform regular copy.

    source := file to copy
    target := destination path 
    target_is_dir := copy the source file to the target directory and perserve filename

    """

    # first make sure that the source path exists:
    if not os.path.isfile(source):
        raise Exception('File does not exist (or is not a regular file): ' + source)

    # target could be a file or directory, expand path as appropriate
    if target_is_dir:
        target_dir = target
        target_path = os.path.join(target, os.path.basename(source))

    else: 
        target_dir = os.path.dirname(target)
        target_path = target

    # create directory if it doesn't exist
    if not os.path.isdir(target_dir):
        # if this raises an exception then something is actually wrong
        # probably target_is_dir was used incorrectly
        os.makedirs(target_dir, 0755)

    # if the target file already exists, check if the it's different
    if os.path.exists(target_path):

        if os.path.samefile(source, target_path):
            # files are the same inode, can safely skip
            return

        # check if they have the same size
        elif os.stat(source).st_size == os.stat(target_path).st_size:

            # check if they are the same hash
            if sha1sum(source) != sha1sum(target_path):
                # file exists but has different hash
                raise FileCollisionError('Destination file exists but has different hash: {src}, {dest}\n'.format(src=source, dest=target_path))

        else:
            # target file exists but is a different size
            raise FileCollisionError('Destination file exists and is different size: {src}, {dest}\n'.format(src=source, dest=target_path))


    # file did not already exist
    else:

        # create a hardlink on unix
        try:
            os.link(source, target_path)
            if verbose: print "Linking: {s} -> {t}".format(s=source, t=target_path)

        # otherwise, copy the file
        except OSError as e:
            if verbose: print "Copying: {s} -> {t}".format(s=source, t=target_path)
            copyfile(source, target_path)


