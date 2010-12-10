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
import itertools
import xmlrpclib
import logging
import progressbar
import bb.msg
from bb import ui
from bb.ui import uihelper

logger = logging.getLogger("BitBake")
widgets = [progressbar.Percentage(), ' ', progressbar.Bar(), ' ',
           progressbar.ETA()]

class BBProgress(progressbar.ProgressBar):
    def __init__(self, msg, maxval):
        self.msg = msg
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

def main(server, eventHandler):

    # Get values of variables which control our output
    includelogs = server.runCommand(["getVariable", "BBINCLUDELOGS"])
    loglines = server.runCommand(["getVariable", "BBINCLUDELOGS_LINES"])

    helper = uihelper.BBUIHelper()

    # Set up logging to stdout in our usual format
    logging.addLevelName(logging.INFO, "NOTE")
    logging.addLevelName(logging.CRITICAL, "ERROR")

    for level in xrange(logging.INFO - 1, logging.DEBUG + 1, -1):
        logging.addLevelName(level, logging.getLevelName(logging.INFO))

    for level in xrange(logging.DEBUG - 1, 0, -1):
        logging.addLevelName(level, logging.getLevelName(logging.DEBUG))

    console = logging.StreamHandler(sys.stdout)
    format = bb.msg.BBLogFormatter("%(levelname)s: %(message)s")
    console.setFormatter(format)
    logger.addHandler(console)

    try:
        cmdline = server.runCommand(["getCmdLineAction"])
        if not cmdline:
            return 1
        ret = server.runCommand(cmdline)
        if ret != True:
            print("Couldn't get default commandline! %s" % ret)
            return 1
    except xmlrpclib.Fault as x:
        print("XMLRPC Fault getting commandline:\n %s" % x)
        return 1

    parseprogress = None
    interactive = os.isatty(sys.stdout.fileno())
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
                if interactive:
                    progress = BBProgress
                else:
                    progress = NonInteractiveProgress
                parseprogress = progress("Parsing recipes", event.total).start()
                continue
            if isinstance(event, bb.event.ParseProgress):
                parseprogress.update(event.current)
                continue
            if isinstance(event, bb.event.ParseCompleted):
                parseprogress.finish()
                print(("Parsing of %d .bb files complete (%d cached, %d parsed). %d targets, %d skipped, %d masked, %d errors."
                    % ( event.total, event.cached, event.parsed, event.virtuals, event.skipped, event.masked, event.errors)))
                continue

            if isinstance(event, bb.command.CookerCommandCompleted):
                break
            if isinstance(event, bb.command.CookerCommandSetExitCode):
                return_value = event.exitcode
                continue
            if isinstance(event, bb.command.CookerCommandFailed):
                return_value = 1
                logger.error("Command execution failed: %s" % event.error)
                break
            if isinstance(event, bb.cooker.CookerExit):
                break
            if isinstance(event, bb.event.MultipleProviders):
                logger.info("multiple providers are available for %s%s (%s)", event._is_runtime and "runtime " or "",
                            event._item,
                            ", ".join(event._candidates))
                logger.info("consider defining a PREFERRED_PROVIDER entry to match %s", event._item)
                continue
            if isinstance(event, bb.event.NoProvider):
                if event._runtime:
                    r = "R"
                else:
                    r = ""

                if event._dependees:
                    logger.error("Nothing %sPROVIDES '%s' (but %s %sDEPENDS on or otherwise requires it)", r, event._item, ", ".join(event._dependees), r)
                else:
                    logger.error("Nothing %sPROVIDES '%s'", r, event._item)
                continue

            # ignore
            if isinstance(event, (bb.event.BuildBase,
                                  bb.event.StampUpdate,
                                  bb.event.ConfigParsed,
                                  bb.event.RecipeParsed,
                                  bb.runqueue.runQueueEvent,
                                  bb.runqueue.runQueueExitWait)):
                continue

            logger.error("Unknown event: %s", event)

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
