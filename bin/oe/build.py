from oe import event, data
from oe import mkdirhier, fatal, debug, error
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


def exec_func(func, d):
	"""Execute an OE 'function'"""

	exec_func_shell(func, d)


def exec_func_python(func, d):
	"""Execute a python OE 'function'"""


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

	dirs = data.getVarFlag(func, 'dirs', d) or []
	for dir in dirs:
		mkdirhier(dir) 

	if len(dirs) > 0:
		dir = dirs[-1]
	else:
		dir = None

	global logfile
	t = data.getVar('T', d)
	if not t:
		return 0
	mkdirhier(t)
	logfile = "%s/log.%s.%s" % (t, func, str(os.getpid()))
	runfile = "%s/run.%s.%s" % (t, func, str(os.getpid()))

	f = open(runfile, "w")
	f.write("#!/bin/bash\n")
	if data.getVar("OEDEBUG", d): f.write("set -x\n")
	oepath = data.getVar("OEPATH", d)
	if oepath:
		for s in data.expand(oepath, d).split(":"):
			f.write("if test -f %s/build/oebuild.sh; then source %s/build/oebuild.sh; fi\n" % (s,s));
	data.emit_env(f, d)

	if dir: f.write("cd %s\n" % dir)
	if func: f.write(func +"\n")
	f.close()
	os.chmod(runfile, 0775)
	if not func:
		error("Function not specified")
		raise FuncFailed()
	ret = os.system("bash -c 'source %s' 2>&1 | tee %s; exit $PIPESTATUS" % (runfile, logfile))
	if ret==0:
		if not data.getVar("OEDEBUG"):
			os.remove(runfile)
			os.remove(logfile)
		return
	else:
		error("'%s'() failed" % func);
		error("more info in: %s" % logfile);
		raise FuncFailed()


def exec_task(task, d):
	"""Execute an OE 'task'

	   The primary difference between executing a task versus executing
	   a function is that a task exists in the task digraph, and therefore
	   has dependencies amongst other tasks."""

	# check if the task is in the graph..
	if not _task_graph.hasnode(task):
		raise EventException("", InvalidTask(task, d))
#		return 0

	# check whether this task needs executing..

	# follow digraph path up, then execute our way back down
	def execute(graph, item):
		func = data.getVar(item, _task_data)
		if func:
			exec_func_shell(func, d)

	# execute
	try:
		event.fire(TaskStarted(task, d))
		_task_graph.walkdown(task, execute)
		event.fire(TaskSucceeded(task, d))
	except FuncFailed:
		event.fire(TaskFailed(task, d))
		raise FuncFailed()

	# make stamp, or cause event and raise exception
	mkstamp(task, d)


def stamp_is_current(task):
	"""Check if a stamp file for a given task is current"""


def md5_is_current(task):
	"""Check if a md5 file for a given task is current""" 


def mkstamp(task, d):
	"""Creates/updates a stamp for a given task"""
	mkdirhier(data.expand('${TMPDIR}/stamps', d));
	stamp = data.getVar('STAMP', d)
	if not stamp:
		return
	stamp = "%s.%s" % (stamp, task)
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
