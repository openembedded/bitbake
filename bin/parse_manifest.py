#!/usr/bin/env python

import os, sys, string

srcdir = "${WORKDIR}"
destdir = "${D}"
pkgdestdir = "${WORKDIR}/install"

manifest = sys.__stdin__
if len(sys.argv) == 2:
	manifest = file(sys.argv[1], "r")

def mangle_path_stage(field, fields):
	path = fields[field]
	if not path:
		return None
	if field == "src":
		if os.path.isabs(path):
			return path
		if path.startswith('/'):
			path = path[1:]
		path = os.path.join(srcdir, path)
	elif field == "dest":	
		if os.path.isabs(path):
			return path
		if path.startswith('/'):
			path = path[1:]
		path = os.path.join(destdir, path)
		libpath = os.path.join(destdir, '${libdir}')
		incpath = os.path.join(destdir, '${includedir}')
		if path.startswith(libpath):
			path = "${STAGING_LIBDIR}" + path[len(libpath):]
		elif path.startswith(incpath):
			path = "${STAGING_INCDIR}" + path[len(incpath):]
		else:
			return None	
	return path	

def mangle_path_install(field, fields):
	path = fields[field]
	if not path:
		return None
	if field == "src":
		if os.path.isabs(path):
			return path
		if path.startswith('/'):
			path = path[1:]
		path = os.path.join(srcdir, path)
	elif field == "dest":
		if os.path.isabs(path):
			return path
		if path.startswith('/'):
			path = path[1:]
		path = os.path.join(destdir, path)
	return path

def mangle_path_populate(field, fields):
	path = fields[field]
	pkg = fields["pkg"]
	if None in (pkg, path):
		return None
	if field == "src":
		if os.path.isabs(path):
			return path
		if path.startswith('/'):
			path = path[1:]
		path = os.path.join(srcdir, path)
	elif field == "dest":
		if os.path.isabs(path):
			return path
		if path.startswith('/'):
			path = path[1:]
		path = os.path.join(pkgdestdir, pkg, path)
	return path

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

def handle_directory(fields, commands, mangle_path):
	dest = fields["dest"]
	if not dest:
		return
	if os.path.isabs(dest):
		return
	if dest.startswith('/'):
		dest = dest[1:]
	cmd = "install -d "
	dest = mangle_path("dest", fields)
	if not dest:
		return
	cmd += os.path.dirname(dest)
	if not cmd in commands:
		commands.append(cmd)

def handle_file(fields, commands, mangle_path):
	if None in (fields["src"], fields["dest"]):
		return

	handle_directory(fields, commands, mangle_path)
	src = mangle_path("src", fields)
	if not src:
		return
	dest = mangle_path("dest", fields)
	if not dest:
		return
	mode = fields["mode"]

	cmd = "install "
	if mode:
		cmd += "-m " + mode + " "
	cmd += src + " " + dest
	if not cmd in commands:
		commands.append(cmd)

def handle_symbolic_link(fields, commands, mangle_path):
	if None in (fields["src"], fields["dest"]):
		return

	handle_directory(fields, commands, mangle_path)
	dest = mangle_path("dest", fields)
	src = fields["src"]
	if None in (src, dest):
		return

	cmd = "ln -sf " + src + " " + dest
	if not cmd in commands:
		commands.append(cmd)

def handle_hard_link(fields, commands, mangle_path):
	if None in (fields["src"], fields["dest"]):
		return

	handle_directory(fields, commands, mangle_path)
	src = mangle_path("src", fields)
	dest = mangle_path("dest", fields)
	if None in (src, dest):
		return

	cmd = "ln -f " + src + " " + dest
	if not cmd in commands:
		commands.append(cmd)

commands = list()
commands_populate = list()
commands_stage = list()
entries = list()	
while 1:
	line = manifest.readline()
	if not line:
		break
	if line.startswith("#"):
		# skip comments
		continue
	fields = getfields(line)
	if not fields:
		continue

	if not fields in entries:
		entries.append(fields)
			
	if fields["type"] == "d":
		handle_directory(fields, commands, mangle_path_install)
	if fields["type"] == "f":
		handle_file(fields, commands, mangle_path_install)
	if fields["type"] == "s":
		handle_symbolic_link(fields, commands, mangle_path_install)
	if fields["type"] == "h":
		handle_hard_link(fields, commands, mangle_path_install)

	if fields["type"] == "d":
		handle_directory(fields, commands_populate, mangle_path_populate)
	if fields["type"] == "f":
		handle_file(fields, commands_populate, mangle_path_populate)
	if fields["type"] == "s":
		handle_symbolic_link(fields, commands_populate, mangle_path_populate)
	if fields["type"] == "h":
		handle_hard_link(fields, commands_populate, mangle_path_populate)

	if fields["type"] == "d":
		handle_directory(fields, commands_stage, mangle_path_stage)
	if fields["type"] == "f":
		handle_file(fields, commands_stage, mangle_path_stage)
	if fields["type"] == "s":
		handle_symbolic_link(fields, commands_stage, mangle_path_stage)
	
print "do_stage () {"
print '\t' + string.join(commands_stage, '\n\t')
print "}"
print "do_install () {"
print '\t' + string.join(commands, '\n\t')
print "}"
print "do_populate () {"
print '\t' + string.join(commands_populate, '\n\t')
print "}"
