"""class for handling configuration data files

   Reads the file and obtains its metadata"""

import re, oedata, os, sys
from oe import debug

__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>\w+)\s*(?P<colon>:)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__include_regexp__ = re.compile( r"include\s+(.+)" )

def supports(fn):
	return fn[-5:] == ".conf"

def include(oldfn, fn, data = {}):
	if oldfn == fn: # prevent infinate recursion
		return 1

	from oeparse import handle
	return handle(fn, data)

def handle(fn, data = {}):
	oedata.setVar('TOPDIR', os.getcwd(), data)
	oedata.setVar('OEDIR', os.path.join(sys.prefix, "share/oe"), data)
	oedata.setVar('OEPATH', "${OEDIR}/bin:${OEDIR}:${TOPDIR}/bin:${TOPDIR}", data)
	fn = os.path.abspath(fn)
	f = open(fn,'r')
	lineno = 0
	while 1:
		lineno = lineno + 1
		s = f.readline()
		if not s: break
		s = s.strip()
		if not s: continue		# skip empty lines
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
			oedata.setVarFlag(key, "export", 1, data)
		if groupd.has_key("colon") and groupd["colon"] != None:
			val = oedata.expand(groupd["value"], data)
		else:
			val = groupd["value"]
		oedata.setVar(key, val, data)
		return

	m = __include_regexp__.match(s)
	if m:
		s = oedata.expand(m.group(1), data)
		if os.access(os.path.abspath(s), os.R_OK):
			debug(2, "%s:%d: including %s" % (fn, lineno, s))
#			inherit_os_env(2, self.env)
			include(fn, s, data)
		else:
			debug(1, "%s:%d: could not import %s" % (fn, lineno, s))
		return

# Add us to the handlers list
from oeparse import handlers
handlers.append({'supports': supports, 'handle': handle})
del handlers
