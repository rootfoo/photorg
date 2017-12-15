#!/usr/bin/python

import pyexiv2
import argparse
import os
import sys
import hashlib
from shutil import copyfile
from datetime import datetime
from multiprocessing import Pool, cpu_count
from subprocess import Popen, PIPE


"""
prerequisites:
	python-exiv2 ufraw-batch


Note about the Exiv2 library
	pyexiv2 is depreciated in favor of gexiv2 (gobject based)
	this may cause cross platform issues


Metadata of interest

	Identification
		Exif.Image.ImageID 
		Exif.Photo.ImageUniqueID 
		Exif.Image.RawDataUniqueID 
		Exif.Image.OriginalRawFileName 
		Exif.Image.OriginalRawFileDigest 

	Location
		Iptc.Application2.City
		Iptc.Application2.SubLocation
		Iptc.Application2.ProvinceState
		Iptc.Application2.CountryCode
		Iptc.Application2.CountryName

	Caption
		Iptc.Application2.Headline
		Iptc.Application2.Caption

	Keywords
		Iptc.Application2.Keywords
		Iptc.Application2.Subject
		Iptc.Application2.Category
		Iptc.Application2.SuppCategory
	
	Rating
		Iptc.Application2.Urgency

	Resources
		http://www.exiv2.org/tags.html
		http://exiv2.org/iptc.html
		https://wiki.gnome.org/Projects/gexiv2

"""


xmp_template = """<?xpacket begin="<feff>" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:darktable="http://darktable.sf.net/"
   xmp:Rating="1"
   darktable:xmp_version="1"
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta> 
<?xpacket end="w"?>"""



class MetadataError(Exception):
	pass


class FileCollisionError(Exception):
	pass

	
class ImageMetadata(object):

	def __init__(self, path):
		# try to read image and xmp metadata
		# create xmp if it does not exist
		# raise error if either fail
		self.path = path.rstrip('.xmp') # this may not be necessary / errors could be handled in other ways
		self._load_metadata()
		self._load_sidecar()

	def _load_metadata(self):
		"""
		given a path to an image or an xmp file, return a Metadata object
		Metadata objects provide coordinated access to metdata in either xmp or image files
		saving 
		"""

		# try to open the image file, throw exception if DNE
		try:
			self._img_metadata = pyexiv2.ImageMetadata(self.path)
			self._img_metadata.read()

		except Exception as e:
			raise MetadataError(e.message)


	def _load_sidecar(self, create=False):
	
		self.sidecar_path = self.path + '.xmp'
		
		# try to open xmp file if it exists
		if os.path.exists(self.sidecar_path):
			try:
				self._xmp_metadata = pyexiv2.ImageMetadata(self.sidecar_path)
				self._xmp_metadata.read()

			except Exception as e:
				raise MetadataError(e.message)

		# if xmp file DNE, create it
		elif create:
			with open(self.sidecar_path,'w') as f:
				f.write(xmp_template)


	def __getitem__(self, key):
		
		# first check the xmp source
		if hasattr(self, '_xmp_metadata') and key in self._xmp_metadata:
			return self._xmp_metadata[key].value

		# then check the image source
		elif key in self._img_metadata:
			return self._img_metadata[key].value

		# Tag is either not set or name is invalid - either way it's not set
		else:
			raise KeyError('Tag not set ({key})'.format(key=key))
		

	def __setitem__(self, key, value):
		"""set value and save to disk"""
		print "Not implimented"



def ls(path, include_hidden=False):
	"""
	walk the filesystem
	return list of paths rooted at path
	if visitor is specified, return (path, visitor(path)) unless visitor(path) is None 
	
	TODO: implement recursive=bool option
	"""
	pathlist = []
	path = os.path.realpath(path)

	for root, dirs, files in os.walk(path):
		for name in files:
			# skip hidden files as appropriate
			if not include_hidden and name.startswith('.'):
				continue
	
			yield os.path.join(root, name)
			

def new_event_dir(base, date):
	event_dir = os.path.join(base, date.strftime("%Y-%m-%d"))
	if not os.path.exists(event_dir):
		os.makedirs(event_dir, 0755)
		print "New Event:", event_dir
	return event_dir



def copy_file(source, target, target_is_dir=False):
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

		# check if they have the same size but different hash
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
			if VERBOSE: print "Linking: {s} -> {t}".format(s=source, t=target_path)
		
		# otherwise, copy the file
		except OSError as e:
			if VERBOSE: print "Copying: {s} -> {t}".format(s=source, t=target_path)
			copyfile(source, target_path)


