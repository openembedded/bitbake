"""class for handling .oe files

   Reads the file and obtains its metadata"""

import re, oe, string, os, sys
import oe
import oe.fetch
from oe import debug, data, fetch, fatal

from oe.parse.ConfHandler import include, localpath, obtain, init

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

def supports(fn, d):
	localfn = localpath(fn, d)
	return localfn[-3:] == ".oe" or localfn[-8:] == ".oeclass"

def inherit(files, d):
	__inherit_cache = data.getVar('__inherit_cache', d) or ""
	fn = ""
	lineno = 0
	for f in files:
		file = data.expand(f, d)
		if file[0] != "/" and file[-8:] != ".oeclass":
			file = "classes/%s.oeclass" % file

		if not file in string.split(__inherit_cache):
			debug(2, "OE %s:%d: inheriting %s" % (fn, lineno, file))
			__inherit_cache += " %s" % file
			include(fn, file, d)
	data.setVar('__inherit_cache', __inherit_cache, d)


def handle(fn, d = {}, include = 0):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __infunc__, __body__, __oepath_found__
	__body__ = []
	__oepath_found__ = 0
	__infunc__ = ""
	__classname__ = ""

	if include == 0:
		debug(2, "OE %s: handle(data)" % fn)
	else:
		debug(2, "OE %s: handle(data, include)" % fn)

	(root, ext) = os.path.splitext(os.path.basename(fn))
	if ext == ".oeclass":
		__classname__ = root
		classes.append(__classname__)

	init(d)
	if include == 0:
		data.inheritFromOS(2, d)

	oldfile = data.getVar('FILE', d)

	fn = obtain(fn, d)
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

	data.setVar('FILE', fn, d)

	if ext != ".oeclass":
		import string
		i = string.split(data.getVar("INHERIT", d, 1) or "")
		if not "base" in i and __classname__ != "base":
			i[0:0] = ["base"]
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
		if include == 0:
			set_automatic_vars(fn, d, include)
			data.expandKeys(d)
			data.update_data(d)
			set_additional_vars(fn, d, include)
			for var in d.keys():
				if data.getVarFlag(var, 'handler', d):
					oe.event.register(data.getVar(var, d))
					continue
			
				if not data.getVarFlag(var, 'task', d):
					continue
				
				deps = data.getVarFlag(var, 'deps', d) or []
				postdeps = data.getVarFlag(var, 'postdeps', d) or []
				oe.build.add_task(var, deps, d)
				for p in postdeps:
					pdeps = data.getVarFlag(p, 'deps', d) or []
					pdeps.append(var)
					data.setVarFlag(p, 'deps', pdeps, d)
					oe.build.add_task(p, pdeps, d)
	if oldfile:
		data.setVar('FILE', oldfile, d)
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
			__body__.append(s)
		return
			
	m = __func_start_regexp__.match(s)
	if m:
		__infunc__ = m.group("func")
		key = __infunc__
		if data.getVar(key, d):
			# clean up old version of this piece of metadata, as its
			# flags could cause problems
			data.setVarFlag(key, 'python', None, d)
		if m.group("py") is not None:
			data.setVarFlag(key, "python", "1", d)
		else:
			data.setVarFlag(key, "python", None, d)
		return

	__word__ = re.compile(r"\S+")

	m = __export_func_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		for f in n:
			allvars = []
			allvars.append(f)
			allvars.append("%s_%s" % (classes[-1], f))

			vars = [[ allvars[0], allvars[1] ]]
			if len(classes) > 1 and classes[-2] is not None:
				allvars.append("%s_%s" % (classes[-2], f))
				vars = []
				vars.append([allvars[2], allvars[1]])
				vars.append([allvars[0], allvars[2]])

			for (var, calledvar) in vars:
				if data.getVar(var, d) and not data.getVarFlag(var, 'export_func', d):
					continue

				# clean up after possible old flags
				if data.getVar(var, d):
					data.setVarFlag(var, 'python', None, d)
					data.setVarFlag(var, 'func', None, d)

				for flag in [ "func", "python" ]:
					if data.getVarFlag(calledvar, flag, d):
						data.setVarFlag(var, flag, data.getVarFlag(calledvar, flag, d), d)
				for flag in [ "dirs" ]:
					if data.getVarFlag(var, flag, d):
						data.setVarFlag(calledvar, flag, data.getVarFlag(var, flag, d), d)

				if data.getVarFlag(calledvar, "python", d):
					data.setVar(var, "\treturn exec_func('%s', d)\n" % calledvar, d)
				else:
					data.setVar(var, "\t%s\n" % calledvar, d)
				data.setVarFlag(var, 'export_func', '1', d)

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

