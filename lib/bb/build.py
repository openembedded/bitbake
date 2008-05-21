# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake 'Build' implementation
#
# Core code for function execution and task handling in the
# BitBake build tools.
#
# Copyright (C) 2003, 2004  Chris Larson
#
# Based on Gentoo's portage.py.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#Based on functions from the base bb module, Copyright 2003 Holger Schurig

from bb import data, fetch, event, mkdirhier, utils
import bb, os

# events
class FuncFailed(Exception):
    """Executed function failed"""

class EventException(Exception):
    """Exception which is associated with an Event."""

    def __init__(self, msg, event):
        self.args = msg, event

class TaskBase(event.Event):
    """Base class for task events"""

    def __init__(self, t, d ):
        self._task = t
        event.Event.__init__(self, d)

    def getTask(self):
        return self._task

    def setTask(self, task):
        self._task = task

    task = property(getTask, setTask, None, "task property")

class TaskStarted(TaskBase):
    """Task execution started"""

class TaskSucceeded(TaskBase):
    """Task execution completed"""

class TaskFailed(TaskBase):
    """Task execution failed"""

class InvalidTask(TaskBase):
    """Invalid Task"""

# functions

def exec_func(func, d, dirs = None):
    """Execute an BB 'function'"""

    body = data.getVar(func, d)
    if not body:
        return

    flags = data.getVarFlags(func, d)
    for item in ['deps', 'check', 'interactive', 'python', 'cleandirs', 'dirs', 'lockfiles', 'fakeroot']:
        if not item in flags:
            flags[item] = None

    ispython = flags['python']

    cleandirs = (data.expand(flags['cleandirs'], d) or "").split()
    for cdir in cleandirs:
        os.system("rm -rf %s" % cdir)

    if dirs:
        dirs = data.expand(dirs, d)
    else:
        dirs = (data.expand(flags['dirs'], d) or "").split()
    for adir in dirs:
        mkdirhier(adir)

    if len(dirs) > 0:
        adir = dirs[-1]
    else:
        adir = data.getVar('B', d, 1)

    try:
        prevdir = os.getcwd()
    except OSError:
        prevdir = data.getVar('TOPDIR', d, True)
    if adir and os.access(adir, os.F_OK):
        os.chdir(adir)

    locks = []
    lockfiles = (data.expand(flags['lockfiles'], d) or "").split()
    for lock in lockfiles:
        locks.append(bb.utils.lockfile(lock))

    if flags['python']:
        exec_func_python(func, d)
    else:
        exec_func_shell(func, d, flags)

    for lock in locks:
        bb.utils.unlockfile(lock)

    if os.path.exists(prevdir):
        os.chdir(prevdir)

def exec_func_python(func, d):
    """Execute a python BB 'function'"""
    import re, os

    bbfile = bb.data.getVar('FILE', d, 1)
    tmp  = "def " + func + "():\n%s" % data.getVar(func, d)
    tmp += '\n' + func + '()'
    comp = utils.better_compile(tmp, func, bbfile)
    prevdir = os.getcwd()
    g = {} # globals
    g['bb'] = bb
    g['os'] = os
    g['d'] = d
    utils.better_exec(comp, g, tmp, bbfile)
    if os.path.exists(prevdir):
        os.chdir(prevdir)

def exec_func_shell(func, d, flags):
    """Execute a shell BB 'function' Returns true if execution was successful.

    For this, it creates a bash shell script in the tmp dectory, writes the local
    data into it and finally executes. The output of the shell will end in a log file and stdout.

    Note on directory behavior.  The 'dirs' varflag should contain a list
    of the directories you need created prior to execution.  The last
    item in the list is where we will chdir/cd to.
    """
    import sys

    deps = flags['deps']
    check = flags['check']
    interact = flags['interactive']
    if check in globals():
        if globals()[check](func, deps):
            return

    global logfile
    t = data.getVar('T', d, 1)
    if not t:
        return 0
    mkdirhier(t)
    logfile = "%s/log.%s.%s" % (t, func, str(os.getpid()))
    runfile = "%s/run.%s.%s" % (t, func, str(os.getpid()))

    f = open(runfile, "w")
    f.write("#!/bin/sh -e\n")
    if bb.msg.debug_level['default'] > 0: f.write("set -x\n")
    data.emit_env(f, d)

    f.write("cd %s\n" % os.getcwd())
    if func: f.write("%s\n" % func)
    f.close()
    os.chmod(runfile, 0775)
    if not func:
        bb.msg.error(bb.msg.domain.Build, "Function not specified")
        raise FuncFailed()

    # open logs
    si = file('/dev/null', 'r')
    try:
        if bb.msg.debug_level['default'] > 0:
            so = os.popen("tee \"%s\"" % logfile, "w")
        else:
            so = file(logfile, 'w')
    except OSError, e:
        bb.msg.error(bb.msg.domain.Build, "opening log file: %s" % e)
        pass

    se = so

    if not interact:
        # dup the existing fds so we dont lose them
        osi = [os.dup(sys.stdin.fileno()), sys.stdin.fileno()]
        oso = [os.dup(sys.stdout.fileno()), sys.stdout.fileno()]
        ose = [os.dup(sys.stderr.fileno()), sys.stderr.fileno()]

        # replace those fds with our own
        os.dup2(si.fileno(), osi[1])
        os.dup2(so.fileno(), oso[1])
        os.dup2(se.fileno(), ose[1])

    # execute function
    prevdir = os.getcwd()
    if flags['fakeroot']:
        maybe_fakeroot = "PATH=\"%s\" fakeroot " % bb.data.getVar("PATH", d, 1)
    else:
        maybe_fakeroot = ''
    lang_environment = "LC_ALL=C "
    ret = os.system('%s%ssh -e %s' % (lang_environment, maybe_fakeroot, runfile))
    try:
        os.chdir(prevdir)
    except:
        pass

    if not interact:
        # restore the backups
        os.dup2(osi[0], osi[1])
        os.dup2(oso[0], oso[1])
        os.dup2(ose[0], ose[1])

        # close our logs
        si.close()
        so.close()
        se.close()

        # close the backup fds
        os.close(osi[0])
        os.close(oso[0])
        os.close(ose[0])

    if ret==0:
        if bb.msg.debug_level['default'] > 0:
            os.remove(runfile)