def sha1sum(path):
	with open(path) as f:
		return hashlib.sha1(f.read()).hexdigest()
		

def is_duplicate_file(source, directory):
	"""check for any files in the target directory with the same hash as the source file"""
	source_hash = sha1sum(source)
	for path in ls(directory):
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



def organize_by_event(source_dir, dest_dir, day_delta=4, alternate_dir=None): 
	
	# locals
	event_date = None
	event_dir = None
	dest = os.path.realpath(dest_dir)
	source = os.path.realpath(source_dir)
	metadata_list = []
	alternate_list = []

	# walk the source directory and separate photos (with metadata) from everything else
	for path in ls(source):
		
		try:
			# create a metadata object and check for the date key
			# images with metadata valid date attribute set go into metadata_list
			# everything else goes in the alternate_list
			imd = ImageMetadata(path)
			date = imd['Exif.Image.DateTime']
			assert(type(date) == datetime)
			metadata_list.append(imd)

		except MetadataError as e:
			alternate_list.append(path)

		except KeyError as e:
			sys.stderr.write('Exif.Image.DateTime attribute not set: {p}\n'.format(p=path))
			alternate_list.append(path)

		except AssertionError as e:
			sys.stderr.write('Exif.Image.DateTime did not return datetime object: [{d}] {p}\n'.format(d=repr(date), p=path))
			alternate_list.append(path)
	
	
	# update progress counters
	total_count = len(metadata_list) + len(alternate_list)
	current_count = 0
	print "{t} files of which {m} have metadata and {u} will not be organized".format(t=total_count, m=len(metadata_list), u=len(alternate_list))
	# FIXME: print progress

	# iterate over all ImageMetadata objects sorted by Exif.Image.DateTime
	for metadata in sorted(metadata_list, key=lambda md: md['Exif.Image.DateTime']):
		date = metadata['Exif.Image.DateTime']

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
			#print "="*3, label + " / " + str(delta.days), "="*3
		
		# copy file to event_dir 
		target_path = os.path.join(event_dir, os.path.basename(metadata.path))
		try:
			copy_file(metadata.path, target_path)
		
		# if there is a collision, choose a different name in the event dir and try again
		except FileCollisionError as e:
			# but first make sure we didn't already do this once
			if not is_duplicate_file(metadata.path, event_dir):
				renamed_path = get_unique_filename(target_path)
				copy_file(metadata.path, renamed_path)

		# update progress
		current_count += 1
		# FIXME: print progress

	# now deal with the non-images and other files without metadata
	for path in alternate_list:

		# if the user specified an alternate directory for non-image files
		if alternate_dir:
			# preserve the directory structure as a subdirectory 
			prefix = os.path.commonprefix([path, source])
			subpath = path.replace(prefix,'',1).strip(os.path.sep)
			target = os.path.join(alternate_dir, subpath) 
			#sys.stderr.write('Copying non-image file to alternate directory: ' + path + '\t' + target  + '\n') 
			
			# copy the file to "unorganized" directory
			try:
				copy_file(path, target)

			# handle file collisions by choosing a different filename
			except FileCollisionError as e:
				# first check that we didnt already do this once
				if not is_duplicate_file(path, os.path.dirname(target)):
					renamed_path = get_unique_filename(target)
					copy_file(path, renamed_path)

		
		else:
			# there were no image metadata objects in the same directory as this path
			sys.stderr.write('Skipping non-image file: ' + path + '\n')

		# update progress
		current_count += 1


def path_distance(x,y):
	"""Calculate the number of trailing characters that are not equal between two strings."""
	return len(x.lstrip(y))



def print_exiv2_metadata(path):
	m = pyexiv2.ImageMetadata(path)
	m.read()
	tags = []

	# check all possible tags
	for key in m.keys():
		try:
			tag = m[key]
			if tag.value:
				tags.append(tag)
		
		except KeyError as e:
			# Tag not set
			pass

		except pyexiv2.exif.ExifValueError as e:
			# Invalid value for EXIF type
			pass

	# now print tags with values
	for tag in tags:
		if tag.type == 'Undefined':
			value = "<DATA>"
		else:
			value = str(tag.value)
		
		print tag.key.rjust(45) + ': ' + value



#### module level variable for function state
REMDIRS = []

