#
# BitBake (No)TTY UI Implementation (v2)
#
# Handling output to TTYs or files (no TTY)
#
# Copyright (C) 2012 Richard Purdie
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

from bb.ui import knotty
import logging
import sys
logger = logging.getLogger("BitBake")

class InteractConsoleLogFilter(logging.Filter):
    def __init__(self, tf, format):
        self.tf = tf
        self.format = format

    def filter(self, record):
        if record.levelno == self.format.NOTE and (record.msg.startswith("Running") or record.msg.startswith("package ")):
            return False
        self.tf.clearFooter()
        return True

class TerminalFilter2(object):
    def __init__(self, main, helper, console, format):
        self.main = main
        self.helper = helper
        self.cuu = None
        self.stdinbackup = None
        self.interactive = sys.stdout.isatty()
        self.footer_present = False
        self.lastpids = []

        if not self.interactive:
            return

        import curses
        import termios
        import copy
        self.curses = curses
        self.termios = termios
        try:
            fd = sys.stdin.fileno()
            self.stdinbackup = termios.tcgetattr(fd)
            new = copy.deepcopy(self.stdinbackup)
            new[3] = new[3] & ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSADRAIN, new)
            curses.setupterm()
            self.ed = curses.tigetstr("ed")
            if self.ed:
                self.cuu = curses.tigetstr("cuu")
        except:
            self.cuu = None
        console.addFilter(InteractConsoleLogFilter(self, format))

    def clearFooter(self):
        if self.footer_present:
            lines = self.footer_present
            sys.stdout.write(self.curses.tparm(self.cuu, lines))
            sys.stdout.write(self.curses.tparm(self.ed))
        self.footer_present = False

    def updateFooter(self):
        if not self.cuu:
            return
        activetasks = self.helper.running_tasks
        failedtasks = self.helper.failed_tasks
        runningpids = self.helper.running_pids
        if self.footer_present and (self.lastpids == runningpids):
            return
        if self.footer_present:
            self.clearFooter()
        if not activetasks:
            return
        lines = 1
        tasks = []
        for t in runningpids:
            tasks.append("%s (pid %s)" % (activetasks[t]["title"], t))

        if self.main.shutdown:
            print("Waiting for %s running tasks to finish:" % len(activetasks))
        else:
            print("Currently %s running tasks (%s of %s):" % (len(activetasks), self.helper.tasknumber_current, self.helper.tasknumber_total))
        for tasknum, task in enumerate(tasks):
            print("%s: %s" % (tasknum, task))
            lines = lines + 1
        self.footer_present = lines
        self.lastpids = runningpids[:]

    def finish(self):
        if self.stdinbackup:
            fd = sys.stdin.fileno()
            self.termios.tcsetattr(fd, self.termios.TCSADRAIN, self.stdinbackup)

def main(server, eventHandler):
    bb.ui.knotty.main(server, eventHandler, TerminalFilter2)