#            os.remove(logfile)
        return
    else:
        bb.msg.error(bb.msg.domain.Build, "function %s failed" % func)
        if data.getVar("BBINCLUDELOGS", d):
            bb.msg.error(bb.msg.domain.Build, "log data follows (%s)" % logfile)
            number_of_lines = data.getVar("BBINCLUDELOGS_LINES", d)
            if number_of_lines:
                os.system('tail -n%s %s' % (number_of_lines, logfile))
            else:
                f = open(logfile, "r")
                while True:
                    l = f.readline()
                    if l == '':
                        break
                    l = l.rstrip()
                    print '| %s' % l
                f.close()
        else:
            bb.msg.error(bb.msg.domain.Build, "see log in %s" % logfile)
        raise FuncFailed( logfile )


def exec_task(task, d):
    """Execute an BB 'task'

       The primary difference between executing a task versus executing
       a function is that a task exists in the task digraph, and therefore
       has dependencies amongst other tasks."""

    # Check whther this is a valid task
    if not data.getVarFlag(task, 'task', d):
        raise EventException("No such task", InvalidTask(task, d))

    try:
        bb.msg.debug(1, bb.msg.domain.Build, "Executing task %s" % task)
        old_overrides = data.getVar('OVERRIDES', d, 0)
        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', 'task-%s:%s' % (task[3:], old_overrides), localdata)
        data.update_data(localdata)
        data.expandKeys(localdata)
        event.fire(TaskStarted(task, localdata))
        exec_func(task, localdata)
        event.fire(TaskSucceeded(task, localdata))
    except FuncFailed, reason:
        bb.msg.note(1, bb.msg.domain.Build, "Task failed: %s" % reason )
        failedevent = TaskFailed(task, d)
        event.fire(failedevent)
        raise EventException("Function failed in task: %s" % reason, failedevent)

    # make stamp, or cause event and raise exception
    if not data.getVarFlag(task, 'nostamp', d) and not data.getVarFlag(task, 'selfstamp', d):
        make_stamp(task, d)

def extract_stamp(d, fn):
    """
    Extracts stamp format which is either a data dictonary (fn unset) 
    or a dataCache entry (fn set). 
    """
    if fn:
        return d.stamp[fn]
    return data.getVar('STAMP', d, 1)

def stamp_internal(task, d, file_name):
    """
    Internal stamp helper function
    Removes any stamp for the given task
    Makes sure the stamp directory exists
    Returns the stamp path+filename
    """
    stamp = extract_stamp(d, file_name)
    if not stamp:
        return
    stamp = "%s.%s" % (stamp, task)
    mkdirhier(os.path.dirname(stamp))
    # Remove the file and recreate to force timestamp
    # change on broken NFS filesystems
    if os.access(stamp, os.F_OK):
        os.remove(stamp)
    return stamp

def make_stamp(task, d, file_name = None):
    """
    Creates/updates a stamp for a given task
    (d can be a data dict or dataCache)
    """
    stamp = stamp_internal(task, d, file_name)
    if stamp:
        f = open(stamp, "w")
        f.close()

def del_stamp(task, d, file_name = None):
    """
    Removes a stamp for a given task
    (d can be a data dict or dataCache)
    """
    stamp_internal(task, d, file_name)

def add_tasks(tasklist, d):
    task_deps = data.getVar('_task_deps', d)
    if not task_deps:
        task_deps = {}
    if not 'tasks' in task_deps:
        task_deps['tasks'] = []
    if not 'parents' in task_deps:
        task_deps['parents'] = {}

    for task in tasklist:
        task = data.expand(task, d)
        data.setVarFlag(task, 'task', 1, d)

        if not task in task_deps['tasks']:
            task_deps['tasks'].append(task)

        flags = data.getVarFlags(task, d)    
        def getTask(name):
            if not name in task_deps:
                task_deps[name] = {}
            if name in flags:
                deptask = data.expand(flags[name], d)
                task_deps[name][task] = deptask
        getTask('depends')
        getTask('deptask')
        getTask('rdeptask')
        getTask('recrdeptask')
        getTask('nostamp')
        task_deps['parents'][task] = []
        for dep in flags['deps']:
            dep = data.expand(dep, d)
            task_deps['parents'][task].append(dep)

    # don't assume holding a reference
    data.setVar('_task_deps', task_deps, d)

def remove_task(task, kill, d):
    """Remove an BB 'task'.

       If kill is 1, also remove tasks that depend on this task."""

    data.delVarFlag(task, 'task', d)