def remove_duplicates_interactive(paths):
	print '\n' + '\n'.join("{i}: {p}".format(i=i, p=paths[i]) for i in range(len(paths))) 

	global REMDIRS 
	unlink_list = range(len(paths))

	# if a user selected one of these directories before, proceed automatically
	for d in REMDIRS:
		if len(unlink_list) < len(paths):
			break
		for i in unlink_list:
			if paths[i].startswith(d):
				unlink_list.remove(i)
				break

	# if we havent selected which file to save, ask user	
	if len(unlink_list) == len(paths):
		# prompt user interactively
		tryagain = True
		while tryagain:
			try:
				# prompt user which items to save
				choice = int(raw_input("Delete all except: "))

				# remember chosen directory
				REMDIRS.append(os.path.dirname(paths[choice]))

				# do not allow user to delete all items, make sure choices are within the valid range
				unlink_list = range(len(paths))
				unlink_list.remove(choice)
				tryagain = False
			
			except ValueError as e:
				print "Invalid selection"
	
	# double check that we dont delete everything
	assert(len(unlink_list) < len(paths))
	
	# delete duplicates 
	for i in unlink_list:
		p = paths[i]
		print "Deleting {i}: {p}".format(i=i,p=p)
		os.unlink(p)


def find_duplicates(directories, interactive=False, delete=False):
	hashmap = {}
	
	for d in directories:
		files = ls(d)
		sys.stderr.write('Checking {d}\n'.format(d=d))
		for path in files:
			hashmap.setdefault(sha1sum(path),[]).append(path)
	
	for key,paths in hashmap.iteritems():
		if len(paths) > 1:
			if interactive:
				print "[{k}]".format(k=key)
				remove_duplicates_interactive(paths)
			else:
				print '\n'.join("{h}: {p}".format(h=key, p=p) for p in paths) + "\n"
	


def create_preview(path):
	"""
	create a preview for the selected RAW file
	update the jpg with metadata associating it with the raw image
	/usr/bin/ufraw-batch --wb=camera --compression=95 --out-type=jpg path
	"""
	# make sure the preview file doesn't already exist
	preview = os.path.splitext(path)[0] + '.jpg'
	if not os.path.exists(preview):
		p = Popen(['/usr/bin/ufraw-batch', '--wb=camera', '--compression=95', '--out-type=jpg', '--output={p}'.format(p=preview), path], stdout=PIPE, stderr=PIPE)
		out,err = p.communicate()
		if VERBOSE and out:
			sys.stdout.write(out)
		if VERBOSE and err:
			sys.stderr.write(err)



def previews(path):
	"""
	Generate previews of all Raw files under path
	"""
	cpus = cpu_count()
	pool = Pool(cpus)
	raw_files = filter(lambda f: f.lower().endswith('.orf'), ls(path))
	print "Creating previews for {f} RAW images using {c} CPU cores (existing files will be skipped).".format(c=cpus, f=len(raw_files))
	pool.map(create_preview, raw_files)



if __name__=='__main__':

	parser = argparse.ArgumentParser(description='Photo organization')
	parser.add_argument('--organize', metavar=('SOURCE','DEST'), nargs=2, help='organize the photos')
	parser.add_argument('--alternate', help='alternate directory to copy files that could not be organized [default DEST/unorganized]')
	parser.add_argument('--gap', type=int, default=4, help='The minimum number of days between events.')
	parser.add_argument('--show', metavar='IMG', help='show metadata for given image file')
	parser.add_argument('--verbose', action='store_const', const=True, help='display verbose file operations and other info')
	parser.add_argument('--hardlink', action='store_const', const=False, help='hardlink instead of copy')
	parser.add_argument('--find-duplicates', nargs="*", help='find all duplicate files')
	parser.add_argument('--find-duplicates-interactive', nargs="*", help='find all duplicate files')
	parser.add_argument('--raw-previews', metavar='DIR', help='generate JPG preview files for RAW images')
	args = parser.parse_args()
	
	# set verbose flag
	global VERBOSE
	VERBOSE = args.verbose if args.verbose else False

	# print EXIF data for an image
	if args.show:
		print_exiv2_metadata(args.show)

	# organize and copy files from SOURCE into DEST
	elif args.organize:
		source,dest = args.organize
		alternate = args.alternate if args.alternate else os.path.join(dest, 'unorganized')
		organize_by_event(source, dest, args.gap, alternate) 

	elif args.find_duplicates:
		target = args.find_duplicates
		print "Finding all duplicate files (very slow)"
		find_duplicates(target)

	elif args.find_duplicates_interactive:
		target = args.find_duplicates_interactive
		print "Finding all duplicate files (very slow)"
		find_duplicates(target, interactive=True)

	elif args.raw_previews:
		previews(args.raw_previews)

	# help
	else:
		parser.print_usage()


