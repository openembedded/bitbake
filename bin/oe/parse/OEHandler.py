"""class for handling .oe files

   Reads the file and obtains its metadata"""

import re, oe, os, sys
import oe.fetch
from oe import debug, data, fetch, fatal

from oe.parse.ConfHandler import include, localpath, obtain, init

__func_start_regexp__    = re.compile( r"(((?P<py>python)|(?P<fr>fakeroot))\s*)*(?P<func>\w+)?\s*\(\s*\)\s*{$" )
__inherit_regexp__       = re.compile( r"inherit\s+(.+)" )
__export_func_regexp__   = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )
__addtask_regexp__       = re.compile("addtask\s+(?P<func>\w+)\s*((before\s*(?P<before>((.*(?=after))|(.*))))|(after\s*(?P<after>((.*(?=before))|(.*)))))*")
__addhandler_regexp__       = re.compile( r"addhandler\s+(.+)" )
__word__ = re.compile(r"\S+")

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

		if not file in __inherit_cache.split():
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
		debug(2, "OE " + fn + ": handle(data)")
	else:
		debug(2, "OE " + fn + ": handle(data, include)")

	(root, ext) = os.path.splitext(os.path.basename(fn))
	init(d)

	if ext == ".oeclass":
		__classname__ = root
		classes.append(__classname__)

	if include != 0:
		oldfile = data.getVar('FILE', d)
	else:
		oldfile = None

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

	if ext != ".oeclass":
		data.setVar('FILE', fn, d)
		i = (data.getVar("INHERIT", d, 1) or "").split()
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
		while s[-1] == '\\':
			s2 = f.readline()[:-1].strip()
			s = s[:-1] + s2
		feeder(lineno, s, fn, d)
	if ext == ".oeclass":
		classes.remove(__classname__)
	else:
		if include == 0:
			data.expandKeys(d)
			data.update_data(d)
			set_additional_vars(fn, d, include)
			anonqueue = data.getVar("__anonqueue", d, 1) or []
			for anon in anonqueue:
				data.setVar("__anonfunc", anon["content"], d)
				data.setVarFlags("__anonfunc", anon["flags"], d)
				from oe import build
				try:
					t = data.getVar('T', d)
					data.setVar('T', '${TMPDIR}/', d)
					build.exec_func("__anonfunc", d)
					data.delVar('T', d)
					if t:
						data.setVar('T', t, d)
				except Exception, e:
					oe.error("executing anonymous function: %s" % e)
					pass
			data.delVar("__anonqueue", d)
			data.delVar("__anonfunc", d)

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
		oe.data.setVar("FILE", oldfile, d)
	return d

def feeder(lineno, s, fn, d):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __infunc__, __body__, __oepath_found__, classes, oe
	if __infunc__:
		if s == '}':
			__body__.append('')
			data.setVar(__infunc__, '\n'.join(__body__), d)
			data.setVarFlag(__infunc__, "func", 1, d)
			if __infunc__ == "__anonymous":
				anonqueue = oe.data.getVar("__anonqueue", d) or []
				anonitem = {}
				anonitem["content"] = oe.data.getVar("__anonymous", d)
				anonitem["flags"] = oe.data.getVarFlags("__anonymous", d)
				anonqueue.append(anonitem)
				oe.data.setVar("__anonqueue", anonqueue, d)
				oe.data.delVarFlags("__anonymous", d)
				oe.data.delVar("__anonymous", d)
			__infunc__ = ""
			__body__ = []
		else:
			__body__.append(s)
		return

	if s[0] == '#': return		# skip comments

	m = __func_start_regexp__.match(s)
	if m:
		__infunc__ = m.group("func") or "__anonymous"
		key = __infunc__
		if data.getVar(key, d):
			# clean up old version of this piece of metadata, as its
			# flags could cause problems
			data.setVarFlag(key, 'python', None, d)
			data.setVarFlag(key, 'fakeroot', None, d)
		if m.group("py") is not None:
			data.setVarFlag(key, "python", "1", d)
		else:
			data.delVarFlag(key, "python", d)
		if m.group("fr") is not None:
			data.setVarFlag(key, "fakeroot", "1", d)
		else:
			data.delVarFlag(key, "fakeroot", d)
		return

	m = __export_func_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		for f in n:
			allvars = []
			allvars.append(f)
			allvars.append(classes[-1] + "_" + f)

			vars = [[ allvars[0], allvars[1] ]]
			if len(classes) > 1 and classes[-2] is not None:
				allvars.append(classes[-2] + "_" + f)
				vars = []
				vars.append([allvars[2], allvars[1]])
				vars.append([allvars[0], allvars[2]])

			for (var, calledvar) in vars:
				if data.getVar(var, d) and not data.getVarFlag(var, 'export_func', d):
					continue

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
					data.setVar(var, "\treturn oe.build.exec_func('" + calledvar + "', d)\n", d)
				else:
					data.setVar(var, "\t" + calledvar + "\n", d)
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
	if mypkg in __pkgsplit_cache__:
		return __pkgsplit_cache__[mypkg]

	myfile = os.path.splitext(os.path.basename(mypkg))
	parts = myfile[0].split('_')
	__pkgsplit_cache__[mypkg] = parts
	exp = 3 - len(parts)
	tmplist = []
	while exp != 0:
		exp -= 1
		tmplist.append(None)
	parts.extend(tmplist)
	return parts

def set_additional_vars(file, d, include):
	"""Deduce rest of variables, e.g. ${A} out of ${SRC_URI}"""

	debug(2,"OE %s: set_additional_vars" % file)

	src_uri = data.getVar('SRC_URI', d)
	if not src_uri:
		return
	src_uri = data.expand(src_uri, d)

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
	data.setVar('A', "".join(a), d)


# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
