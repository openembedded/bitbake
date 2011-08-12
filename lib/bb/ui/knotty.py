#
# BitBake (No)TTY UI Implementation
#
# Handling output to TTYs or files (no TTY)
#
# Copyright (C) 2006-2007 Richard Purdie
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

from __future__ import division

import os
import sys
import xmlrpclib
import logging
import progressbar
import bb.msg
from bb.ui import uihelper

logger = logging.getLogger("BitBake")
interactive = sys.stdout.isatty()

class BBProgress(progressbar.ProgressBar):
    def __init__(self, msg, maxval):
        self.msg = msg
        widgets = [progressbar.Percentage(), ' ', progressbar.Bar(), ' ',
           progressbar.ETA()]

        progressbar.ProgressBar.__init__(self, maxval, [self.msg + ": "] + widgets)

class NonInteractiveProgress(object):
    fobj = sys.stdout

    def __init__(self, msg, maxval):
        self.msg = msg
        self.maxval = maxval

    def start(self):
        self.fobj.write("%s..." % self.msg)
        self.fobj.flush()
        return self

    def update(self, value):
        pass

    def finish(self):
        self.fobj.write("done.\n")
        self.fobj.flush()

def new_progress(msg, maxval):
    if interactive:
        return BBProgress(msg, maxval)
    else:
        return NonInteractiveProgress(msg, maxval)

