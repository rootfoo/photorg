#!/usr/bin/env python

from distutils.core import setup

setup(name='photorg',
	version='0.1',
	description='Organize photos, grouped by EXIF date',
	author='Marcus Hodges',
	author_email='0xmeta@gmail.com',
	url='http://rootfoo.org',
	license="MIT",
    packages=['photorg'], 
	scripts=['bin/photorg',
	    'bin/photorg-deduplicate']
	)

