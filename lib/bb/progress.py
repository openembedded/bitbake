"""
BitBake progress handling code
"""

# Copyright (C) 2016 Intel Corporation
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

import sys
import re
import time
import bb.event
import bb.build

class ProgressHandler(object):
    """
    Base class that can pretend to be a file object well enough to be
    used to build objects to intercept console output and determine the
    progress of some operation.
    """
    def __init__(self, d, outfile=None):
        self._progress = 0
        self._data = d
        self._lastevent = 0
        if outfile:
            self._outfile = outfile
        else:
            self._outfile = sys.stdout

    def _fire_progress(self, taskprogress, rate=None):
        """Internal function to fire the progress event"""
        bb.event.fire(bb.build.TaskProgress(taskprogress, rate), self._data)

    def write(self, string):
        self._outfile.write(string)

    def flush(self):
        self._outfile.flush()

    def update(self, progress, rate=None):
        ts = time.time()
        if progress > 100:
            progress = 100
        if progress != self._progress or self._lastevent + 1 < ts:
            self._fire_progress(progress, rate)
            self._lastevent = ts
            self._progress = progress

class BasicProgressHandler(ProgressHandler):
    def __init__(self, d, regex=r'(\d+)%', outfile=None):
        super(BasicProgressHandler, self).__init__(d, outfile)
        self._regex = re.compile(regex)
        # Send an initial progress event so the bar gets shown
        self._fire_progress(0)

    def write(self, string):
        percs = self._regex.findall(string)
        if percs:
            progress = int(percs[-1])
            self.update(progress)
        super(BasicProgressHandler, self).write(string)

class OutOfProgressHandler(ProgressHandler):
    def __init__(self, d, regex, outfile=None):
        super(OutOfProgressHandler, self).__init__(d, outfile)
        self._regex = re.compile(regex)
        # Send an initial progress event so the bar gets shown
        self._fire_progress(0)

    def write(self, string):
        nums = self._regex.findall(string)
        if nums:
            progress = (float(nums[-1][0]) / float(nums[-1][1])) * 100
            self.update(progress)
        super(OutOfProgressHandler, self).write(string)
