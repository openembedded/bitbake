#!/usr/bin/python
"""
OpenEmbedded 'Build' implementation

Core code for function execution and task handling in the
OpenEmbedded (http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

from oe import debug, data, fetch, fatal, error, note, event, mkdirhier
import oe
import os

# data holds flags and function name for a given task
_task_data = data.init()

# graph represents task interdependencies
_task_graph = oe.digraph()

# stack represents execution order, excepting dependencies
_task_stack = []

# events
class FuncFailed(Exception):
	"""Executed function failed"""

class EventException(Exception):
	"""Exception which is associated with an Event."""

	def __init__(self, msg, event):
		self.event = event

	def getEvent(self):
		return self._event

	def setEvent(self, event):
		self._event = event

	event = property(getEvent, setEvent, None, "event property")

class TaskBase(event.Event):
	"""Base class for task events"""

	def __init__(self, t, d = {}):
		self.task = t
		self.data = d

	def getTask(self):
		return self._task

	def setTask(self, task):
		self._task = task

	task = property(getTask, setTask, None, "task property")

	def getData(self):
		return self._data

	def setData(self, data):
		self._data = data

	data = property(getData, setData, None, "data property")

class TaskStarted(TaskBase):
	"""Task execution started"""
	
class TaskSucceeded(TaskBase):
	"""Task execution succeeded"""

class TaskFailed(TaskBase):
	"""Task execution failed"""

class InvalidTask(TaskBase):
	"""Invalid Task"""

# functions

def init(data):
	global _task_data, _task_graph, _task_stack
	_task_data = data.init()
	_task_graph = oe.digraph()
	_task_stack = []


def exec_func(func, d, dirs = None):
	"""Execute an OE 'function'"""

	if not dirs:
		dirs = data.getVarFlag(func, 'dirs', d) or []
	for adir in dirs:
		adir = data.expand(adir, d)
		mkdirhier(adir) 

	if len(dirs) > 0:
		adir = dirs[-1]
	else:
		adir = data.getVar('S', d)

	adir = data.expand(adir, d)

	prevdir = os.getcwd()
	if adir and os.access(adir, os.F_OK):
		os.chdir(adir)

	if data.getVarFlag(func, "python", d):
		exec_func_python(func, d)
	else:
		exec_func_shell(func, d)
	os.chdir(prevdir)

def tmpFunction(d):
	"""Default function for python code blocks"""
	return 1

def exec_func_python(func, d):
	"""Execute a python OE 'function'"""
	body = data.getVar(func, d)
	if not body:
		return
	tmp = "def tmpFunction(d):\n%s" % body
	comp = compile(tmp, "tmpFunction(d)", "exec")
	prevdir = os.getcwd()
	exec(comp)
	os.chdir(prevdir)
	tmpFunction(d)

def exec_func_shell(func, d):
	"""Execute a shell OE 'function' Returns true if execution was successful.

	For this, it creates a bash shell script in the tmp dectory, writes the local
	data into it and finally executes. The output of the shell will end in a log file and stdout.

	Note on directory behavior.  The 'dirs' varflag should contain a list
	of the directories you need created prior to execution.  The last
	item in the list is where we will chdir/cd to.
	"""

	deps = data.getVarFlag(func, 'deps', _task_data)
	check = data.getVarFlag(func, 'check', _task_data)
	if globals().has_key(check):
		if globals()[check](func, deps):
			return

	global logfile
	t = data.getVar('T', d)
	if not t:
		return 0
	t = data.expand(t, d)
	mkdirhier(t)
	logfile = "%s/log.%s.%s" % (t, func, str(os.getpid()))
	runfile = "%s/run.%s.%s" % (t, func, str(os.getpid()))

	f = open(runfile, "w")
	f.write("#!/bin/bash\n")
	if data.getVar("OEDEBUG", d): f.write("set -x\n")
	oepath = data.getVar("OEPATH", d)
	if oepath:
		oepath = data.expand(oepath, d)
		for s in data.expand(oepath, d).split(":"):
			f.write("if test -f %s/build/oebuild.sh; then source %s/build/oebuild.sh; fi\n" % (s,s));
	data.emit_env(f, d)

#	if dir: f.write("cd %s\n" % dir)
	if func: f.write(func +"\n")
	f.close()
	os.chmod(runfile, 0775)
	if not func:
		error("Function not specified")
		raise FuncFailed()
	prevdir = os.getcwd()
	ret = os.system("bash -c 'source %s' 2>&1 | tee %s; exit $PIPESTATUS" % (runfile, logfile))
	os.chdir(prevdir)
	if ret==0:
		if not data.getVar("OEDEBUG"):
			os.remove(runfile)
			os.remove(logfile)
		return
	else:
		error("function %s failed" % func)
		error("see log in %s" % logfile)
		raise FuncFailed()


_task_cache = []

def exec_task(task, d):
	"""Execute an OE 'task'

	   The primary difference between executing a task versus executing
	   a function is that a task exists in the task digraph, and therefore
	   has dependencies amongst other tasks."""

	# check if the task is in the graph..
	if not _task_graph.hasnode(task):
		raise EventException("", InvalidTask(task, d))

	# check whether this task needs executing..
	if stamp_is_current(task, d):
		return 1

	# follow digraph path up, then execute our way back down
	def execute(graph, item):
		func = data.getVar(item, _task_data)
		if func:
			if func in _task_cache:
				return 1

			if task != func:
				# deeper than toplevel, exec w/ deps
				exec_task(func, d)
				return 1

			try:
				debug(1, "Executing task %s" % func)
				event.fire(TaskStarted(func, d))
				exec_func(func, d)
				event.fire(TaskSucceeded(func, d))
				_task_cache.append(func)
			except FuncFailed:
				failedevent = TaskFailed(func, d)
				event.fire(failedevent)
				raise EventException(None, failedevent)

	# execute
	_task_graph.walkdown(task, execute)

	# make stamp, or cause event and raise exception
	if not data.getVarFlag(task, 'nostamp', _task_data):
		mkstamp(task, d)


def stamp_is_current(task, d, checkdeps = 1):
	"""Check status of a given task's stamp. returns False if it is not current and needs updating."""
	stamp = data.getVar('STAMP', d)
	if not stamp:
		return False
	stampfile = "%s.%s" % (data.expand(stamp, d), task)
	if not os.access(stampfile, os.F_OK):
		return False

	if checkdeps == 0:
		return True

	import stat
	tasktime = os.stat(stampfile)[stat.ST_MTIME]

	_deps = []
	def checkStamp(graph, task):
		# check for existance
		if data.getVarFlag(task, 'nostamp', _task_data):
			return 1

		if not stamp_is_current(task, d, 0):
			return 0

		depfile = "%s.%s" % (data.expand(stamp, d), task)
		deptime = os.stat(depfile)[stat.ST_MTIME]
		if deptime > tasktime:
			return 0
		return 1

	return _task_graph.walkdown(task, checkStamp)


