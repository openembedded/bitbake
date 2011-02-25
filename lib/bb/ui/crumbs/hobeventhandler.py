#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2011        Intel Corporation
#
# Authored by Joshua Lock <josh@linux.intel.com>
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

import gobject
from bb.ui.crumbs.progress import ProgressBar

progress_total = 0

class HobHandler(gobject.GObject):

    """
    This object does BitBake event handling for the hob gui.
    """
    __gsignals__ = {
         "machines-updated" : (gobject.SIGNAL_RUN_LAST,
	                       gobject.TYPE_NONE,
			       (gobject.TYPE_PYOBJECT,)),
	 "distros-updated" : (gobject.SIGNAL_RUN_LAST,
	 		      gobject.TYPE_NONE,
			      (gobject.TYPE_PYOBJECT,)),
         "generating-data" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE,
                              ()),
         "data-generated" : (gobject.SIGNAL_RUN_LAST,
                             gobject.TYPE_NONE,
                             ())
    }

    def __init__(self, taskmodel, server):
        gobject.GObject.__init__(self)

        self.model = taskmodel
        self.server = server
        self.current_command = None
        self.building = False

        self.command_map = {
            "findConfigFilesDistro" : ("findConfigFiles", "MACHINE", "findConfigFilesMachine"),
            "findConfigFilesMachine" : ("generateTargetsTree", "classes/image.bbclass", None),
            "generateTargetsTree"  : (None, None, None),
            }

    def run_next_command(self):
        # FIXME: this is ugly and I *will* replace it
        if self.current_command:
            next_cmd = self.command_map[self.current_command]
            command = next_cmd[0]
            argument = next_cmd[1]
            self.current_command = next_cmd[2]
            if command == "generateTargetsTree":
                self.emit("generating-data")
            self.server.runCommand([command, argument])

    def handle_event(self, event, running_build, pbar=None):
        if not event:
	    return

        # If we're running a build, use the RunningBuild event handler
        if self.building:
            running_build.handle_event(event)
        elif isinstance(event, bb.event.TargetsTreeGenerated):
            self.emit("data-generated")
            if event._model:
                self.model.populate(event._model)
                
        elif isinstance(event, bb.event.ConfigFilesFound):
            var = event._variable
	    if var == "distro":
		distros = event._values
		distros.sort()
		self.emit("distros-updated", distros)
	    elif var == "machine":
	        machines = event._values
		machines.sort()
		self.emit("machines-updated", machines)

        elif isinstance(event, bb.command.CommandCompleted):
            self.run_next_command()
        elif isinstance(event, bb.event.CacheLoadStarted) and pbar:
            pbar.set_title("Loading cache")
            bb.ui.crumbs.hobeventhandler.progress_total = event.total
            pbar.update(0, bb.ui.crumbs.hobeventhandler.progress_total)
        elif isinstance(event, bb.event.CacheLoadProgress) and pbar:
            pbar.update(event.current, bb.ui.crumbs.hobeventhandler.progress_total)
        elif isinstance(event, bb.event.CacheLoadCompleted) and pbar:
            pbar.update(bb.ui.crumbs.hobeventhandler.progress_total, bb.ui.crumbs.hobeventhandler.progress_total)
        elif isinstance(event, bb.event.ParseStarted) and pbar:
            if event.total == 0:
                return
            pbar.set_title("Processing recipes")
            bb.ui.crumbs.hobeventhandler.progress_total = event.total
            pbar.update(0, bb.ui.crumbs.hobeventhandler.progress_total)
        elif isinstance(event, bb.event.ParseProgress) and pbar:
            pbar.update(event.current, bb.ui.crumbs.hobeventhandler.progress_total)
        elif isinstance(event, bb.event.ParseCompleted) and pbar:
            pbar.hide()
            
        return

    def event_handle_idle_func (self, eventHandler, running_build, pbar):
        # Consume as many messages as we can in the time available to us
        event = eventHandler.getEvent()
        while event:
            self.handle_event(event, running_build, pbar)
            event = eventHandler.getEvent()
        return True

    def set_machine(self, machine):
        self.server.runCommand(["setVariable", "MACHINE", machine])
        self.current_command = "findConfigFilesMachine"
        self.run_next_command()

    def set_distro(self, distro):
        self.server.runCommand(["setVariable", "DISTRO", distro])

    def run_build(self, targets):
        self.building = True
        self.server.runCommand(["buildTargets", targets, "build"])

    def cancel_build(self):
        # Note: this may not be the right way to stop an in-progress build
        self.server.runCommand(["stateStop"])
