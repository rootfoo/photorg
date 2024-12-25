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

logger = logging.getLogger('photorg')


VIDEO_FILE_EXTENSIONS = ['webm', 'mkv', 'flv', 'vob', 'ogv', 'ogg', 'rrc', 'gifv', 'mng', 'mov', 'avi', 'qt', 'wmv', 
                          'yuv', 'rm', 'asf', 'amv', 'mp4', 'm4p', 'm4v', 'mpg', 'mp2', 'mpeg', 'mpe', 'mpv', 'm4v', 
                          'svi', '3gp', '3g2', 'mxf', 'roq', 'nsv', 'flv', 'f4v', 'f4p', 'f4a', 'f4b', 'mod', 'mts']

RAW_FILE_EXTENSIONS = ['3fr', 'ari', 'arw', 'bay', 'braw', 'crw', 'cr2', 'cr3', 'cap', 'data', 'dcs', 'dcr', 'dng', 
                       'drf', 'eip', 'erf', 'fff', 'gpr', 'iiq', 'k25', 'kdc', 'mdc', 'mef', 'mos', 'mrw', 'nef', 
                       'nrw', 'obm', 'orf', 'pef', 'ptx', 'pxn', 'r3d', 'raf', 'raw', 'rwl', 'rw2', 'rwz', 'sr2', 
                       'srf', 'srw', 'tif', 'x3f']

IMAGE_FILE_EXTENSIONS = ['jpg', 'jpeg', 'jxl', 'png', 'gif', 'webp', 'tiff', 'heif', 'bmp', 'xcf', 'svg', 'img', 'avif']

PHOTO_FILE_EXTENSIONS = RAW_FILE_EXTENSIONS + IMAGE_FILE_EXTENSIONS



def new_event_dir(base, date, date_fmt="%Y/%Y-%m-%d"):
    """
    Create a directory, inside base dir, named by date, if not already exists
    """
    event_dir = os.path.join(base, date.strftime(date_fmt))
    if not os.path.exists(event_dir):
        os.makedirs(event_dir, 0o755)
        logger.info("New Event: {0}".format(event_dir))
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
    logger.debug('Running exiftool')
    p = Popen(['/usr/bin/exiftool', '-recurse', '-dateFormat', "%Y-%m-%d %H:%M:%S", '-json', path], stdout=PIPE, stderr=PIPE)
    out,err = p.communicate()
    
    if err:
        for msg in err.decode().strip().split('\n'):
            logger.warning("exiftool: " + msg.strip())
    return out



def run_cmd(argcv=[]):
    program = argcv[0]
    logger.debug('Running {0}'.format(program))
    p = Popen(argcv, stdout=PIPE, stderr=PIPE)
    out,err = p.communicate()
    if err:
        for msg in err.decode().strip().split('\n'):
            logger.warning("{0}: {1}".format(program, msg.strip()))
    return out



def ffprobe_json(path):
    """run ffprobe to get metadata from video formats"""
    return run_cmd(["/usr/bin/ffprobe", "-v", "quiet", "-of", "json", "-show_entries", "format", path])



def file_format(path):
    """check if file extension is a known video file"""
    parts = os.path.splitext(path)
    if len(path) > 1:
        ext = parts[1].lower().strip(".")
        if ext in VIDEO_FILE_EXTENSIONS:
            return 'VIDEO'
        elif ext in PHOTO_FILE_EXTENSIONS:
            return 'PHOTO'
    return 'OTHER'