def md5_is_current(task):
	"""Check if a md5 file for a given task is current""" 


def mkstamp(task, d):
	"""Creates/updates a stamp for a given task"""
	mkdirhier(data.expand('${TMPDIR}/stamps', d));
	stamp = data.getVar('STAMP', d)
	if not stamp:
		return
	stamp = "%s.%s" % (data.expand(stamp, d), task)
	open(stamp, "w+")


def add_task(task, content, deps):
	data.setVar(task, content, _task_data)
	_task_graph.addnode(task, None)
	for dep in deps:
		if not _task_graph.hasnode(dep):
			_task_graph.addnode(dep, None)
		_task_graph.addnode(task, dep)


def remove_task(task, kill = 1, taskdata = _task_data):
	"""Remove an OE 'task'.

	   If kill is 1, also remove tasks that depend on this task."""

	if not _task_graph.hasnode(task):
		return

	data.delVar(task, taskdata)
	ref = 1
	if kill == 1:
		ref = 2
	_task_graph.delnode(task, ref)

def task_exists(task):
	return _task_graph.hasnode(task)

def get_task_data():
	return _task_data

data.setVarFlag("do_showdata", "nostamp", "1", _task_data)
data.setVarFlag("do_clean", "nostamp", "1", _task_data)
data.setVarFlag("do_mrproper", "nostamp", "1", _task_data)
data.setVarFlag("do_build", "nostamp", "1", _task_data)

data.setVarFlag("do_fetch", "nostamp", "1", _task_data)
data.setVarFlag("do_fetch", "check", "check_md5", _task_data)
data.setVarFlag("do_fetch", "md5data", [ "${SRC_URI}" ], _task_data)

data.setVarFlag("do_unpack", "check", "check_md5", _task_data)
data.setVarFlag("do_unpack", "md5data", [ "A" ], _task_data)
data.setVarFlag("do_unpack", "undo", [ "do_clean" ], _task_data)

data.setVarFlag("do_patch", "check", "check_md5", _task_data)
data.setVarFlag("do_patch", "md5data", [ "A" ], _task_data)

data.setVarFlag("do_compile", "check", "check_md5", _task_data)

data.setVarFlag("do_stage", "check", "check_md5", _task_data)

data.setVarFlag("do_install", "check", "check_md5", _task_data)

data.setVarFlag("do_package", "check", "check_md5", _task_data)
