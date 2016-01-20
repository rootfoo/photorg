
import os
import string
import sys

if __name__=='__main__':
	names = []
	alphanum = set(string.letters + string.digits)
	symbols = set(string.printable) - set(string.letters) - set(string.digits)
	path = sys.argv[1]	
	
	extensions = set()
	patterns = set()

	for root, dirs, files in os.walk(path):                                               
		for name in files:

			name_pattern = ""
			for c in name:
				if c in alphanum:
					name_pattern += 'x'
				else:
					name_pattern += c

			patterns.add(name_pattern)

			ext = os.path.splitext(name)[1].lower()
			extensions.add(ext)
			
			# to print files with wierd extensions
			if ext not in ['.png','.xmp','.avi','.jpg','.orf','.dsc','.mov']:
				print os.path.join(root,name)
	
	print '-'*20
	for x in extensions:
		print x
	
	print "-"*20
	for x in patterns:
		print x
