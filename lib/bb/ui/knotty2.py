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
import os
import fcntl
import struct
import copy
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
    columns = 80

    def sigwinch_handle(self, signum, frame):
        self.columns = self.getTerminalColumns()
        if self._sigwinch_default:
            self._sigwinch_default(signum, frame)

    def getTerminalColumns(self):
        def ioctl_GWINSZ(fd):
            try:
                cr = struct.unpack('hh', fcntl.ioctl(fd, self.termios.TIOCGWINSZ, '1234'))
            except:
                return None
            return cr
        cr = ioctl_GWINSZ(sys.stdout.fileno())
        if not cr:
            try:
                fd = os.open(os.ctermid(), os.O_RDONLY)
                cr = ioctl_GWINSZ(fd)
                os.close(fd)
            except:
                pass
        if not cr:
            try:
                cr = (env['LINES'], env['COLUMNS'])
            except:
                cr = (25, 80)
        return cr[1]

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
            try:
                self._sigwinch_default = signal.getsignal(signal.SIGWINCH)
                signal.signal(signal.SIGWINCH, self.sigwinch_handle)
            except:
                pass
            self.columns = self.getTerminalColumns()
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
        tasks = []
        for t in runningpids:
            tasks.append("%s (pid %s)" % (activetasks[t]["title"], t))

        if self.main.shutdown:
            content = "Waiting for %s running tasks to finish:" % len(activetasks)
        else:
            content = "Currently %s running tasks (%s of %s):" % (len(activetasks), self.helper.tasknumber_current, self.helper.tasknumber_total)
        print content
        lines = 1 + int(len(content) / (self.columns + 1))
        for tasknum, task in enumerate(tasks):
            content = "%s: %s" % (tasknum, task)
            print content
            lines = lines + 1 + int(len(content) / (self.columns + 1))
        self.footer_present = lines
        self.lastpids = runningpids[:]

    def finish(self):
        if self.stdinbackup:
            fd = sys.stdin.fileno()
            self.termios.tcsetattr(fd, self.termios.TCSADRAIN, self.stdinbackup)

def main(server, eventHandler):
    return bb.ui.knotty.main(server, eventHandler, TerminalFilter2)
