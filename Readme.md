
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

# Install 

## Required packages
sudo apt-get install exiftool

## From outside the project directory
sudo pip install photorg

## From the directory containing setup.py
sudo pip install .

## Verify
pip show photorg

## Uninstall
sudo pip uninstall photorg

## Developer install, add project folder to python path
sudo pip install -e .

# Usage Examples

photorg -h 
photorg ~/photos/unorganized/ ~/photos/organized/
photorg --gap 2 --progress --log log.txt unorganized/ organized/
photorg -v /tmp/photos ~/photos
photorg -vvv -log /tmp/logfile unorganized/ organized/


