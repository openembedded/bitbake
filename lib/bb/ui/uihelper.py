# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2006 - 2007  Michael 'Mickey' Lauer
# Copyright (C) 2006 - 2007  Richard Purdie
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

class BBUIHelper:
    def __init__(self):
        self.running_tasks = {}

    def eventHandler(self, event):
        if event[0].startswith('bb.build.TaskStarted'):
            self.running_tasks["%s %s\n" % (event[1]['_package'], event[1]['_task'])] = ""
        if event[0].startswith('bb.build.TaskSucceeded'):
            del self.running_tasks["%s %s\n" % (event[1]['_package'], event[1]['_task'])]
        if event[0].startswith('bb.runqueue.runQueueTaskCompleted'):
            a = 1
        if event[0].startswith('bb.runqueue.runQueueTaskStarted'):
            a = 1
        if event[0].startswith('bb.runqueue.runQueueTaskFailed'):
            a = 1
        if event[0].startswith('bb.runqueue.runQueueExitWait'):
            a = 1

    def getTasks(self):
        return self.running_tasks
