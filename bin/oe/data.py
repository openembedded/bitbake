#!/usr/bin/python
"""
OpenEmbedded 'Data' implementations

Functions for interacting with the data structure used by the
OpenEmbedded (http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

import sys, os, time
if sys.argv[0][-5:] == "pydoc":
	path = os.path.dirname(os.path.dirname(sys.argv[1]))
else:
	path = os.path.dirname(os.path.dirname(sys.argv[0]))
sys.path.append(path)

from oe import note, debug

def init():
	return {}

_data = init()

def initVar(var, d = _data):
	"""Non-destructive var init for data structure"""
	if not d.has_key(var):
		d[var] = {}

	if not d[var].has_key("flags"):
		d[var]["flags"] = {}

def setVar(var, value, d = _data):
	"""Set a variable to a given value

	Example:
		>>> setVar('TEST', 'testcontents')
		>>> print getVar('TEST')
		testcontents
	"""
	for v in ["_append", "_prepend", "_delete"]:
		match = re.match('(?P<base>.*?)%s(_(?P<add>.*))?' % v, var)
		if match:
			base = match.group('base')
			override = match.group('add')
			l = getVarFlag(base, v, d) or []
			if override == 'delete':
				if l.count([value, None]):
					del l[l.index([value, None])]
			l.append([value, override])
			setVarFlag(base, v, l, d)
			return
		
	try:
		d[var]["content"] = value 
	except KeyError:
		initVar(var, d)
		d[var]["content"] = value 

def getVar(var, d = _data, exp = 0):
	"""Gets the value of a variable

	Example:
		>>> setVar('TEST', 'testcontents')
		>>> print getVar('TEST')
		testcontents
	"""
	try:
		if exp:
			return expand(d[var]["content"], d)
		else:
			return d[var]["content"]
	except KeyError:
		return None

def delVar(var, d = _data):
	"""Removes a variable from the data set

	Example:
		>>> setVar('TEST', 'testcontents')
		>>> print getVar('TEST')
		testcontents
		>>> delVar('TEST')
		>>> print getVar('TEST')
		None
	"""
	del d[var]

def setVarFlag(var, flag, flagvalue, d = _data):
	"""Set a flag for a given variable to a given value

	Example:
		>>> setVarFlag('TEST', 'python', 1)
		>>> print getVarFlag('TEST', 'python')
		1
	"""
#	print "d[%s][\"flags\"][%s] = %s" % (var, flag, flagvalue)
	try:
		d[var]["flags"][flag] = flagvalue
	except KeyError:
		initVar(var, d)
		d[var]["flags"][flag] = flagvalue

def getVarFlag(var, flag, d = _data):
	"""Gets given flag from given var

	Example:
		>>> setVarFlag('TEST', 'python', 1)
		>>> print getVarFlag('TEST', 'python')
		1
	"""
	try:
		return d[var]["flags"][flag]
	except KeyError:
		return None

def delVarFlag(var, flag, d = _data):
	"""Removes a given flag from the variable's flags

	Example:
		>>> setVarFlag('TEST', 'testflag', 1)
		>>> print getVarFlag('TEST', 'testflag')
		1
		>>> delVarFlag('TEST', 'testflag')
		>>> print getVarFlag('TEST', 'testflag')
		None
		
	"""
	del d[var]["flags"][flag]

def setVarFlags(var, flags, d = _data):
	"""Set the flags for a given variable
	
	Example:
		>>> myflags = {}
		>>> myflags['test'] = 'blah'
		>>> setVarFlags('TEST', myflags)
		>>> print getVarFlag('TEST', 'test')
		blah
	"""
	try:
		d[var]["flags"] = flags
	except KeyError:
		initVar(var, d)
		d[var]["flags"] = flags

def getVarFlags(var, d = _data):
	"""Gets a variable's flags

	Example:
		>>> setVarFlag('TEST', 'test', 'blah')
		>>> print getVarFlags('TEST')['test']
		blah
	"""
	try:
		return d[var]["flags"]
	except KeyError:
		return None

def delVarFlags(var, d = _data):
	"""Removes a variable's flags

	Example:
		>>> setVarFlag('TEST', 'testflag', 1)
		>>> print getVarFlag('TEST', 'testflag')
		1
		>>> delVarFlags('TEST')
		>>> print getVarFlags('TEST')
		None
		
	"""
	del d[var]["flags"]

def getData(d = _data):
	"""Returns the data object used"""
	return d

def setData(newData, d = _data):
	"""Sets the data object to the supplied value"""
	d = newData

import re

__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")

def expand(s, d = _data):
	"""Variable expansion using the data store.

	Example:
		Standard expansion:
		>>> setVar('A', 'sshd')
		>>> print expand('/usr/bin/${A}')
		/usr/bin/sshd

		Python expansion:
		>>> print expand('result: ${@37 * 72}')
		result: 2664
	"""
	def var_sub(match):
		key = match.group()[2:-1]
		#print "got key:", key
		var = getVar(key, d)
		if var is not None:
			return var
		else:
			return match.group()

	def python_sub(match):
		code = match.group()[3:-1]
		import oe
		locals()['d'] = d
		s = eval(code)
		import types
		if type(s) == types.IntType: s = str(s)
		return s

	if s is None: # sanity check
		return s

	while s.find('$') != -1:
		olds = s
		s = __expand_var_regexp__.sub(var_sub, s)
		s = __expand_python_regexp__.sub(python_sub, s)
		if len(s)>2048:
			debug(1, "expanded string too long")
			return s
		if s == olds: break
	return s

def expandKeys(alterdata = _data, readdata = None):
	if readdata == None:
		readdata = alterdata

	for key in alterdata.keys():
		ekey = expand(key, readdata)
		val = getVar(key, alterdata)
		if val is None:
			continue
		setVar(ekey, val, alterdata)

def expandData(alterdata = _data, readdata = None):
	"""For each variable in alterdata, expand it, and update the var contents.
	   Replacements use data from readdata.

	Example:
		>>> a=init()
		>>> b=init()
		>>> setVar("dlmsg", "dl_dir is ${DL_DIR}", a)
		>>> setVar("DL_DIR", "/path/to/whatever", b)
		>>> expandData(a, b)
		>>> print getVar("dlmsg", a)
		dl_dir is /path/to/whatever
	   """
	if readdata == None:
		readdata = alterdata

	for key in alterdata.keys():
		val = getVar(key, alterdata)
		if val is None:
			continue
		expanded = expand(val, readdata)
#		print "key is %s, val is %s, expanded is %s" % (key, val, expanded)
		setVar(key, expanded, alterdata)

import os

def inheritFromOS(pos, d = _data):
	"""Inherit variables from the environment.

	Example:
		>>> d=init()
		>>> os.environ["TEST"] = "test"
		>>> setVarFlag('TEST', 'inherit', '1', d)
		>>> inheritFromOS(1, d)
		>>> print getVar('TEST', d)
		test
	"""
	pos = str(pos)
	for s in os.environ.keys():
		try:
			if pos == "1":
				setVar(s, os.environ[s], d)
			else:
				inherit = getVarFlag(s, "inherit", d)
				if inherit is not None and inherit == pos:
					setVar(s, os.environ[s], d)
		except KeyError:
			pass

import sys, string

def emit_var(var, o=sys.__stdout__, d = _data):
	"""Emit a variable to be sourced by a shell."""
	if getVarFlag(var, "python", d):
		return 0

	val = getVar(var, d, 1)
	if val is None:
		debug(2, "Warning, %s variable is None, not emitting" % var)
		return 0

	if var.find("-") != -1 or var.find(".") != -1 or var.find('{') != -1 or var.find('}') != -1 or var.find('+') != -1:
		debug(2, "Warning, %s variable name contains an invalid char, not emitting to shell" % var)
		return 0

	if getVarFlag(var, "func", d):
		# NOTE: should probably check for unbalanced {} within the var
		o.write("%s() {\n%s\n}\n" % (var, val))
		return 1
	else:	
		if getVarFlag(var, "export", d):
			o.write('export ')
		# if we're going to output this within doublequotes,
		# to a shell, we need to escape the quotes in the var
		alter = re.sub('"', '\\"', val.strip())
		o.write('%s="%s"\n' % (var, alter))
		return 1


def emit_env(o=sys.__stdout__, d = _data):
	"""Emits all items in the data store in a format such that it can be sourced by a shell."""

	oepath = string.split(getVar('OEPATH', d, 1) or "", ":")
	path = getVar('PATH', d)
	if path:
		path = path.split(":")
		for p in oepath:
			path[0:0] = [ os.path.join("%s" % p, "bin/build") ]
		pset = []
		pcount = 0
		for p in path[:]:
			if p not in pset:
				pset[0:0] = [ p ]
				pcount += 1
				continue
			del path[pcount]
		setVar('PATH', expand(string.join(path, ":"), d), d)

	expandData(d)
	env = d.keys()

	for e in env:
		if getVarFlag(e, "func", d):
			continue
		emit_var(e, o, d) and o.write('\n')

	for e in env:
		if not getVarFlag(e, "func", d):
			continue
		emit_var(e, o, d) and o.write('\n')

def update_data(d = _data):
	"""Modifies the environment vars according to local overrides and commands.
	Examples:
		Appending to a variable:
		>>> setVar('TEST', 'this is a')
		>>> setVar('TEST_append', ' test')
		>>> setVar('TEST_append', ' of the emergency broadcast system.')
		>>> update_data()
		>>> print getVar('TEST')
		this is a test of the emergency broadcast system.

		Prepending to a variable:
		>>> setVar('TEST', 'virtual/libc')
		>>> setVar('TEST_prepend', 'virtual/tmake ')
		>>> setVar('TEST_prepend', 'virtual/patcher ')
		>>> update_data()
		>>> print getVar('TEST')
		virtual/patcher virtual/tmake virtual/libc

		Overrides:
		>>> setVar('TEST_arm', 'target')
		>>> setVar('TEST_ramses', 'machine')
		>>> setVar('TEST_local', 'local')
	        >>> setVar('OVERRIDES', 'arm')
	
		>>> setVar('TEST', 'original')
		>>> update_data()
		>>> print getVar('TEST')
		target
	
	        >>> setVar('OVERRIDES', 'arm:ramses:local')
		>>> setVar('TEST', 'original')
		>>> update_data()
		>>> print getVar('TEST')
		local
	"""

	debug(2, "update_data()")

	# can't do delete env[...] while iterating over the dictionary, so remember them
	dodel = []
	overrides = string.split(getVar('OVERRIDES', d, 1) or "", ":") or []

	def applyOverrides(var, d = _data):
		if not overrides:
			debug(1, "OVERRIDES not defined, nothing to do")
			return
		val = getVar(var, d)
		flags = getVarFlags(var, d)
		for o in overrides:
			name = "%s_%s" % (var, o)
			nameval = getVar(name, d)
			if nameval:
				nameflags = getVarFlags(name, d)
				setVar(var, nameval, d)
				setVarFlags(var, nameflags, d)

	for s in d.keys():
		applyOverrides(s, d)
		sval = getVar(s, d) or ""

		# Handle line appends:
		for (a, o) in getVarFlag(s, '_append', d) or []:
			try:
				delVarFlag(s, '_append', d)
			except KeyError:
				pass
			if o:
				if not o in overrides:
					break
			sval+=a
			setVar(s, sval, d)
		
		# Handle line prepends
		for (a, o) in getVarFlag(s, '_prepend', d) or []:
			try:
				delVarFlag(s, '_prepend', d)
			except KeyError:
				pass
			if o:
				if not o in overrides:
					break
			sval=a+sval
			setVar(s, sval, d)

		# Handle line deletions
		name = "%s_delete" % s
		nameval = getVar(name, d)
		if nameval:
			sval = getVar(s, d)
			if sval:
				new = ''
				pattern = string.replace(nameval,"\n","").strip()
				for line in string.split(sval,"\n"):
					if line.find(pattern) == -1:
						new = new + '\n' + line
				setVar(s, new, d)
				dodel.append(name)

	# delete all environment vars no longer needed
	for s in dodel:
		delVar(s, d)

	inheritFromOS(5)

def _test():
	"""Start a doctest run on this module"""
	import doctest
	from oe import data
	doctest.testmod(data)

if __name__ == "__main__":
	_test()