def main(server, eventHandler):

    # Get values of variables which control our output
    includelogs = server.runCommand(["getVariable", "BBINCLUDELOGS"])
    loglines = server.runCommand(["getVariable", "BBINCLUDELOGS_LINES"])

    helper = uihelper.BBUIHelper()

    console = logging.StreamHandler(sys.stdout)
    format = bb.msg.BBLogFormatter("%(levelname)s: %(message)s")
    bb.msg.addDefaultlogFilter(console)
    console.setFormatter(format)
    logger.addHandler(console)

    try:
        cmdline = server.runCommand(["getCmdLineAction"])
        if not cmdline:
            print("Nothing to do.  Use 'bitbake world' to build everything, or run 'bitbake --help' for usage information.")
            return 1
        elif not cmdline['action']:
            print(cmdline['msg'])
            return 1
        ret = server.runCommand(cmdline['action'])
        if ret != True:
            print("Couldn't get default commandline! %s" % ret)
            return 1
    except xmlrpclib.Fault as x:
        print("XMLRPC Fault getting commandline:\n %s" % x)
        return 1


    parseprogress = None
    cacheprogress = None
    shutdown = 0
    return_value = 0
    while True:
        try:
            event = eventHandler.waitEvent(0.25)
            if event is None:
                continue
            helper.eventHandler(event)
            if isinstance(event, bb.runqueue.runQueueExitWait):
                if not shutdown:
                    shutdown = 1
            if shutdown and helper.needUpdate:
                activetasks, failedtasks = helper.getTasks()
                if activetasks:
                    print("Waiting for %s active tasks to finish:" % len(activetasks))
                    for tasknum, task in enumerate(activetasks):
                        print("%s: %s (pid %s)" % (tasknum, activetasks[task]["title"], task))

            if isinstance(event, logging.LogRecord):
                if event.levelno >= format.ERROR:
                    return_value = 1
                # For "normal" logging conditions, don't show note logs from tasks
                # but do show them if the user has changed the default log level to 
                # include verbose/debug messages
                #if logger.getEffectiveLevel() > format.VERBOSE:
                if event.taskpid != 0 and event.levelno <= format.NOTE:
                        continue
                logger.handle(event)
                continue

            if isinstance(event, bb.build.TaskFailed):
                return_value = 1
                logfile = event.logfile
                if logfile and os.path.exists(logfile):
                    print("ERROR: Logfile of failure stored in: %s" % logfile)
                    if 1 or includelogs:
                        print("Log data follows:")
                        f = open(logfile, "r")
                        lines = []
                        while True:
                            l = f.readline()
                            if l == '':
                                break
                            l = l.rstrip()
                            if loglines:
                                lines.append(' | %s' % l)
                                if len(lines) > int(loglines):
                                    lines.pop(0)
                            else:
                                print('| %s' % l)
                        f.close()
                        if lines:
                            for line in lines:
                                print(line)
            if isinstance(event, bb.build.TaskBase):
                logger.info(event._message)
                continue
            if isinstance(event, bb.event.ParseStarted):
                if event.total == 0:
                    continue
                parseprogress = new_progress("Parsing recipes", event.total).start()
                continue
            if isinstance(event, bb.event.ParseProgress):
                parseprogress.update(event.current)
                continue
            if isinstance(event, bb.event.ParseCompleted):
                if not parseprogress:
                    continue

                parseprogress.finish()
                print(("Parsing of %d .bb files complete (%d cached, %d parsed). %d targets, %d skipped, %d masked, %d errors."
                    % ( event.total, event.cached, event.parsed, event.virtuals, event.skipped, event.masked, event.errors)))
                continue

            if isinstance(event, bb.event.CacheLoadStarted):
                cacheprogress = new_progress("Loading cache", event.total).start()
                continue
            if isinstance(event, bb.event.CacheLoadProgress):
                cacheprogress.update(event.current)
                continue
            if isinstance(event, bb.event.CacheLoadCompleted):
                cacheprogress.finish()
                print("Loaded %d entries from dependency cache." % event.num_entries)
                continue

            if isinstance(event, bb.command.CommandCompleted):
                break
            if isinstance(event, bb.command.CommandFailed):
                return_value = event.exitcode
                logger.error("Command execution failed: %s", event.error)
                break
            if isinstance(event, bb.command.CommandExit):
                if not return_value:
                    return_value = event.exitcode
                continue
            if isinstance(event, bb.cooker.CookerExit):
                break
            if isinstance(event, bb.event.MultipleProviders):
                logger.info("multiple providers are available for %s%s (%s)", event._is_runtime and "runtime " or "",
                            event._item,
                            ", ".join(event._candidates))
                logger.info("consider defining a PREFERRED_PROVIDER entry to match %s", event._item)
                continue
            if isinstance(event, bb.event.NoProvider):
                return_value = 1
                if event._runtime:
                    r = "R"
                else:
                    r = ""

                if event._dependees:
                    logger.error("Nothing %sPROVIDES '%s' (but %s %sDEPENDS on or otherwise requires it)", r, event._item, ", ".join(event._dependees), r)
                else:
                    logger.error("Nothing %sPROVIDES '%s'", r, event._item)
                if event._reasons:
                    for reason in event._reasons:
                        logger.error("%s", reason)
                continue

            if isinstance(event, bb.runqueue.runQueueTaskStarted):
                if event.noexec:
                    tasktype = 'noexec task'
                else:
                    tasktype = 'task'
                logger.info("Running %s %s of %s (ID: %s, %s)",
                            tasktype,
                            event.stats.completed + event.stats.active +
                                event.stats.failed + 1,
                            event.stats.total, event.taskid, event.taskstring)
                continue

            if isinstance(event, bb.runqueue.runQueueTaskFailed):
                logger.error("Task %s (%s) failed with exit code '%s'",
                             event.taskid, event.taskstring, event.exitcode)
                continue

            # ignore
            if isinstance(event, (bb.event.BuildBase,
                                  bb.event.StampUpdate,
                                  bb.event.ConfigParsed,
                                  bb.event.RecipeParsed,
                                  bb.event.RecipePreFinalise,
                                  bb.runqueue.runQueueEvent,
                                  bb.runqueue.runQueueExitWait)):
                continue

            logger.error("Unknown event: %s", event)

        except EnvironmentError as ioerror:
            # ignore interrupted io
            if ioerror.args[0] == 4:
                pass
        except KeyboardInterrupt:
            if shutdown == 2:
                print("\nThird Keyboard Interrupt, exit.\n")
                break
            if shutdown == 1:
                print("\nSecond Keyboard Interrupt, stopping...\n")
                server.runCommand(["stateStop"])
            if shutdown == 0:
                print("\nKeyboard Interrupt, closing down...\n")
                server.runCommand(["stateShutdown"])
            shutdown = shutdown + 1
            pass
    return return_value
