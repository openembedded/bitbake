"""class for handling configuration data files

   Reads the file and obtains its metadata"""

import re, oe.data, os, sys
from oe import debug, fatal

#__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}]+)\s*(?P<colon>:)?(?P<ques>\?)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}]+)(\[(?P<flag>[a-zA-Z0-9\-_+.]+)\])?\s*(?P<colon>:)?(?P<ques>\?)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__include_regexp__ = re.compile( r"include\s+(.+)" )

def init(data):
	if not oe.data.getVar('TOPDIR', data):
		oe.data.setVar('TOPDIR', os.getcwd(), data)
	if not oe.data.getVar('OEPATH', data):
		oebuild = os.path.abspath(sys.argv[0])
		oebin = os.path.dirname(oebuild)
		oedir = os.path.dirname(oebin)
		oe.data.setVar('OEPATH', "${TOPDIR}:%s:%s:${HOME}/.oe:${OEDIR}/bin:${OEDIR}:%s/share/oe" % (oebin, oedir, sys.prefix), data)

def supports(fn, d):
	return localpath(fn, d)[-5:] == ".conf"

def localpath(fn, d):
	if os.path.exists(fn):
		return fn

	localfn = None
	try:
		localfn = oe.fetch.localpath(fn, d)
	except oe.MalformedUrl:
		pass

	if not localfn:
		localfn = fn
	return localfn

def obtain(fn, data = {}):
	import sys, oe
	fn = oe.data.expand(fn, data)
	localfn = oe.data.expand(localpath(fn, data), data)

	if localfn != fn:
		dldir = oe.data.getVar('DL_DIR', data, 1)
		if not dldir:
			debug(1, "obtain: DL_DIR not defined")
			return localfn
		oe.mkdirhier(dldir)
		try:
			oe.fetch.init([fn])
		except oe.fetch.NoMethodError:
			(type, value, traceback) = sys.exc_info()
			debug(1, "obtain: no method: %s" % value)
			return localfn
	
		try:
			oe.fetch.go(data)
		except oe.fetch.MissingParameterError:
			(type, value, traceback) = sys.exc_info()
			debug(1, "obtain: missing parameters: %s" % value)
			return localfn
		except oe.fetch.FetchError:
			(type, value, traceback) = sys.exc_info()
			debug(1, "obtain: failed: %s" % value)
			return localfn
	return localfn


def include(oldfn, fn, data = {}):
	if oldfn == fn: # prevent infinate recursion
		return None

	import oe
	fn = oe.data.expand(fn, data)
	oldfn = oe.data.expand(oldfn, data)

	from oe.parse import handle
	try:
		ret = handle(fn, data, 1)
	except IOError:
		debug(2, "CONF file '%s' not found" % fn)

def handle(fn, data = {}, include = 0):
	if include:
		inc_string = "including"
	else:
		inc_string = "reading"
	init(data)

	if include == 0:
		oe.data.inheritFromOS(data)
		oldfile = None
	else:
		oldfile = oe.data.getVar('FILE', data)

	fn = obtain(fn, data)
	oepath = ['.']
	if not os.path.isabs(fn):
		f = None
		voepath = oe.data.getVar("OEPATH", data)
		if voepath:
			oepath += voepath.split(":")
		for p in oepath:
			currname = os.path.join(oe.data.expand(p, data), fn)
			if os.access(currname, os.R_OK):
				f = open(currname, 'r')
				debug(1, "CONF %s %s" % (inc_string, currname))
				break
		if f is None:
			raise IOError("file not found")
	else:
		f = open(fn,'r')
		debug(1, "CONF %s %s" % (inc_string,fn))
	lineno = 0
	oe.data.setVar('FILE', fn, data)
	while 1:
		lineno = lineno + 1
		s = f.readline()
		if not s: break
		w = s.strip()
		if not w: continue		# skip empty lines
		s = s.rstrip()
		if s[0] == '#': continue	# skip comments
		while s[-1] == '\\':
			s2 = f.readline()[:-1].strip()
			lineno = lineno + 1
			s = s[:-1] + s2
		feeder(lineno, s, fn, data)

	if oldfile:
		oe.data.setVar('FILE', oldfile, data)
	return data

def feeder(lineno, s, fn, data = {}):
	m = __config_regexp__.match(s)
	if m:
		groupd = m.groupdict()
		key = groupd["var"]
		if "exp" in groupd and groupd["exp"] != None:
			oe.data.setVarFlag(key, "export", 1, data)
		if "ques" in groupd and groupd["ques"] != None:
			val = oe.data.getVar(key, data)
			if not val:
				val = groupd["value"]
		elif "colon" in groupd and groupd["colon"] != None:
			val = oe.data.expand(groupd["value"], data)
		else:
			val = groupd["value"]
		if 'flag' in groupd and groupd['flag'] != None:
			#oe.note("setVarFlag(%s, %s, %s, data)" % (key, groupd['flag'], val))
			oe.data.setVarFlag(key, groupd['flag'], val, data)
		else:
			oe.data.setVar(key, val, data)
		return

	m = __include_regexp__.match(s)
	if m:
		s = oe.data.expand(m.group(1), data)
		#debug(2, "CONF %s:%d: including %s" % (fn, lineno, s))
		include(fn, s, data)
		return

	raise ParseError("%s:%d: unparsed line" % (fn, lineno));

# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
