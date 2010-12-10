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

import os
import sys
import logging
import bb
import bb.msg
import bb.utils
import bb.process
from contextlib import nested
from bb import data, event, mkdirhier, utils

bblogger = logging.getLogger('BitBake')
logger = logging.getLogger('BitBake.Build')

NULL = open('/dev/null', 'a')


# When we execute a python function we'd like certain things
# in all namespaces, hence we add them to __builtins__
# If we do not do this and use the exec globals, they will
# not be available to subfunctions.
__builtins__['bb'] = bb
__builtins__['os'] = os

class FuncFailed(Exception):
    def __init__(self, name, logfile = None):
        self.logfile = logfile
        if logfile is None:
            self.name = None
            self.message = name
        else:
            self.name = name
            self.message = "Function '%s' failed" % name

    def __str__(self):
        if self.logfile and os.path.exists(self.logfile):
            msg = "%s (see %s for further information)" % \
                  (self.message, self.logfile)
        else:
            msg = self.message
        return msg

class TaskBase(event.Event):
    """Base class for task events"""

    def __init__(self, t, d ):
        self._task = t
        self._package = bb.data.getVar("PF", d, 1)
        event.Event.__init__(self)
        self._message = "package %s: task %s: %s" % (bb.data.getVar("PF", d, 1), t, bb.event.getName(self)[4:])

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

    def __init__(self, task, logfile, metadata):
        self.logfile = logfile
        super(TaskFailed, self).__init__(task, metadata)

class InvalidTask(Exception):
    def __init__(self, task, metadata):
        self.task = task
        self.metadata = metadata

    def __str__(self):
        return "No such task '%s'" % self.task


class tee(file):
    def write(self, string):
        logger.plain(string)
        file.write(self, string)

    def __repr__(self):
        return "<open[tee] file '{0}'>".format(self.name)


def exec_func(func, d, dirs = None):
    """Execute an BB 'function'"""

    body = data.getVar(func, d)
    if not body:
        logger.warn("Function %s doesn't exist" % func)
        return

    flags = data.getVarFlags(func, d)
    cleandirs = flags.get('cleandirs')
    if cleandirs:
        for cdir in data.expand(cleandirs, d).split():
            os.system("rm -rf %s" % cdir)

    if dirs is None:
        dirs = flags.get('dirs')
        if dirs:
            dirs = data.expand(dirs, d).split()

    if dirs:
        for adir in dirs:
            bb.utils.mkdirhier(adir)
        adir = dirs[-1]
    else:
        adir = data.getVar('B', d, 1)
        bb.utils.mkdirhier(adir)

    ispython = flags.get('python')
    fakeroot = flags.get('fakeroot')

    t = data.getVar('T', d, 1)
    if not t:
        bb.fatal("T variable not set, unable to build")
    bb.utils.mkdirhier(t)
    loglink = os.path.join(t, 'log.{0}'.format(func))
    logfn = os.path.join(t, 'log.{0}.{1}'.format(func, os.getpid()))
    runfile = os.path.join(t, 'run.{0}.{1}'.format(func, os.getpid()))

    if loglink:
        try:
           os.remove(loglink)
        except OSError:
           pass

        try:
           os.symlink(logfn, loglink)
        except OSError:
           pass

    if logger.getEffectiveLevel() <= logging.DEBUG:
        logfile = tee(logfn, 'w')
    else:
        logfile = open(logfn, 'w')

    lockflag = flags.get('lockfiles')
    if lockflag:
        lockfiles = [data.expand(f, d) for f in lockflag.split()]
    else:
        lockfiles = None

    with nested(logfile, bb.utils.fileslocked(lockfiles)):
        try:
            if ispython:
                exec_func_python(func, d, runfile, logfile, cwd=adir)
            else:
                exec_func_shell(func, d, runfile, logfile, cwd=adir, fakeroot=fakeroot)
        finally:
            if os.path.exists(logfn) and os.path.getsize(logfn) == 0:
                logger.debug(2, "Zero size logfn %s, removing", logfn)
                bb.utils.remove(logfn)
                bb.utils.remove(loglink)

_functionfmt = """
def {function}(d):
{body}

{function}(d)
"""
logformatter = bb.msg.BBLogFormatter("%(levelname)s: %(message)s")
def exec_func_python(func, d, runfile, logfile, cwd=None):
    """Execute a python BB 'function'"""

    bbfile = d.getVar('file', True)
    olddir = os.getcwd()
    code = _functionfmt.format(function=func, body=d.getVar(func, True))
    with open(runfile, 'w') as script:
        script.write(code)

    if cwd:
        os.chdir(cwd)

    stdout, stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = NULL, NULL

    handler = logging.StreamHandler(logfile)
    handler.setFormatter(logformatter)
    bblogger.addHandler(handler)

    try:
        comp = utils.better_compile(code, func, bbfile)
        utils.better_exec(comp, {"d": d}, code, bbfile)
    except:
        if sys.exc_info()[0] in (bb.parse.SkipPackage, bb.build.FuncFailed):
            raise

        raise FuncFailed(func, None)
    finally:
        bblogger.removeHandler(handler)
        sys.stdout, sys.stderr = stdout, stderr
        os.chdir(olddir)

def exec_func_shell(function, d, runfile, logfile, cwd=None, fakeroot=False):
    """Execute a shell function from the metadata

    Note on directory behavior.  The 'dirs' varflag should contain a list
    of the directories you need created prior to execution.  The last
    item in the list is where we will chdir/cd to.
    """

    with open(runfile, 'w') as script:
        script.write('#!/bin/sh -e\n')
        if logger.getEffectiveLevel() <= logging.DEBUG:
            script.write("set -x\n")
        data.emit_env(script, d)

        script.write("%s\n" % function)
        os.fchmod(script.fileno(), 0775)

    env = {
        'PATH': d.getVar('PATH', True),
        'LANG': 'C',
    }
    if fakeroot:
        cmd = ['fakeroot', runfile]
    else:
        cmd = runfile

    try:
        bb.process.run(cmd, env=env, cwd=cwd, shell=False, stdin=NULL,
                       log=logfile)
    except bb.process.CmdError:
        raise FuncFailed(function, logfile.name)

def exec_task(fn, task, d):
    """Execute a BB 'task'

    Execution of a task involves a bit more setup than executing a function,
    running it with its own local metadata, and with some useful variables set.
    """

    # Check whther this is a valid task
    if not data.getVarFlag(task, 'task', d):
        raise InvalidTask(task, d)

    try:
        logger.debug(1, "Executing task %s", task)
        old_overrides = data.getVar('OVERRIDES', d, 0)
        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', 'task-%s:%s' % (task[3:], old_overrides), localdata)
        data.update_data(localdata)
        data.expandKeys(localdata)
        data.setVar('BB_FILENAME', fn, d)
        data.setVar('BB_CURRENTTASK', task[3:], d)
        event.fire(TaskStarted(task, localdata), localdata)
        exec_func(task, localdata)
        event.fire(TaskSucceeded(task, localdata), localdata)
    except FuncFailed as exc:
        event.fire(TaskFailed(exc.name, exc.logfile, localdata), localdata)
        raise

    # make stamp, or cause event and raise exception
    if not data.getVarFlag(task, 'nostamp', d) and not data.getVarFlag(task, 'selfstamp', d):
        make_stamp(task, d)

def extract_stamp(d, fn):
    """
    Extracts stamp format which is either a data dictionary (fn unset)
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
    bb.utils.mkdirhier(os.path.dirname(stamp))
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
