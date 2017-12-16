
# Intro

The Photorg project contains command line tools for organizing photos and videos in various formats.

## photorg

photorg recursively scans a source directory of photos using the very robust exiftool and extracts the creation date of each file.
The files are then grouped into directories by event date, such that each event directory contains all the sequence of photos such that the origination date of the photos is less than the configured gap (default 4 days). 


## photorg-deduplicate

photorg-deduplciate is a tool for scanning directories and removing all but the first occurrence of duplicate files. Files are hashed with the sha1 algorithm. The tool is designed to be compatible with common Linux utilities (ssh, find, sha1sum) such that it can discover duplicate files on remote servers. 


# Build

python setup.py build

# Install

sudo python setup.py install

# Clean

python setup.py clean

# Usage

photorg -h  
photorg /tmp/photos ~/photos
photorg --gap 2 
photorg --progress /tmp/photos ~/photos
photorg -v /tmp/photos ~/photos
photorg -vvv -log /tmp/logfile /tmp/photos ~/photos


