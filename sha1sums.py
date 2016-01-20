#!/usr/bin/python

"""
this is equivelent to find + sha1sum:
  cd path && find . -type f -exec sha1sum {} \;
"""

import os
from hashlib import sha1
import sys

if __name__=='__main__':

	path = sys.argv[1]
	os.chdir(path)
	for root,dirs,files in os.walk('.', topdown=True):
		for f in files:
			path = os.path.join(root,f)
			with open(path) as fh:
				digest = sha1(fh.read()).hexdigest()
				print digest, path


