"""class for handling .oe files

   Reads the file and obtains its metadata"""

import re, oe, string, os, sys
import oe
import oe.fetch
from oe import debug, data, fetch, fatal

from oe.parse.ConfHandler import include, init

__func_start_regexp__    = re.compile( r"((?P<py>python)\s*)*(?P<func>\w+)\s*\(\s*\)\s*{$" )
__inherit_regexp__       = re.compile( r"inherit\s+(.+)" )
__export_func_regexp__   = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )
__addtask_regexp__       = re.compile("addtask\s+(?P<func>\w+)\s*((before\s*(?P<before>((.*(?=after))|(.*))))|(after\s*(?P<after>((.*(?=before))|(.*)))))*")
__addhandler_regexp__       = re.compile( r"addhandler\s+(.+)" )

__infunc__ = ""
__body__   = []
__oepath_found__ = 0
__classname__ = ""
classes = [ None, ]

def supports(fn):
	return fn[-3:] == ".oe" or fn[-8:] == ".oeclass"

def inherit(files, d):
	fn = ""
	lineno = 0
	for f in files:
		file = data.expand(f, d)
		if file[0] != "/":
			if d.has_key('OEPATH'):
				__oepath_found__ = 0
				for dir in data.expand(data.getVar('OEPATH', d), d).split(":"):
					if os.access(os.path.join(dir, "classes", file + ".oeclass"), os.R_OK):
						file = os.path.join(dir, "classes",file + ".oeclass")
						__oepath_found__ = 1
			if __oepath_found__ == 0:
				debug(1, "unable to locate %s in OEPATH"  % file)

		if os.access(os.path.abspath(file), os.R_OK):
			debug(2, "%s:%d: inheriting %s" % (fn, lineno, file))
			include(fn, file, d)
		else:
			debug(1, "%s:%d: could not import %s" % (fn, lineno, file))


def handle(fn, d = {}):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __infunc__, __body__, __oepath_found__
	__body__ = []
	__oepath_found__ = 0
	__infunc__ = ""

	(root, ext) = os.path.splitext(os.path.basename(fn))
	if ext == ".oeclass":
		__classname__ = root
		classes.append(__classname__)

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

	inheritclasses = data.getVar("INHERIT", d)
	if inheritclasses:
		i = inheritclasses.split()
	else:
		i = []
	i[0:0] = ["base.oeclass"]
	inherit(i, d)

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
		feeder(lineno, s, fn, d)
	if ext == ".oeclass":
		classes.remove(__classname__)
	else:
		set_automatic_vars(fn, d)
	return d

def feeder(lineno, s, fn, d):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __infunc__, __body__, __oepath_found__, classes, oe
	if __infunc__:
		if s == '}':
			__body__.append('')
			data.setVar(__infunc__, string.join(__body__, '\n'), d)
			data.setVarFlag(__infunc__, "func", 1, d)
			__infunc__ = ""
			__body__ = []
		else:
			try:
				if data.getVarFlag(__infunc__, "python", d) == 1:
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
			data.setVarFlag(key, "python", 1, d)
		return

	__word__ = re.compile(r"\S+")

	m = __export_func_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		for f in n:
			var = f
			if len(classes) > 1 and classes[-2] is not None:
				var = "%s_%s" % (classes[-2], var)
			data.setVar(var, "\t%s_%s\n" % (classes[-1], f), d)
			data.setVarFlag(var, "func", 1, d)
			if data.getVarFlag("%s_%s" % (classes[-1], f), "python", d) == 1:
				data.setVarFlag(var, "python", 1, d)

		return

	m = __addtask_regexp__.match(s)
	if m:
		func = m.group("func")
		before = m.group("before")
		after = m.group("after")
		if func is None:
			return
		var = "do_" + func

		data.setVarFlag(var, "task", 1, d)

		if after is not None:
			# set up deps for function
			data.setVarFlag(var, "deps", after.split(), d)
		if before is not None:
			# set up things that depend on this func 
			data.setVarFlag(var, "postdeps", before.split(), d)
		return

	m = __addhandler_regexp__.match(s)
	if m:
		fns = m.group(1)
		hs = __word__.findall(fns)
		for h in hs:
			data.setVarFlag(h, "handler", 1, d)
		return

	m = __inherit_regexp__.match(s)
	if m:

		files = m.group(1)
		n = __word__.findall(files)
		inherit(n, d)
		return

	from oe.parse import ConfHandler
	return ConfHandler.feeder(lineno, s, fn, d)

def set_automatic_vars(file, d):
	"""Deduce per-package environment variables"""

	debug(2, "setting automatic vars")
	pkg = oe.catpkgsplit(file)
	if pkg == None:
		fatal("package file not in valid format")

	data.setVar('CATEGORY', pkg[0], d)
	data.setVar('PN', pkg[1], d)
	data.setVar('PV', pkg[2], d)
	data.setVar('PR', pkg[3], d)
	data.setVar('P', '${PN}-${PV}', d)
	data.setVar('PF', '${P}-${PR}', d)

	for s in ['${TOPDIR}/${CATEGORY}/${PF}', 
		  '${TOPDIR}/${CATEGORY}/${PN}-${PV}',
		  '${TOPDIR}/${CATEGORY}/files',
		  '${TOPDIR}/${CATEGORY}']:
		s = data.expand(s, d)
		if os.access(s, os.R_OK):
			data.setVar('FILESDIR', s, d)
			break

	data.setVar('WORKDIR', '${TMPDIR}/${CATEGORY}/${PF}', d)
	data.setVar('T', '${WORKDIR}/temp', d)
	data.setVar('D', '${WORKDIR}/image', d)
	data.setVar('D', '${WORKDIR}/${P}', d)
	data.setVar('SLOT', '0', d)
	data.inheritFromOS(3, d)

# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
