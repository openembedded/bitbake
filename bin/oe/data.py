#!/usr/bin/python

# proposed new way of structuring environment data for the
# OpenEmbedded buildsystem

from oe import debug

_data = {}

def init(d = _data):
	d = {}

def initVar(var, d = _data):
	"""Non-destructive var init for data structure"""
	if not d.has_key(var):
		d[var] = {}

	if not d[var].has_key("flags"):
		d[var]["flags"] = {}

def setVar(var, value, d = _data):
	"""Set a variable to a given value"""
	try:
		d[var]["content"] = value 
	except KeyError:
		initVar(var, d)
		d[var]["content"] = value 

def getVar(var, d = _data):
	"""Gets the value of a variable"""
	try:
		return d[var]["content"]
	except KeyError:
		return None

def setVarFlag(var, flag, flagvalue, d = _data):
	"""Set a flag for a given variable to a given value"""
#	print "d[%s][\"flags\"][%s] = %s" % (var, flag, flagvalue)
	try:
		d[var]["flags"][flag] = flagvalue
	except KeyError:
		initVar(var, d)
		d[var]["flags"][flag] = flagvalue

def getVarFlag(var, flag, d = _data):
	"""Gets given flag from given var""" 
	try:
		return d[var]["flags"][flag]
	except KeyError:
		return None

def setVarFlags(var, flags, d = _data):
	"""Set the flags for a given variable"""
	try:
		d[var]["flags"] = flags
	except KeyError:
		initVar(var, d)
		d[var]["flags"] = flags

def getVarFlags(var, d = _data):
	"""Gets a variable's flags"""
	try:
		return d[var]["flags"]
	except KeyError:
		return None

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
	"""Can expand variables with their values from env[]

	>>> env['MID'] = 'drin'
	>>> print expand('vorher ${MID} dahinter')
	vorher drin dahinter

	Unset variables are kept as is:

	>>> print expand('vorher ${MID} dahinter ${UNKNOWN}')
	vorher drin dahinter ${UNKNOWN}

	A syntax error just returns the string:

	>>> print expand('${UNKNOWN')
	${UNKNOWN

	We can evaluate python code:

	>>> print expand('${@ "Test"*3}')
	TestTestTest
	>>> env['START'] = '0x4000'
	>>> print expand('${@ hex(0x1000000+${START}) }')
	0x1004000

	We are able to handle recursive definitions:

	>>> env['ARCH'] = 'arm'
	>>> env['OS'] = 'linux'
	>>> env['SYS'] = '${ARCH}-${OS}'
	>>> print expand('${SYS}')
	arm-linux
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
		s = eval(code)
		if type(s) == types.IntType: s = str(s)
		return s

	if s is None: # sanity check
		return s

	while s.find('$') != -1:
		olds = s
		s = __expand_var_regexp__.sub(var_sub, s)
		s = __expand_python_regexp__.sub(python_sub, s)
		if len(s)>2048:
			fatal("expanded string too long")
		if s == olds: break
	return s

def expandData(alterdata = _data, readdata = _data):
	"""For each variable in alterdata, expand it, and update the var contents.
	   Replacements use data from readdata.

	   Example:
	   to = {}
	   from = {}
	   setVar("dlmsg", "dl_dir is ${DL_DIR}", to)
	   setVar("DL_DIR", "/path/to/whatever", from)
	   expandData(to, from)
	   getVar("dlmsg", to) returns "dl_dir is /path/to/whatever"
	   """
	for key in alterdata.keys():
		val = getVar(key, alterdata)
		if val is None:
			continue
		expanded = expand(val, readdata)
#		print "key is %s, val is %s, expanded is %s" % (key, val, expanded)
		setVar(key, expanded, alterdata)

import os

def inheritFromOS(pos, d = _data):
	pos = str(pos)
	for s in os.environ.keys():
		try:
			inherit = getVarFlag(s, "inherit", d)
			if inherit is not None and inherit == pos:
				setVar(s, os.environ[s], d)
		except KeyError:
			pass

import sys

def emit_env(o=sys.__stdout__, d = _data):
	"""This prints the data so that it can later be sourced by a shell
	Normally, it prints to stdout, but this it can be redirectory to some open file handle

	It is used by exec_shell_func().
	"""

#	o.write('\nPATH="' + os.path.join(projectdir, 'bin/build') + ':${PATH}"\n')

	expandData(d, d)
	env = d.keys()

	for e in env:
		if getVarFlag(e, "func", d):
			continue
		if getVarFlag(e, "python", d):
			continue
		o.write('\n')
		if getVarFlag(e, "export", d):
			o.write('export ')
		val = getVar(e, d)
		if val is None:
			debug(2, "Warning, %s variable is None" % e)
			continue
		o.write(e+'="'+ val + '"\n')	

	for e in env:
		if not getVarFlag(e, "func", d):
			continue
		if getVarFlag(e, "python", d):
			continue
		o.write("\n" + e + '() {\n' + getVar(e, d) + '}\n')

