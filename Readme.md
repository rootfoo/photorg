
# Intro

The Photorg project contains Python command line tools for organizing photos by date and to safely manage data deduplication. 

## photorg

The photorg utility takes a directory of unorganized photos and copies them into a directory tree based on dates. The source directory is scanned with exiftool and extracts the creation date of each file. The files are then sorted and grouped into collections such that the time delta between photos in the collection is less than the configured gap (default 4 days). In other words, it iterates over the list of photos until the current photos was taken more than 4 days from the prior photo, then it starts a new collection.  

The tool was designed to be as safe and robust as possible in the following ways:

 * It should be incredibly difficult to accidentally delete photos or make unrecoverable mistakes
 * Exception handling and logging should gracefully handle edge cases
 * Destination photos with the same name should not be overwritten blindly
 * The delete option should only remove the source file after the destination file size has been verified
 * The tool should be as idempotent as possible

Earlier versions of this tool used python EXIF libraries which can only extract EXIF data from a small subset of photo formats (primarily JPEG). However, the very robust exiftool Perl program supports a significant variety of image formats, including RAW formats and videos and supports JSON output. 


## photorg-deduplicate

photorg-deduplciate is a tool for scanning directories and removing all but the first occurrence of duplicate files. Files are considered duplicate if they have the same SHA1 hash digest. The tool is designed to be compatible with common Linux utilities (ssh, find, sha1sum) such that directories can be compared to files on remote servers easily, in a bandwidth efficient manner, with ubiquitous tools.

The tool was designed to be as safe and robust as possible in the following ways;

 * By default it only scans and shows duplicate files
 * It should not be possible to delete all instances of a file (the first instance is never deleted)
 * Argument order controls directories from which files are deleted
 * Useful for file deduplication in general, not specific to photos or media
 * Designed to integrate with ubiquitous Linux tools such as ssh, find, and sha1sum for management of data on remote systems 

To prune empty directories
```find . -depth -type d -exec rmdir --ignore-fail-on-non-empty {} \; ```

# Install

## Prerequisites (Ubuntu 24.04)
```
sudo apt install python3-full pipx libimage-exiftool-perl python3-build python3-pip
```

## Build python packages (sdist and wheel)
Build the Python source and wheel packages from the repository. Then copy the wheel (.whl) file to the target host and proceed with installation.
```
python3 -m build
```

See also: https://packaging.python.org/en/latest/flow/ 


## Install package (wheel) for user / development
On Ubuntu `pipx` is preferred, but `pipx` and `pip` are interchangeable in the commands below.
```
pipx ensurepath

# install from wheel using pipx (for Ubuntu)
python3 -m pipx install dist/photorg-0.0.1-py3-none-any.whl

# verify
pipx show photorg
which photorg

# uninstall
pipx uninstall photorg
```


## Install package globally with pipx
```
pipx ensurepath

# Pipx install globally by setting environment variables
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install photorg-0.0.1-py3-none-any.whl 

# verify install (env vars need to be same as install)
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx list
which photorg
photorg --help

# uninistall
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx uninstall photorg
```

See also: https://pipx.pypa.io/stable/installation/ 



# Usage Examples
```
photorg -h 
photorg ~/photos/unorganized/ ~/photos/organized/
photorg --gap 2 --progress --log log.txt unorganized/ organized/
photorg -v /tmp/photos ~/photos
photorg -vvv -log /tmp/logfile unorganized/ organized/
```