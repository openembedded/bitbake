#!/usr/bin/env python

import os, sys, string
import oe, oe.data

def getfields(line):
	fields = {}
	fieldmap = ( "pkg", "src", "dest", "type", "mode", "uid", "gid", "major", "minor", "start", "inc", "count" )
	for f in xrange(len(fieldmap)):
		fields[fieldmap[f]] = None

	if not line:
		return None

	splitline = line.split()
	if not len(splitline):
		return None

	try:
		for f in xrange(len(fieldmap)):
			if splitline[f] == '-':
				continue
			fields[fieldmap[f]] = splitline[f]
	except IndexError:
		pass
	return fields

def parse (mfile, d):
	manifest = []
	while 1:
		line = mfile.readline()
		if not line:
			break
		if line.startswith("#"):
			continue
		fields = getfields(oe.data.expand(line, d))
		if not fields:
			continue
		manifest.append(fields)
	return manifest

def emit (func, manifest, d):
#str = "%s () {\n" % func
	str = ""
	for line in manifest:
		emittedline = emit_line(func, line, d)
		if not emittedline:
			continue
		str += emittedline + "\n"
#	str += "}\n"
	return str

def mangle (func, line):
	src = line["src"]

	if src:
		if not os.path.isabs(src):
			src = "${WORKDIR}/" + src

	dest = line["dest"]
	if not dest:
		return

	if dest.startswith("/"):
		dest = dest[1:]

	if func is "do_install":
		dest = "${D}/" + dest

	elif func is "do_populate":
		dest = "${WORKDIR}/install/" + line["pkg"] + "/" + dest

	elif func is "do_stage":
		varmap = {}
		varmap["${bindir}"] = "${STAGING_BINDIR}"
		varmap["${libdir}"] = "${STAGING_LIBDIR}"
		varmap["${includedir}"] = "${STAGING_INCDIR}"
		varmap["${datadir}"] = "${STAGING_DIR}/share"

		matched = 0
		for key in varmap.keys():
			if dest.startswith(key):
				dest = varmap[key] + "/" + dest[len(key):]
				matched = 1
		if not matched:
			line = None
			return
	else:
		line = None
		return

	line["src"] = src
	line["dest"] = dest

def emit_line (func, line, d):
	import copy
	newline = copy.deepcopy(line)
	mangle(func, newline)
	if not newline:
		return None

	str = ""
	type = newline["type"]
	mode = newline["mode"]
	src = newline["src"]
	dest = newline["dest"]
	if type is "d":
		str = "install -d " + dest
		if mode:
			str += "-m %s " % mode
	elif type is "f":
		if not src:
			return None
		str = "install -D "
		if mode:
			str += "-m %s " % mode
		str += src + " " + dest
	del newline
	return str
