#!/usr/bin/env python

import os, sys, string

srcdir = "${WORKDIR}"
destdir = "${D}"

manifest = sys.__stdin__
if len(sys.argv) == 2:
	manifest = file(sys.argv[1], "r")

def mangle_srcpath(fields):
	if not fields["src"]:
		return
	if os.path.isabs(fields["src"]):
		return
	if fields["src"].startswith('/'):
		fields["src"] = fields["src"][1:]
	fields["src"] = os.path.join(srcdir, fields["src"])

def mangle_destpath(fields):
	if not fields["dest"]:
		return
	if os.path.isabs(fields["dest"]):
		return
	if fields["dest"].startswith('/'):
		fields["dest"] = fields["dest"][1:]
	fields["dest"] = os.path.join(destdir, fields["dest"])

def getfields(line):
	fields = {}
	fieldmap = ( "src", "dest", "type", "mode", "uid", "gid", "major", "minor", "start", "inc", "count" )
	for f in xrange(len(fieldmap)):
		fields[fieldmap[f]] = None
	
	if not line:
		return None

	splitline = line.split()
	if not len(splitline):
		return None

	try:
		for f in xrange(len(fieldmap)):
			fields[fieldmap[f]] = splitline[f]
	except IndexError:
		pass
	return fields

def handle_directory(fields, commands):
	if not fields["dest"]:
		return
	cmd = "install -d "
	cmd += os.path.join(destdir, os.path.dirname(fields["dest"])[1:])
	if not cmd in commands:
		commands.append(cmd)

def handle_file(fields, commands):
	if None in (fields["src"], fields["dest"]):
		return

	handle_directory(fields, commands)
	mangle_srcpath(fields)
	mangle_destpath(fields)

	cmd = "install "
	if fields["mode"]:
		cmd += "-m " + fields["mode"] + " "
	cmd += fields["src"] + " " + fields["dest"]
	if not cmd in commands:
		commands.append(cmd)

def handle_symbolic_link(fields, commands):
	if None in (fields["src"], fields["dest"]):
		return

	handle_directory(fields, commands)
	mangle_destpath(fields)

	cmd = "ln -sf " + fields["src"] + " " + fields["dest"]
	if not cmd in commands:
		commands.append(cmd)

def handle_hard_link(fields, commands):
	if None in (fields["src"], fields["dest"]):
		return

	handle_directory(fields, commands)
	mangle_srcpath(fields)
	mangle_destpath(fields)

	cmd = "ln -f " + fields["src"] + " " + fields["dest"]
	if not cmd in commands:
		commands.append(cmd)

commands = list()
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

	if fields["type"] == "d":
		handle_directory(fields, commands)
	if fields["type"] == "f":
		handle_file(fields, commands)
	if fields["type"] == "s":
		handle_symbolic_link(fields, commands)
	if fields["type"] == "h":
		handle_hard_link(fields, commands)
print "do_install () {"
print '\t' + string.join(commands, '\n\t')
print "}"
