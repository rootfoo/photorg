#!/usr/bin/python
# apt-get install python-hachoir-metadata

from hachoir_metadata import extractMetadata
from hachoir_parser import createParser
import sys


def hachoir_get_metadata(path):
	filename = unicode(path)
	parser = createParser(filename, real_filename=filename, tags=None)
	metadata = extractMetadata(parser)
	
	d = {}
	# data is hachoir_metadata.metadata_item.Data instance
	# has properties: key, values, description
	for data in metadata:
		# data.values is either [] or hachoir_metadata.metadata_item.DataValue instance
		# has properties: text, value
		if data.values:
			d[data.key] = data.values[0].value
	
	return d


def pretty_print_dict(d):
	max_len = max([len(k) for k in d])
	for k,v in d.items():
		print k.rjust(max_len) + ":", v

if __name__=='__main__':

	path = sys.argv[1]
	d = hachoir_get_metadata(path)
	pretty_print_dict(d)
