
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
import logging
import time
import urllib
import urllib2

class Colors(object):
    OK = "#ffffff"
    RUNNING = "#aaffaa"
    WARNING ="#f88017"
    ERROR = "#ffaaaa"

class RunningBuildModel (gtk.TreeStore):
    (COL_LOG, COL_PACKAGE, COL_TASK, COL_MESSAGE, COL_ICON, COL_COLOR, COL_NUM_ACTIVE) = range(7)

    def __init__ (self):
        gtk.TreeStore.__init__ (self,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_INT)

class RunningBuild (gobject.GObject):
    __gsignals__ = {
          'build-started' : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               ()),
          'build-succeeded' : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               ()),
          'build-failed' : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                            ()),
          'build-complete' : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE,
                              ())
          }
    pids_to_task = {}
    tasks_to_iter = {}

    def __init__ (self, sequential=False):
        gobject.GObject.__init__ (self)
        self.model = RunningBuildModel()
        self.sequential = sequential

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
        if hasattr(event, 'process'):
            pid = event.process

        if pid and pid in self.pids_to_task:
            (package, task) = self.pids_to_task[pid]
            parent = self.tasks_to_iter[(package, task)]

        if(isinstance(event, logging.LogRecord)):
            if (event.levelno < logging.INFO or
                event.msg.startswith("Running task")):
                return # don't add these to the list

            if event.levelno >= logging.ERROR:
                icon = "dialog-error"
                color = Colors.ERROR
            elif event.levelno >= logging.WARNING:
                icon = "dialog-warning"
                color = Colors.WARNING
            else:
                icon = None
                color = Colors.OK

            # if we know which package we belong to, we'll append onto its list.
            # otherwise, we'll jump to the top of the master list
            if self.sequential or not parent:
                tree_add = self.model.append
            else:
                tree_add = self.model.prepend
            tree_add(parent,
                     (None,
                      package,
                      task,
                      event.getMessage(),
                      icon,
                      color,
                      0))

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
                if self.sequential:
                    add = self.model.append
                else:
                    add = self.model.prepend
                parent = add(None, (None,
                                    package,
                                    None,
                                    "Package: %s" % (package),
                                    None,
                                    Colors.OK,
                                    0))
                self.tasks_to_iter[(package, None)] = parent

            # Because this parent package now has an active child mark it as
            # such.
            # @todo if parent is already in error, don't mark it green
            self.model.set(parent, self.model.COL_ICON, "gtk-execute",
                           self.model.COL_COLOR, Colors.RUNNING)

            # Add an entry in the model for this task
            i = self.model.append (parent, (None,
                                            package,
                                            task,
                                            "Task: %s" % (task),
                                            "gtk-execute",
                                            Colors.RUNNING,
                                            0))

            # update the parent's active task count
            num_active = self.model.get(parent, self.model.COL_NUM_ACTIVE)[0] + 1
            self.model.set(parent, self.model.COL_NUM_ACTIVE, num_active)

            # Save out the iter so that we can find it when we have a message
            # that we need to attach to a task.
            self.tasks_to_iter[(package, task)] = i

        elif isinstance(event, bb.build.TaskBase):
            current = self.tasks_to_iter[(package, task)]
            parent = self.tasks_to_iter[(package, None)]

            # remove this task from the parent's active count
            num_active = self.model.get(parent, self.model.COL_NUM_ACTIVE)[0] - 1
            self.model.set(parent, self.model.COL_NUM_ACTIVE, num_active)

            if isinstance(event, bb.build.TaskFailed):
                # Mark the task and parent as failed
                icon = "dialog-error"
                color = Colors.ERROR

                logfile = event.logfile
                if logfile and os.path.exists(logfile):
                    with open(logfile) as f:
                        logdata = f.read()
                        self.model.append(current, ('pastebin', None, None, logdata, 'gtk-error', Colors.OK, 0))

                for i in (current, parent):
                    self.model.set(i, self.model.COL_ICON, icon,
                                   self.model.COL_COLOR, color)
            else:
                icon = None
                color = Colors.OK

                # Mark the task as inactive
                self.model.set(current, self.model.COL_ICON, icon,
                               self.model.COL_COLOR, color)

                # Mark the parent package as inactive, but make sure to
                # preserve error and active states
                i = self.tasks_to_iter[(package, None)]
                if self.model.get(parent, self.model.COL_ICON) != 'dialog-error':
                    self.model.set(parent, self.model.COL_ICON, icon)
                    if num_active == 0:
                        self.model.set(parent, self.model.COL_COLOR, Colors.OK)

            # Clear the iters and the pids since when the task goes away the
            # pid will no longer be used for messages
            del self.tasks_to_iter[(package, task)]
            del self.pids_to_task[pid]

        elif isinstance(event, bb.event.BuildStarted):

            self.emit("build-started")
            self.model.prepend(None, (None,
                                      None,
                                      None,
                                      "Build Started (%s)" % time.strftime('%m/%d/%Y %H:%M:%S'),
                                      None,
                                      Colors.OK,
                                      0))
        elif isinstance(event, bb.event.BuildCompleted):
            failures = int (event._failures)
            self.model.prepend(None, (None,
                                      None,
                                      None,
                                      "Build Completed (%s)" % time.strftime('%m/%d/%Y %H:%M:%S'),
                                      None,
                                      Colors.OK,
                                      0))

            # Emit a generic "build-complete" signal for things wishing to
            # handle when the build is finished
            self.emit("build-complete")
            # Emit the appropriate signal depending on the number of failures
            if (failures >= 1):
                self.emit ("build-failed")
            else:
                self.emit ("build-succeeded")

        elif isinstance(event, bb.command.CommandFailed):
            if event.error.startswith("Exited with"):
                # If the command fails with an exit code we're done, emit the
                # generic signal for the UI to notify the user
                self.emit("build-complete")

        elif isinstance(event, bb.event.CacheLoadStarted) and pbar:
            pbar.set_title("Loading cache")
            self.progress_total = event.total
            pbar.update(0, self.progress_total)
        elif isinstance(event, bb.event.CacheLoadProgress) and pbar:
            pbar.update(event.current, self.progress_total)
        elif isinstance(event, bb.event.CacheLoadCompleted) and pbar:
            pbar.update(self.progress_total, self.progress_total)
            pbar.hide()
        elif isinstance(event, bb.event.ParseStarted) and pbar:
            if event.total == 0:
                return
            pbar.set_title("Processing recipes")
            self.progress_total = event.total
            pbar.update(0, self.progress_total)
        elif isinstance(event, bb.event.ParseProgress) and pbar:
            pbar.update(event.current, self.progress_total)
        elif isinstance(event, bb.event.ParseCompleted) and pbar:
            pbar.hide()

        return


