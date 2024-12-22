#!/usr/bin/python

from __future__ import absolute_import
import logging.handlers
import os
import sys
import json
import logging 
import argparse

from datetime import datetime
from multiprocessing import Pool, cpu_count
from subprocess import Popen, PIPE
from .common import *


VIDEO_FILES_EXTENSIONS = ['webm', 'mkv', 'flv', 'vob', 'ogv', 'ogg', 'rrc', 'gifv', 'mng', 'mov', 'avi', 'qt', 'wmv', 
                          'yuv', 'rm', 'asf', 'amv', 'mp4', 'm4p', 'm4v', 'mpg', 'mp2', 'mpeg', 'mpe', 'mpv', 'm4v', 
                          'svi', '3gp', '3g2', 'mxf', 'roq', 'nsv', 'flv', 'f4v', 'f4p', 'f4a', 'f4b', 'mod']


def new_event_dir(base, date, date_fmt="%Y/%Y-%m-%d"):
    """
    Create a directory, inside base dir, named by date, if not already exists
    """
    event_dir = os.path.join(base, date.strftime(date_fmt))
    if not os.path.exists(event_dir):
        os.makedirs(event_dir, 0o755)
        logging.info("New Event: {0}".format(event_dir))
    return event_dir




def is_duplicate_file(source, directory):
    """check for any files in the target directory with the same hash as the source file"""
    source_hash = sha1(source)
    for path in ls(directory, relative=False):
        if sha1(path) == source_hash:
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
    p = Popen(['/usr/bin/exiftool', '-recurse', '-dateFormat', "%Y-%m-%d %H:%M:%S", '-json', path], stdout=PIPE, stderr=PIPE)
    out,err = p.communicate()
    
    if err:
        for msg in err.decode().strip().split('\n'):
            logging.info("exiftool: " + msg.strip())
    return out



def run_cmd(argcv=[]):
    program = argcv[0]
    logging.debug('Running {0}'.format(program))
    p = Popen(argcv, stdout=PIPE, stderr=PIPE)
    out,err = p.communicate()
    if err:
        for msg in err.decode().strip().split('\n'):
            logging.error("{0}: {1}".format(program, msg.strip()))
    return out



def ffprobe_json(path):
    """run ffprobe to get metadata from video formats"""
    return run_cmd(["/usr/bin/ffprobe", "-v", "quiet", "-of", "json", "-show_entries", "format", path])



def file_is_video(path):
    """check if file extension is a known video file"""
    parts = os.path.splitext(path)
    if len(path) > 1:
        ext = parts[1].lower().strip(".")
        if ext in VIDEO_FILES_EXTENSIONS:
            return True
    return False




def date_sorted_paths(source_dir):
    """
    Run exiftool on directory and parse EXIF data JSON output
    Sort all files that have EXIF data by datetime object
    return [(date,path)] 
    """
    date_path_list = []

    # images 
    try:
        exif_list = json.loads(exiftool_json(source_dir))
    except ValueError as e:
        logging.error("Could not parse exiftool json: {0}".format(str(e)))
        sys.exit(1)

    for exif in exif_list:
        try:
            # DateTimeOriginal is shutter time; CreateDate is file origination time
            # MTS movies from Sony have DateTimeOriginal
            # AVI movies from Olympus cameras have DateTimeOriginal
            path = os.path.realpath(exif['SourceFile'])
            date_key = 'DateTimeOriginal'
            if date_key not in exif:
                logging.warning("{0} not in EXIF for {1}".format(date_key, path))
                date_key = 'CreateDate'

            creation_date = datetime.strptime(exif[date_key], '%Y-%m-%d %H:%M:%S')
            date_path_list.append((creation_date,path))
        
        except (KeyError, ValueError) as e:
            logging.error("EXIF {0}: {1}".format(str(e).strip("'"), path))

    # videos
    for root, dirs, files in os.walk(source_dir):
        for name in files:
            if file_is_video(name):
                path = os.path.join(root,name)
                creation_date = None
                try:
                    out = ffprobe_json(path)
                    js = json.loads(out)
                    creation_str = js['format']['tags']['creation_time'] # e.g. 2024-10-27T18:55:15.000000Z
                    creation_date = datetime.strptime(creation_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                    date_path_list.append((creation_date,path))
                except Exception as e:
                    logging.error(e)
                finally:
                    logging.info("ffprobe {0} --> {1}".format(path, str(creation_date)))

    logging.info('{n} files have date metadata'.format(n=len(date_path_list)))
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
        count += 1
        
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

    logging.info("Copied {0} of {1} files with date metadata".format(count, total))



def photorg_main():
    parser = argparse.ArgumentParser(description='Photo organization')
    parser.add_argument('SOURCE', help='directory to source photos')
    parser.add_argument('DEST', help='output directory for organized directories of photos')
    parser.add_argument('-v', '--verbose', action='count', help='verbosity level; -v=warn, -vv=info, -vvv=debug', default=1)
    parser.add_argument('--logfile', type=str, help='logging file')
    parser.add_argument('--syslog', action='store_true', help='log to syslog')
    parser.add_argument('--gap', type=int, default=4, help='The minimum number of days between events (default 4).')
    parser.add_argument('--hardlink', action='store_true', help='hardlink instead of copy')
    parser.add_argument('--delete', action='store_true', help='delete source file after copy')
    parser.add_argument('--rename', action='store_true', help='Resolve collisions (same path, different content) by renaming file')
    parser.add_argument('--progress', action='store_true', help='show progress')
    # TODO
    #parser.add_argument('--quiet', action='store_true', help='Supress all stderr/stdout messages (use with --log)')
    args = parser.parse_args()
   
    # set log level
    if args.verbose == 1:
        level = logging.WARN
    elif args.verbose == 2:
        level = logging.INFO
    elif args.verbose >= 3:
        level = logging.DEBUG
    else:
        level = logging.ERROR

    # set log level on root logger or INFO wont display
    logging.getLogger().setLevel(level)
    logger = logging.getLogger('photorg')
    
    # errors always go to stderr stream
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    sh.setLevel(level)
    logging.getLogger('').addHandler(sh)

    if args.logfile:
        # verbose messages go to log file
        fh = logging.FileHandler(args.logfile)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        fh.setLevel(level)
        logging.getLogger('').addHandler(fh)
    
    if args.syslog:
        sysh = logging.handlers.SysLogHandler(address="/dev/log")
        sysh.setFormatter(logging.Formatter('photorg: [%(levelname)s] %(message)s'))
        sysh.setLevel(level)
        logging.getLogger('').addHandler(sysh)

    try:
        logging.info("photorg start")
        # organize and copy files from SOURCE into DEST
        organize_by_event(args.SOURCE, args.DEST, 
                day_delta=args.gap, 
                hardlink=args.hardlink, 
                delete=args.delete, 
                rename=args.rename, 
                progress=args.progress)
        logging.info("photorg done") 
    
    except Exception as e:
        logger.exception('Unhandled exception')
        logger.exception(e)



if __name__ == '__main__':
    photorg_main()
