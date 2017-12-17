#!/usr/bin/python

import os
import sys
import json
import logging 

from datetime import datetime
from multiprocessing import Pool, cpu_count
from subprocess import Popen, PIPE
from common import *



def new_event_dir(base, date):
    """
    Create a directory, inside base dir, named by date, if not already exists
    """
    event_dir = os.path.join(base, date.strftime("%Y-%m-%d"))
    if not os.path.exists(event_dir):
        os.makedirs(event_dir, 0755)
        logging.info("New Event: {0}".format(event_dir))
    return event_dir




def is_duplicate_file(source, directory):
    """check for any files in the target directory with the same hash as the source file"""
    source_hash = sha1sum(source)
    for path in ls(directory, relative=False):
        if sha1sum(path) == source_hash:
            return True
    return False


def get_unique_filename(path):
    """
    find a unique filename based on the path such that the file does not already exist.
    In order to be idempotent, make sure existing files are actually different.
    """
    dirname = os.path.dirname(path)
    name,ext = os.path.splitext(os.path.basename(path))
    counter = 1
    name_base = name
    path_hash = None

    # start counter at value in current filename if any
    name_split = name.rsplit('-',1)
    if len(name_split) == 2:
        try:
            counter = int(name_split[1])
            name_base = name_split[0]

        except ValueError as e:
            pass

    # now iterate until a usable name is found
    for i in range(counter, counter+255):
        new_name = "{b}-{c}{e}".format(b=name_base, c=str(i), e=ext)
        new_path = os.path.join(dirname, new_name)
        if not os.path.exists(new_path):
            return new_path

    else:
        raise Exception('Error: could not find unique filename')



def exiftool_json(path):
    """
    Run exiftool to extract embedded EXIF data from images and movies.
    Exiftool supports significantly more file types, raw photos, movies than any available python lib
    Returns json
    """
    # make sure the preview file doesn't already exist
    logging.info('Running exiftool')
    p = Popen(['/usr/bin/exiftool', '-recurse', '-json', path], stdout=PIPE, stderr=PIPE)
    out,err = p.communicate()
    if err:
        logging.info(', '.join(x.strip() for x in str(err).split('\n') if x))
    return out



def date_sorted_paths(source_dir):
    """
    Run exiftool on directory and parse EXIF data JSON output
    Sort all files that have EXIF data by datetime object
    return [(date,path)] 
    """
    date_path_list = []
    
    try:
        exif_list = json.loads(exiftool_json(source_dir))
    except ValueError as e:
        logging.error("Could not parse exiftool json: {0}".format(str(e)))
        sys.exit(1)

    for exif in exif_list:
        try:
            # DateTimeOriginal is shutter time (not set for movies), CreateDate is file origination time 
            path = os.path.realpath(exif['SourceFile'])
            date = datetime.strptime(exif['CreateDate'], '%Y:%m:%d %H:%M:%S')
            date_path_list.append((date,path))
        except KeyError as e:
            logging.error("EXIF Error ({0}): {1}".format(str(e).strip("'"), path))

    logging.info('{n} files have EXIF data'.format(n=len(date_path_list)))
    return sorted(date_path_list, key=lambda x: x[0])


    

def organize_by_event(source_dir, dest_dir, day_delta=4, hardlink=False, delete=False, rename=False, progress=False): 
    """
    walk files in source_dir and extract CreateDate from EXIF data using Exiftool
    Sort files by date and group into collection with time delta less than 4 days between
    copy files into dest_dir with a new directory for each collection
    """
    event_date = None
    event_dir = None
    dest = os.path.realpath(dest_dir)
    source = os.path.realpath(source_dir)
    date_paths = date_sorted_paths(source)
    count = 0
    total = len(date_paths)

    # iterate over (date,path) sorted by date
    for date,path in date_paths:

        # first iteration: initialize date and create event dir
        if not event_date: 
            event_date = date
            event_dir = new_event_dir(dest, event_date)

        # decide if time delta is large enough to start a new event
        delta = date - event_date 
        if delta.days > day_delta:
            # new event, create event directory 
            event_date = date
            event_dir = new_event_dir(dest, event_date)

        # copy file to event_dir 
        target_path = os.path.join(event_dir, os.path.basename(path))
        try:
            copy_file(path, target_path, hardlink=hardlink, delete=delete)

        # if there is a collision, choose a different name in the event dir and try again
        except FileCollisionError as e:
            if rename:
                # but first make sure we didn't already do this once
                if not is_duplicate_file(path, event_dir):
                    renamed_path = get_unique_filename(target_path)
                    copy_file(path, renamed_path, hardlink=hardlink, delete=delete)
            else:
                logging.error('Error: {0}'.format(str(e)))

        # update progress, use carriage return to update terminal line
        if progress: sys.stderr.write("{0}/{1}         \r".format(count, total))
        count += 1