def do_pastebin(text):
    url = 'http://pastebin.com/api_public.php'
    params = {'paste_code': text, 'paste_format': 'text'}

    req = urllib2.Request(url, urllib.urlencode(params))
    response = urllib2.urlopen(req)
    paste_url = response.read()

    return paste_url


class RunningBuildTreeView (gtk.TreeView):
    __gsignals__ = {
        "button_press_event" : "override"
        }
    def __init__ (self, readonly=False):
        gtk.TreeView.__init__ (self)
        self.readonly = readonly

        # The icon that indicates whether we're building or failed.
        renderer = gtk.CellRendererPixbuf ()
        col = gtk.TreeViewColumn ("Status", renderer)
        col.add_attribute (renderer, "icon-name", 4)
        self.append_column (col)

        # The message of the build.
        self.message_renderer = gtk.CellRendererText ()
        self.message_column = gtk.TreeViewColumn ("Message", self.message_renderer, text=3)
        self.message_column.add_attribute(self.message_renderer, 'background', 5)
        self.message_renderer.set_property('editable', (not self.readonly))
        self.append_column (self.message_column)

    def do_button_press_event(self, event):
        gtk.TreeView.do_button_press_event(self, event)

        if event.button == 3:
            selection = super(RunningBuildTreeView, self).get_selection()
            (model, it) = selection.get_selected()
            if it is not None:
                can_paste = model.get(it, model.COL_LOG)[0]
                if can_paste == 'pastebin':
                    # build a simple menu with a pastebin option
                    menu = gtk.Menu()
                    menuitem = gtk.MenuItem("Copy")
                    menu.append(menuitem)
                    menuitem.connect("activate", self.copy_handler, (model, it))
                    menuitem.show()
                    menuitem = gtk.MenuItem("Send log to pastebin")
                    menu.append(menuitem)
                    menuitem.connect("activate", self.pastebin_handler, (model, it))
                    menuitem.show()
                    menu.show()
                    menu.popup(None, None, None, event.button, event.time)

    def _add_to_clipboard(self, clipping):
        """
        Add the contents of clipping to the system clipboard.
        """
        clipboard = gtk.clipboard_get()
        clipboard.set_text(clipping)
        clipboard.store()

    def pastebin_handler(self, widget, data):
        """
        Send the log data to pastebin, then add the new paste url to the
        clipboard.
        """
        (model, it) = data
        paste_url = do_pastebin(model.get(it, model.COL_MESSAGE)[0])

        # @todo Provide visual feedback to the user that it is done and that
        # it worked.
        print paste_url

        self._add_to_clipboard(paste_url)

    def clipboard_handler(self, widget, data):
        """
        """
        (model, it) = data
        message = model.get(it, model.COL_MESSAGE)[0]

        self._add_to_clipboard(message)