def date_sorted_paths(source_dir):
    """
    Run exiftool on source directory and parse photo EXIF data JSON output. 
    Walk directory and run ffprobe on video files. Then sort and return [(path,date)].
    """
    path_date_dict = {}
    photo_count = 0
    video_count = 0
    other_count = 0
    exif_count = 0
    ffprobe_count = 0

    # images 
    try:
        exif_list = json.loads(exiftool_json(source_dir))
    except ValueError as e:
        logger.error("Could not parse exiftool json: {0}".format(str(e)))
        logger.exception(str(e))
        sys.exit(1)

    for exif in exif_list:
        try:
            # DateTimeOriginal is shutter time; CreateDate is file origination time
            # MTS movies from Sony have DateTimeOriginal
            # AVI movies from Olympus cameras have DateTimeOriginal
            path = os.path.realpath(exif['SourceFile'])
            date_str = ''
            if 'DateTimeOriginal' in exif:
                date_str = exif['DateTimeOriginal']
            elif 'CreateDate' in exif:
                date_str = exif['CreateDate']
            else:
                logger.error("EXIF has no CreateDate or DateTimeOriginal for {0}".format(path))
                continue

            creation_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            if path not in path_date_dict:
                path_date_dict[path] = creation_date
                exif_count += 1
        
        except (KeyError, ValueError) as e:
            logger.error("EXIF {0}: {1}".format(str(e).strip("'"), path))
            logger.exception(str(e))

    # videos
    for root, dirs, files in os.walk(source_dir):
        for name in files:
            format = file_format(name)
            path = os.path.join(root,name)

            if format == 'VIDEO':
                video_count += 1
                creation_date = None
                try:
                    out = ffprobe_json(path)
                    js = json.loads(out)
                    creation_str = js['format']['tags']['creation_time'] # e.g. 2024-10-27T18:55:15.000000Z
                    creation_date = datetime.strptime(creation_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                    if path not in path_date_dict:
                        path_date_dict[path] = creation_date
                        ffprobe_count += 1
                except Exception as e:
                    logger.error("Video without metadata: {0}".format(path))
                    logger.exception(str(e))
                finally:
                    logger.info("ffprobe {0} --> {1}".format(path, str(creation_date)))
            
            elif format == 'PHOTO':
                photo_count += 1
                if path not in path_date_dict:
                    logger.warning("Photo without metadata: {0}".format(path))
            else:
                other_count += 1


    logger.info('File statistics: {0} photos, {1} videos, {2} other'.format(photo_count, video_count, other_count))
    total_media = photo_count + video_count
    if len(path_date_dict) != total_media:
        logger.warning("{0} of {1} media files do not have date metadata".format(total_media - len(path_date_dict), total_media))
    else:
        logger.info("All {0} media files have date metadata".format(total_media))
    
    return sorted(path_date_dict.items(), key=lambda x: x[1])



def organize_by_event(source_dir, dest_dir, day_delta=4, hardlink=False, delete=False, rename=False, progress=False, simulate=False):
    """
    walk files in source_dir and extract CreateDate from EXIF data using Exiftool
    Sort files by date and group into collection with time delta less than 4 days between
    copy files into dest_dir with a new directory for each collection
    """
    count = 0
    event_date = None
    event_dir = None
    dest = os.path.realpath(dest_dir)
    source = os.path.realpath(source_dir)
    
    # walk the filesystem, read metadata
    path_dates = date_sorted_paths(source)
    total = len(path_dates)

    # iterate over (date,path) sorted by date
    for path,date in path_dates:
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
        if not simulate:
            try:
                logger.info("Copying ({c}/{n}): {s} --> {t}".format(c=count, n=total, s=source, t=target_path))
                copy_file(path, target_path, hardlink=hardlink, delete=delete)

            # if there is a collision, choose a different name in the event dir and try again
            except FileCollisionError as e:
                if rename:
                    # but first make sure we didn't already do this once
                    if not is_duplicate_file(path, event_dir):
                        renamed_path = get_unique_filename(target_path)
                        logger.info("Copying ({c}/{n}): {s} --> {t}".format(c=count, n=total, s=source, t=target_path))
                        copy_file(path, renamed_path, hardlink=hardlink, delete=delete)
                else:
                    logger.exception(str(e))

            # update progress, use carriage return to update terminal line
            #if progress: sys.stderr.write("{0}/{1}         \r".format(count, total))

    logger.info("Copied {0} of {1} files with date metadata".format(count, total))



def photorg_main():
    parser = argparse.ArgumentParser(description='Photo organization')
    parser.add_argument('SOURCE', help='directory to source photos')
    parser.add_argument('DEST', help='output directory for organized directories of photos')
    parser.add_argument('-v', '--verbose', action='count', help='verbosity level; -v=warn, -vv=info, -vvv=debug', default=0)
    parser.add_argument('--logfile', type=str, help='logging file')
    parser.add_argument('--syslog', action='store_true', help='log to syslog')
    parser.add_argument('--gap', type=int, default=4, help='The minimum number of days between events (default 4).')
    parser.add_argument('--hardlink', action='store_true', help='hardlink instead of copy')
    parser.add_argument('--delete', action='store_true', help='delete source file after copy')
    parser.add_argument('--rename', action='store_true', help='Resolve collisions (same path, different content) by renaming file')
    parser.add_argument('--progress', action='store_true', help='show progress')
    parser.add_argument('--simulate', action='store_true', help='No action; only perform a simulation of events that would occur')
    # TODO
    #parser.add_argument('--quiet', action='store_true', help='Supress all stderr/stdout messages (use with --log)')
    args = parser.parse_args()
   
    # set log level
    level = logging.ERROR
    if args.verbose == 1:
        level = logging.WARN
    elif args.verbose == 2:
        level = logging.INFO
    elif args.verbose >= 3:
        level = logging.DEBUG

    # also set level on root logger
    logger.setLevel(level)
    logging.getLogger().setLevel(level)
    
    # errors always go to stderr stream
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(sh)

    if args.logfile:
        # verbose messages go to log file
        fh = logging.FileHandler(args.logfile)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logger.addHandler(fh)
    
    if args.syslog:
        sysh = logging.handlers.SysLogHandler(address="/dev/log")
        sysh.setFormatter(logging.Formatter('%(name)s [%(levelname)s] %(message)s'))
        logger.addHandler(sysh)

    try:
        logger.info("photorg start")
        # organize and copy files from SOURCE into DEST
        organize_by_event(args.SOURCE, args.DEST, 
                day_delta=args.gap, 
                hardlink=args.hardlink, 
                delete=args.delete, 
                rename=args.rename, 
                progress=args.progress,
                simulate=args.simulate)
        logger.info("photorg done") 
    
    except Exception as e:
        logger.exception('Unhandled exception')
        logger.exception(e)



if __name__ == '__main__':
    photorg_main()
