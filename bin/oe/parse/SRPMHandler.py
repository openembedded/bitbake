"""class for handling .src.rpm files

   Accesses the file and obtains its metadata"""

import re, oe, string, os, sys
import oe
import oe.fetch
from oe import debug, data, fetch, fatal

from oe.parse.ConfHandler import init

def supports(fn):
	return fn[-8:] == ".src.rpm"

def handle(fn, d = {}):
	init(d)
	data.inheritFromOS(2, d)
	oepath = ['.']
	if not os.path.isabs(fn):
		f = None
		voepath = data.getVar("OEPATH", d)
		if voepath:
			oepath += voepath.split(":")
		for p in oepath:
			p = data.expand(p, d)
			if os.access(os.path.join(p, fn), os.R_OK):
				f = open(os.path.join(p, fn), 'r')
		if f is None:
			raise IOError("file not found")
	else:
		f = open(fn,'r')

	print "Setting SRPMFILE to %s" % fn
	data.setVar("SRPMFILE", fn, d)

	inheritclasses = data.getVar("INHERIT", d)
	if inheritclasses:
		i = inheritclasses.split()
	else:
		i = []

	if not "base_srpm" in i:
		i[0:0] = ["base_srpm"]

	for c in i:
		oe.parse.handle('classes/%s.oeclass' % c, d)

	data.update_data(d)
	return d

# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
