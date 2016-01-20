
# http://en.wikipedia.org/wiki/Resource_Interchange_File_Format
import sys
from struct import pack, unpack

if __name__=='__main__':
	
	path = sys.argv[1]
	with open(path) as f:

		ident = f.read(4)
		size = unpack('<I', f.read(4))[0]
		print ident, size

		if ident in ['RIFF','LIST']:
			list_ident = f.read(4)
			print list_ident