__pkgsplit_cache__={}
def vars_from_file(mypkg, d):
	if not mypkg:
		return (None, None, None)
	if __pkgsplit_cache__.has_key(mypkg):
		return __pkgsplit_cache__[mypkg]
		
	myfile = os.path.splitext(os.path.basename(mypkg))
	parts = string.split(myfile[0], '_')
	__pkgsplit_cache__[mypkg] = parts
	exp = 3 - len(parts)
	tmplist = []
	while exp != 0:
		exp -= 1
		tmplist.append(None)
	parts.extend(tmplist)
	return parts

def set_automatic_vars(file, d, include):
	"""Deduce per-package environment variables"""

	debug(2, "OE %s: setting automatic vars" % file)
#	pkg = oe.catpkgsplit(file)
#	pkg = vars_from_fn(file, d)
#	if None in pkg:
#		fatal("package file not in valid format")
#	if not data.getVar('CATEGORY', d):
#		if pkg[0] is None:
#			fatal("package file not in valid format")
#		data.setVar('CATEGORY', pkg[0], d)
#	if not data.getVar('PN', d):
#		if pkg[1] is None:
#			fatal("package file not in valid format")
#		data.setVar('PN', pkg[1], d)
#	if not data.getVar('PV', d):
#		if pkg[2] is None:
#			fatal("package file not in valid format")
#		data.setVar('PV', pkg[2], d)
#	if not data.getVar('PR', d):
#		if pkg[3] is None:
#			fatal("package file not in valid format")
#		data.setVar('PR', pkg[3], d)

	data.setVar('P', '${PN}-${PV}', d)
	data.setVar('PF', '${P}-${PR}', d)

	for t in [ os.path.dirname(file), '${TOPDIR}/${CATEGORY}' ]:
		if data.getVar('FILESDIR', d):
			break
		for s in [ '${PF}', 
			  '${PN}-${PV}',
			  '${PN}',
			  'files',
			  '']:
			path = data.expand(os.path.join(t, s), d)
			if not os.path.isabs(path):
				path = os.path.abspath(path)
			if os.access(path, os.R_OK):
				data.setVar('FILESDIR', path, d)
				break

	if not data.getVar('WORKDIR', d):
		data.setVar('WORKDIR', '${TMPDIR}/${CATEGORY}/${PF}', d)
	if not data.getVar('T', d):
		data.setVar('T', '${WORKDIR}/temp', d)
	if not data.getVar('D', d):
		data.setVar('D', '${WORKDIR}/image', d)
	if not data.getVar('S', d):
		data.setVar('S', '${WORKDIR}/${P}', d)
	if not data.getVar('SLOT', d):
		data.setVar('SLOT', '0', d)
	if include == 0:
		data.inheritFromOS(3, d)

def set_additional_vars(file, d, include):
	"""Deduce rest of variables, e.g. ${A} out of ${SRC_URI}"""

	debug(2,"OE %s: set_additional_vars" % file)

	if include == 0:
		data.inheritFromOS(4, d)
	src_uri = data.getVar('SRC_URI', d)
	if not src_uri:
		return
	src_uri = data.expand(src_uri, d)

	# Do we already have something in A?
	a = data.getVar('A', d)
	if a:
		a = data.expand(a, d).split()
	else:
		a = []

	from oe import fetch
	try:
		fetch.init(src_uri.split())
	except fetch.NoMethodError:
		pass

	a += fetch.localpaths(d)
	del fetch
	data.setVar('A', string.join(a), d)


# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
