"""class for handling .oe files

   Reads the file and obtains its metadata"""

import re, oedata, string, os, sys
from oe import debug

from oeparse.ConfHandler import include

__func_start_regexp__ = re.compile( r"(\w+)\s*\(\s*\)\s*{$" )
__inherit_regexp__ = re.compile( r"inherit\s+(.+)" )
__export_func_regexp__ = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )
__addtask_regexp__ = re.compile( r"addtask\s+(.+)" )

__infunc__ = ""
__body__   = []
__oepath_found__ = 0

def supports(fn):
	return fn[-3:] == ".oe"

def handle(fn, data = {}):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __infunc__, __body__, __oepath_found__
	oedata.setVar('TOPDIR', os.getcwd(), data)
	oedata.setVar('OEDIR', os.path.join(sys.prefix, "share/oe"), data)
	oedata.setVar('OEPATH', "${OEDIR}/bin:${OEDIR}:${TOPDIR}/bin:${TOPDIR}", data)
	__body__ = []
	__oepath_found__ = 0
	__infunc__ = ""

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
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __infunc__, __body__, __oepath_found__
	if __infunc__:
		if s == '}':
			__body__.append('')
			oedata.setVar(__infunc__, string.join(__body__, '\n'), data)
			oedata.setVarFlag(__infunc__, "func", 1, data)
			__infunc__ = ""
			__body__ = []
		else:
			__body__.append(s)
		return

	m = __func_start_regexp__.match(s)
	if m:
		__infunc__ = m.group(1)
		return

	__word__ = re.compile(r"\S+")

	m = __export_func_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		for f in n:
			oedata.setVar(f, "\t%s_%s\n" % (fn, f), data)
		return

	m = __addtask_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		if not envflags.has_key(n[0]):
			envflags[n[0]] = {}
		oedata.setVarFlag(n[0], "task", 1, data)
		return

	m = __inherit_regexp__.match(s)
	if m:
		files = m.group(1)
		n = __word__.findall(files)
		for f in n:
			file = oedata.expand(f, data)
			if file[0] != "/":
				if data.has_key('OEPATH'):
					__oepath_found__ = 0
					for dir in oedata.expand(cfgenv['OEPATH'], data).split(":"):
						if os.access(os.path.join(dir, "classes", file + ".oeclass"), os.R_OK):
							file = os.path.join(dir, "classes",file + ".oeclass")
							__oepath_found__ = 1
				if __oepath_found__ == 0:
					debug(1, "unable to locate %s in OEPATH"  % file)

			if os.access(os.path.abspath(file), os.R_OK):
				debug(2, "%s:%d: inheriting %s" % (fn, lineno, file))
#				inherit_os_env(2, self.env)
				include(fn, s, data)
			else:
				debug(1, "%s:%d: could not import %s" % (fn, lineno, file))
		return

	import oeparse.ConfHandler
	return oeparse.ConfHandler.feeder(lineno, s, fn, data)

# Add us to the handlers list
from oeparse import handlers
handlers.append({'supports': supports, 'handle': handle})
del handlers
