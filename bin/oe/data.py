#!/usr/bin/python
"""
OpenEmbedded 'Data' implementations

Functions for interacting with the data structure used by the
OpenEmbedded (http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

import sys, os, re, time, types
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
	if not var in d:
		d[var] = {}

	if not "flags" in d[var]:
		d[var]["flags"] = {}

__setvar_regexp__ = {}
__setvar_regexp__["_append"]  = re.compile('(?P<base>.*?)%s(_(?P<add>.*))?' % "_append")
__setvar_regexp__["_prepend"] = re.compile('(?P<base>.*?)%s(_(?P<add>.*))?' % "_prepend")
__setvar_regexp__["_delete"]  = re.compile('(?P<base>.*?)%s(_(?P<add>.*))?' % "_delete")

def setVar(var, value, d = _data):
	"""Set a variable to a given value

	Example:
		>>> setVar('TEST', 'testcontents')
		>>> print getVar('TEST')
		testcontents
	"""
	for v in ["_append", "_prepend", "_delete"]:
		match = __setvar_regexp__[v].match(var)
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

	if not var in d:
		initVar(var, d)
	if getVarFlag(var, 'matchesenv', d):
		delVarFlag(var, 'matchesenv', d)
		setVarFlag(var, 'export', 1, d)
	d[var]["content"] = value

def getVar(var, d = _data, exp = 0):
	"""Gets the value of a variable

	Example:
		>>> setVar('TEST', 'testcontents')
		>>> print getVar('TEST')
		testcontents
	"""
	if not var in d or not "content" in d[var]:
		return None
	if exp:
		return expand(d[var]["content"], d, var)
	return d[var]["content"]

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
	if var in d:
		del d[var]

def setVarFlag(var, flag, flagvalue, d = _data):
	"""Set a flag for a given variable to a given value

	Example:
		>>> setVarFlag('TEST', 'python', 1)
		>>> print getVarFlag('TEST', 'python')
		1
	"""
#	print "d[%s][\"flags\"][%s] = %s" % (var, flag, flagvalue)
	if not var in d:
		initVar(var, d)
	d[var]["flags"][flag] = flagvalue

def getVarFlag(var, flag, d = _data):
	"""Gets given flag from given var

	Example:
		>>> setVarFlag('TEST', 'python', 1)
		>>> print getVarFlag('TEST', 'python')
		1
	"""
	if var in d and "flags" in d[var] and flag in d[var]["flags"]:
		return d[var]["flags"][flag]
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
	if var in d and "flags" in d[var] and flag in d[var]["flags"]:
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
	if not var in d:
		initVar(var, d)
	d[var]["flags"] = flags

def getVarFlags(var, d = _data):
	"""Gets a variable's flags

	Example:
		>>> setVarFlag('TEST', 'test', 'blah')
		>>> print getVarFlags('TEST')['test']
		blah
	"""
	if var in d and "flags" in d[var]:
		return d[var]["flags"]
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
	if var in d and "flags" in d[var]:
		del d[var]["flags"]

def getData(d = _data):
	"""Returns the data object used"""
	return d

def setData(newData, d = _data):
	"""Sets the data object to the supplied value"""
	d = newData

__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")

def expand(s, d = _data, varname = None):
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
		if varname and key:
			if varname == key:
				raise Exception("variable %s references itself!" % varname)
		var = getVar(key, d, 1)
		if var is not None:
			setVar(key, var, d)
			return var
		else:
			return match.group()

	def python_sub(match):
		code = match.group()[3:-1]
		import oe
		locals()['d'] = d
		try:
			s = eval(code)
		except:
			oe.note("%s:%s while evaluating:\n%s" % (sys.exc_info()[0], sys.exc_info()[1], code))
			raise
		if type(s) == types.IntType: s = str(s)
		return s

	if type(s) is not types.StringType: # sanity check
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
		if key == ekey:
			continue
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
		if type(val) is not types.StringType:
			continue
		expanded = expand(val, readdata)
#		print "key is %s, val is %s, expanded is %s" % (key, val, expanded)
		if val != expanded:
			setVar(key, expanded, alterdata)

import os

def inheritFromOS(d = _data):
	"""Inherit variables from the environment."""
	# fakeroot needs to be able to set these
	non_inherit_vars = [ "LD_LIBRARY_PATH", "LD_PRELOAD" ]
	for s in os.environ.keys():
		if not s in non_inherit_vars:
			try:
				setVar(s, os.environ[s], d)
				setVarFlag(s, 'matchesenv', '1', d)
			except TypeError:
				pass

import sys

def emit_var(var, o=sys.__stdout__, d = _data, all=False):
	"""Emit a variable to be sourced by a shell."""
	if getVarFlag(var, "python", d):
		return 0

	try:
		val = getVar(var, d, 1)
	except:
		o.write('# expansion of %s threw %s\n' % (var, sys.exc_info()[0]))
		return 0
		
	if type(val) is not types.StringType:
		return 0

	if getVarFlag(var, 'matchesenv', d):
		return 0

	if var.find("-") != -1 or var.find(".") != -1 or var.find('{') != -1 or var.find('}') != -1 or var.find('+') != -1:
		return 0

	val.rstrip()
	if not val:
		return 0

	if getVarFlag(var, "func", d):
		# NOTE: should probably check for unbalanced {} within the var
		o.write("%s() {\n%s\n}\n" % (var, val))
	else:
		if getVarFlag(var, "export", d):
			o.write('export ')
		else:
			if not all:
				return 0
		# if we're going to output this within doublequotes,
		# to a shell, we need to escape the quotes in the var
		alter = re.sub('"', '\\"', val.strip())
		o.write('%s="%s"\n' % (var, alter))
	return 1


def emit_env(o=sys.__stdout__, d = _data, all=False):
	"""Emits all items in the data store in a format such that it can be sourced by a shell."""

	env = d.keys()

	for e in env:
		if getVarFlag(e, "func", d):
			continue
		emit_var(e, o, d, all) and o.write('\n')

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
	overrides = (getVar('OVERRIDES', d, 1) or "").split(':') or []

	def applyOverrides(var, d = _data):
		if not overrides:
			debug(1, "OVERRIDES not defined, nothing to do")
			return
		val = getVar(var, d)
		for o in overrides:
			if var.endswith("_" + o):
				l = len(o)+1
				name = var[:-l]
				d[name] = d[var]

	for s in d.keys():
		applyOverrides(s, d)
		sval = getVar(s, d) or ""

		# Handle line appends:
		for (a, o) in getVarFlag(s, '_append', d) or []:
			delVarFlag(s, '_append', d)
			if o:
				if not o in overrides:
					break
			sval+=a
			setVar(s, sval, d)

		# Handle line prepends
		for (a, o) in getVarFlag(s, '_prepend', d) or []:
			delVarFlag(s, '_prepend', d)
			if o:
				if not o in overrides:
					break
			sval=a+sval
			setVar(s, sval, d)

		# Handle line deletions
		name = s + "_delete"
		nameval = getVar(name, d)
		if nameval:
			sval = getVar(s, d)
			if sval:
				new = ''
				pattern = nameval.replace('\n','').strip()
				for line in sval.split('\n'):
					if line.find(pattern) == -1:
						new = new + '\n' + line
				setVar(s, new, d)
				dodel.append(name)

	# delete all environment vars no longer needed
	for s in dodel:
		delVar(s, d)

def _test():
	"""Start a doctest run on this module"""
	import doctest
	from oe import data
	doctest.testmod(data)

if __name__ == "__main__":
	_test()
