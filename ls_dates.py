#!/usr/bin/python

from photorg import ls, ImageMetadata
import sys
import os
from matplotlib import pyplot
from numpy import mean,average,std





if __name__=='__main__':


	images = []
	for p in ls(sys.argv[1]):
		path,ext = os.path.splitext(p)
		if ext.lower() in ['.orf','.jpg']:
			imd = ImageMetadata(p)
			imd.time = int(imd['Exif.Image.DateTime'].strftime('%s'))
			images.append(imd)
	
	images = sorted(images, key=lambda x: x.time)

	#for imd in images:
	#	print imd.time, imd.path

	
	total_delta = images[-1].time - images[0].time
	deltas = []

	for i in range(1,len(images)):
		#density = float(images[i].time - images[0].time) / i
		#print i, density
		
		delta = images[i].time - images[i-1].time

		deltas.append(delta)
	
		av = average(deltas)
		st = std(deltas)
		mark = ""
		if delta > av+st:
			mark = "*"*5
			deltas = []
		
		print "{}\t{}\t{}\t{}\t{}".format(i,delta,av,st,mark)
		#print i, "std", std(deltas)


	#dmax = max(deltas)
	#dnorm = [float(d)/dmax for d in deltas]
	#print "max={},avg={}".format(dmax,average(deltas))

	#pyplot.bar(range(len(deltas)), dnorm, .1)
	#pyplot.show()

