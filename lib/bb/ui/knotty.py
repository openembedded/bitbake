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

import os

import sys
import itertools
import xmlrpclib
from bb import ui
from bb.ui import uihelper


parsespin = itertools.cycle( r'|/-\\' )

def init(server, eventHandler):

    # Get values of variables which control our output
    includelogs = server.runCommand(["getVariable", "BBINCLUDELOGS"])
    loglines = server.runCommand(["getVariable", "BBINCLUDELOGS_LINES"])

    helper = uihelper.BBUIHelper()

    try:
        cmdline = server.runCommand(["getCmdLineAction"])
        #print cmdline
        if not cmdline:
            return 1
        ret = server.runCommand(cmdline)
        if ret != True:
            print("Couldn't get default commandline! %s" % ret)
            return 1
    except xmlrpclib.Fault as x:
        print("XMLRPC Fault getting commandline:\n %s" % x)
        return 1

    shutdown = 0
    return_value = 0
    while True:
        try:
            event = eventHandler.waitEvent(0.25)
            if event is None:
                continue
            #print event
            helper.eventHandler(event)
            if isinstance(event, bb.runqueue.runQueueExitWait):
                if not shutdown:
                    shutdown = 1
            if shutdown and helper.needUpdate:
                activetasks, failedtasks = helper.getTasks()
                if activetasks:
                    print("Waiting for %s active tasks to finish:" % len(activetasks))
                    tasknum = 1
                    for task in activetasks:
                        print("%s: %s (pid %s)" % (tasknum, activetasks[task]["title"], task))
                        tasknum = tasknum + 1

            if isinstance(event, bb.msg.MsgPlain):
                print(event._message)
                continue
            if isinstance(event, bb.msg.MsgDebug):
                print('DEBUG: ' + event._message)
                continue
            if isinstance(event, bb.msg.MsgNote):
                print('NOTE: ' + event._message)
                continue
            if isinstance(event, bb.msg.MsgWarn):
                print('WARNING: ' + event._message)
                continue
            if isinstance(event, bb.msg.MsgError):
                return_value = 1
                print('ERROR: ' + event._message)
                continue
            if isinstance(event, bb.msg.MsgFatal):
                return_value = 1
                print('FATAL: ' + event._message)
                break
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
                print("NOTE: %s" % event._message)
                continue
            if isinstance(event, bb.event.ParseProgress):
                x = event.sofar
                y = event.total
                if os.isatty(sys.stdout.fileno()):
                    sys.stdout.write("\rNOTE: Handling BitBake files: %s (%04d/%04d) [%2d %%]" % ( parsespin.next(), x, y, x*100/y ) )
                    sys.stdout.flush()
                else:
                    if x == 1:
                        sys.stdout.write("Parsing .bb files, please wait...")
                        sys.stdout.flush()
                    if x == y:
                        sys.stdout.write("done.")
                        sys.stdout.flush()
                if x == y:
                    print(("\nParsing of %d .bb files complete (%d cached, %d parsed). %d targets, %d skipped, %d masked, %d errors."
                        % ( event.total, event.cached, event.parsed, event.virtuals, event.skipped, event.masked, event.errors)))
                continue

            if isinstance(event, bb.command.CookerCommandCompleted):
                break
            if isinstance(event, bb.command.CookerCommandSetExitCode):
                return_value = event.exitcode
                continue
            if isinstance(event, bb.command.CookerCommandFailed):
                return_value = 1
                print("Command execution failed: %s" % event.error)
                break
            if isinstance(event, bb.cooker.CookerExit):
                break
            if isinstance(event, bb.event.MultipleProviders):
                print("NOTE: multiple providers are available for %s%s (%s)" % (event._is_runtime and "runtime " or "",
                                                                                event._item,
                                                                                ", ".join(event._candidates)))
                print("NOTE: consider defining a PREFERRED_PROVIDER entry to match %s" % event._item)
                continue
            if isinstance(event, bb.event.NoProvider):
                if event._runtime:
                    r = "R"
                else:
                    r = ""

                if event._dependees:
                    print("ERROR: Nothing %sPROVIDES '%s' (but %s %sDEPENDS on or otherwise requires it)" % (r, event._item, ", ".join(event._dependees), r))
                else:
                    print("ERROR: Nothing %sPROVIDES '%s'" % (r, event._item))
                continue

            # ignore
            if isinstance(event, (bb.event.BuildBase,
                                  bb.event.StampUpdate,
                                  bb.event.ConfigParsed,
                                  bb.event.RecipeParsed,
                                  bb.runqueue.runQueueEvent,
                                  bb.runqueue.runQueueExitWait)):
                continue

            print("Unknown Event: %s" % event)

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
