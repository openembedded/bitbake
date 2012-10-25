#!/usr/bin/env python
#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2012        Intel Corporation
#
# Authored by Cristiana Voicu <cristiana.voicu@intel.com>
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

import threading
import gtk
import subprocess

#
# OpeningLogThread
#
class OpeningLogThread(threading.Thread):
    def __init__(self, dialog, log_file, parent):
        threading.Thread.__init__(self)
        self.dialog =dialog
        self.log_file = log_file
        self.parent = parent

    def run(self):
        p = subprocess.Popen(['xdg-open',self.log_file])
        retcode = p.poll()
        while (retcode == None):
            if self.parent.stop:
                try:
                    p.terminate()
                except OSError, e:
                    if e.errno == 3:
                        pass  # no such process
                    else:
                        raise
            retcode = p.poll()

        self.dialog.destroy()

