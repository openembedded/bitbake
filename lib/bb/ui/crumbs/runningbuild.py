#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2008        Intel Corporation
#
# Authored by Rob Bradford <rob@linux.intel.com>
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

import gtk
import gobject

class RunningBuildModel (gtk.TreeStore):
    (COL_TYPE, COL_PACKAGE, COL_TASK, COL_MESSAGE, COL_ICON, COL_ACTIVE) = (0, 1, 2, 3, 4, 5)
    def __init__ (self):
        gtk.TreeStore.__init__ (self,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_BOOLEAN)

class RunningBuild (gobject.GObject):
    __gsignals__ = {
          'build-succeeded' : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               ()),
          'build-failed' : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                            ())
          }
    pids_to_task = {}
    tasks_to_iter = {}

    def __init__ (self):
        gobject.GObject.__init__ (self)
        self.model = RunningBuildModel()

    def handle_event (self, event, pbar=None):
        # Handle an event from the event queue, this may result in updating
        # the model and thus the UI. Or it may be to tell us that the build
        # has finished successfully (or not, as the case may be.)

        parent = None
        pid = 0
        package = None
        task = None

        # If we have a pid attached to this message/event try and get the
        # (package, task) pair for it. If we get that then get the parent iter
        # for the message.
        if hasattr(event, 'pid'):
            pid = event.pid
            if pid in self.pids_to_task:
                (package, task) = self.pids_to_task[pid]
                parent = self.tasks_to_iter[(package, task)]

        if isinstance(event, bb.msg.MsgBase):
            # Ignore the "Running task i of n .."
            if (event._message.startswith ("Running task")):
                return # don't add these to the list

            # Set a pretty icon for the message based on it's type.
            if isinstance(event, bb.msg.MsgWarn):
                icon = "dialog-warning"
            elif isinstance(event, bb.msg.MsgError):
                icon = "dialog-error"
            else:
                icon = None

            # Add the message to the tree either at the top level if parent is
            # None otherwise as a descendent of a task.
            self.model.append (parent,
                               (event.__class__.__name__.split()[-1], # e.g. MsgWarn, MsgError
                                package,
                                task,
                                event._message,
                                icon,
                                False))
        elif isinstance(event, bb.build.TaskStarted):
            (package, task) = (event._package, event._task)

            # Save out this PID.
            self.pids_to_task[pid] = (package, task)

            # Check if we already have this package in our model. If so then
            # that can be the parent for the task. Otherwise we create a new
            # top level for the package.
            if ((package, None) in self.tasks_to_iter):
                parent = self.tasks_to_iter[(package, None)]
            else:
                parent = self.model.append (None, (None,
                                                   package,
                                                   None,
                                                   "Package: %s" % (package),
                                                   None,
                                                   False))
                self.tasks_to_iter[(package, None)] = parent

            # Because this parent package now has an active child mark it as
            # such.
            self.model.set(parent, self.model.COL_ICON, "gtk-execute")

            # Add an entry in the model for this task
            i = self.model.append (parent, (None,
                                            package,
                                            task,
                                            "Task: %s" % (task),
                                            None,
                                            False))

            # Save out the iter so that we can find it when we have a message
            # that we need to attach to a task.
            self.tasks_to_iter[(package, task)] = i

            # Mark this task as active.
            self.model.set(i, self.model.COL_ICON, "gtk-execute")

        elif isinstance(event, bb.build.TaskBase):

            if isinstance(event, bb.build.TaskFailed):
                # Mark the task as failed
                i = self.tasks_to_iter[(package, task)]
                self.model.set(i, self.model.COL_ICON, "dialog-error")

                # Mark the parent package as failed
                i = self.tasks_to_iter[(package, None)]
                self.model.set(i, self.model.COL_ICON, "dialog-error")
            else:
                # Mark the task as inactive
                i = self.tasks_to_iter[(package, task)]
                self.model.set(i, self.model.COL_ICON, None)

                # Mark the parent package as inactive
                i = self.tasks_to_iter[(package, None)]
                self.model.set(i, self.model.COL_ICON, None)


            # Clear the iters and the pids since when the task goes away the
            # pid will no longer be used for messages
            del self.tasks_to_iter[(package, task)]
            del self.pids_to_task[pid]

        elif isinstance(event, bb.event.BuildCompleted):
            failures = int (event._failures)

            # Emit the appropriate signal depending on the number of failures
            if (failures > 1):
                self.emit ("build-failed")
            else:
                self.emit ("build-succeeded")

        elif isinstance(event, bb.event.ParseProgress) and pbar:
            x = event.sofar
            y = event.total
            if x == y:
                pbar.hide()
                return
            pbar.update(x, y)

class RunningBuildTreeView (gtk.TreeView):
    def __init__ (self):
        gtk.TreeView.__init__ (self)

        # The icon that indicates whether we're building or failed.
        renderer = gtk.CellRendererPixbuf ()
        col = gtk.TreeViewColumn ("Status", renderer)
        col.add_attribute (renderer, "icon-name", 4)
        self.append_column (col)

        # The message of the build.
        renderer = gtk.CellRendererText ()
        col = gtk.TreeViewColumn ("Message", renderer, text=3)
        self.append_column (col)
