"""class for handling configuration data files

   Reads the file and obtains its metadata"""

import re, oe.data, os, sys
from oe import debug

__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>\w+)\s*(?P<colon>:)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__include_regexp__ = re.compile( r"include\s+(.+)" )

def init(data):
	oe.data.setVar('TOPDIR', os.getcwd(), data)
	oe.data.setVar('OEDIR', os.path.join(sys.prefix, "share/oe"), data)
	oe.data.setVar('OEPATH', "${OEDIR}/bin:${OEDIR}:${TOPDIR}/bin:${TOPDIR}", data)

def supports(fn):
	return fn[-5:] == ".conf"

def include(oldfn, fn, data = {}):
	if oldfn == fn: # prevent infinate recursion
		return None

	from oe.parse import handle
	return handle(fn, data)

def handle(fn, data = {}):
	init(data)
	oe.data.inheritFromOS(1, data)
	oepath = ['.']
	if not os.path.isabs(fn):
		f = None
		voepath = oe.data.getVar("OEPATH", data)
		if voepath:
			oepath += voepath.split(":")
		for p in oepath:
			p = oe.data.expand(p, data)
			if os.access(os.path.join(p, fn), os.R_OK):
				f = open(os.path.join(p, fn), 'r')
		if f is None:
			raise IOError("file not found")
	else:
		f = open(fn,'r')
	lineno = 0
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
			s = s[:-1] + s2
		feeder(lineno, s, fn, data)
	return data

def feeder(lineno, s, fn, data = {}):
	m = __config_regexp__.match(s)
	if m:
		groupd = m.groupdict()
		key = groupd["var"]
		if groupd.has_key("exp") and groupd["exp"] != None:
			oe.data.setVarFlag(key, "export", 1, data)
		if groupd.has_key("colon") and groupd["colon"] != None:
			val = oe.data.expand(groupd["value"], data)
		else:
			val = groupd["value"]
		oe.data.setVar(key, val, data)
		return

	m = __include_regexp__.match(s)
	if m:
		s = oe.data.expand(m.group(1), data)
		if os.access(os.path.abspath(s), os.R_OK):
			debug(2, "%s:%d: including %s" % (fn, lineno, s))
			oe.data.inheritFromOS(2, data)
			include(fn, s, data)
		else:
			debug(1, "%s:%d: could not import %s" % (fn, lineno, s))
		return

# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
