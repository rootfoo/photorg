
# Intro

Photorg is a photo organizer that creates a directory structure based on EXIF date information.

this scans all the photos in the source directory (recursively) and organizis them into a folder strutcured based on date
an event is a series of photos without a day gap greater than 4 days (configurable)

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


