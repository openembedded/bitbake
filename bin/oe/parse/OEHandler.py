"""class for handling .oe files

   Reads the file and obtains its metadata"""

import re, oe, string, os, sys
import oe
import oe.data
import oe.fetch
from oe import debug

from oe.parse.ConfHandler import include

__func_start_regexp__    = re.compile( r"((?P<py>python)\s*)*(?P<func>\w+)\s*\(\s*\)\s*{$" )
__inherit_regexp__       = re.compile( r"inherit\s+(.+)" )
__export_func_regexp__   = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )
__addtask_regexp__       = re.compile("addtask\s+(?P<func>\w+)\s*((before\s*(?P<before>((.*(?=after))|(.*))))|(after\s*(?P<after>((.*(?=before))|(.*)))))*")

__infunc__ = ""
__body__   = []
__oepath_found__ = 0
__classname__ = ""

def init(data):
	oe.data.setVar('TOPDIR', os.getcwd(), data)
	oe.data.setVar('OEDIR', os.path.join(sys.prefix, "share/oe"), data)
	oe.data.setVar('OEPATH', "${OEDIR}/bin:${OEDIR}:${TOPDIR}/bin:${TOPDIR}", data)

def supports(fn):
	return fn[-3:] == ".oe" or fn[-8:] == ".oeclass"

def handle(fn, data = {}):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __infunc__, __body__, __oepath_found__, __classname__
	__body__ = []
	__oepath_found__ = 0
	__infunc__ = ""

	fn = os.path.abspath(fn)
	__classname__ = fn
	o = re.match(r".*/([^/\.]+)",fn)
	if o:
		__classname__ = o.group(1)

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
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __infunc__, __body__, __oepath_found__, __classname__, oe
	if __infunc__:
		if s == '}':
			__body__.append('')
			import oe.data
			oe.data.setVar(__infunc__, string.join(__body__, '\n'), data)
			oe.data.setVarFlag(__infunc__, "func", 1, data)
			__infunc__ = ""
			__body__ = []
		else:
			try:
				if oe.data.getVarFlag(__infunc__, "python", data) == 1:
					s = re.sub(r"^\t", '', s)
			except KeyError:
				pass
			__body__.append(s)
		return
			
	m = __func_start_regexp__.match(s)
	if m:
		__infunc__ = m.group("func")
		key = __infunc__
		if m.group("py") is not None:
			oe.data.setVarFlag(key, "python", 1, data)
		return

	__word__ = re.compile(r"\S+")

	m = __export_func_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		for f in n:
			oe.data.setVar(f, "\t%s_%s\n" % (__classname__, f), data)
			oe.data.setVarFlag(f, "func", 1, data)
			if oe.data.getVarFlag("%s_%s" % (__classname__, f), "python", data) == 1:
				oe.data.setVarFlag(f, "python", 1, data)
		return

	m = __addtask_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		oe.data.setVarFlag(n[0], "task", 1, data)
		return

	m = __inherit_regexp__.match(s)
	if m:
		files = m.group(1)
		n = __word__.findall(files)
		for f in n:
			import oe.data
			file = oe.data.expand(f, data)
			if file[0] != "/":
				if data.has_key('OEPATH'):
					__oepath_found__ = 0
					for dir in oe.data.expand(oe.data.getVar('OEPATH', data), data).split(":"):
						if os.access(os.path.join(dir, "classes", file + ".oeclass"), os.R_OK):
							file = os.path.join(dir, "classes",file + ".oeclass")
							__oepath_found__ = 1
				if __oepath_found__ == 0:
					debug(1, "unable to locate %s in OEPATH"  % file)

			if os.access(os.path.abspath(file), os.R_OK):
				debug(2, "%s:%d: inheriting %s" % (fn, lineno, file))
				oe.data.inheritFromOS(2, data)
				include(fn, file, data)
			else:
				debug(1, "%s:%d: could not import %s" % (fn, lineno, file))
		return

	import oe.parse.ConfHandler
	return oe.parse.ConfHandler.feeder(lineno, s, fn, data)

# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
