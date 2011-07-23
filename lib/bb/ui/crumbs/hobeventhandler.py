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

progress_total = 0

class HobHandler(gobject.GObject):

    """
    This object does BitBake event handling for the hob gui.
    """
    __gsignals__ = {
         "machines-updated"    : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_PYOBJECT,)),
         "sdk-machines-updated": (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_PYOBJECT,)),
         "distros-updated"     : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_PYOBJECT,)),
         "package-formats-found" : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_PYOBJECT,)),
         "config-found"        : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_STRING,)),
         "generating-data"     : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  ()),
         "data-generated"      : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  ()),
         "error"               : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_STRING,)),
         "build-complete"      : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  ()),
         "reload-triggered"    : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_STRING,
                                   gobject.TYPE_STRING)),
    }

    def __init__(self, taskmodel, server):
        gobject.GObject.__init__(self)
        self.current_command = None
        self.building = None
        self.gplv3_excluded = False
        self.build_toolchain = False
        self.build_toolchain_headers = False
        self.generating = False
        self.build_queue = []

        self.model = taskmodel
        self.server = server

        self.image_output_types = self.server.runCommand(["getVariable", "IMAGE_FSTYPES"]).split(" ")

        self.command_map = {
            "findConfigFilePathLocal" : ("findConfigFilePath", ["hob.local.conf"], "findConfigFilePathHobLocal"),
            "findConfigFilePathHobLocal" : ("findConfigFilePath", ["bblayers.conf"], "findConfigFilePathLayers"),
            "findConfigFilePathLayers" : ("findConfigFiles", ["DISTRO"], "findConfigFilesDistro"),
            "findConfigFilesDistro" : ("findConfigFiles", ["MACHINE"], "findConfigFilesMachine"),
            "findConfigFilesMachine" : ("findConfigFiles", ["MACHINE-SDK"], "findConfigFilesSdkMachine"),
            "findConfigFilesSdkMachine" : ("findFilesMatchingInDir", ["rootfs_", "classes"], "findFilesMatchingPackage"),
            "findFilesMatchingPackage" : ("generateTargetsTree", ["classes/image.bbclass"], None),
            "generateTargetsTree"  : (None, [], None),
            }

    def run_next_command(self):
        # FIXME: this is ugly and I *will* replace it
        if self.current_command:
            if not self.generating:
                self.emit("generating-data")
                self.generating = True
            next_cmd = self.command_map[self.current_command]
            command = next_cmd[0]
            argument = next_cmd[1]
            self.current_command = next_cmd[2]
            args = [command]
            args.extend(argument)
            self.server.runCommand(args)

    def handle_event(self, event, running_build, pbar):
        if not event:
	    return

        # If we're running a build, use the RunningBuild event handler
        if self.building:
            running_build.handle_event(event)
        elif isinstance(event, bb.event.TargetsTreeGenerated):
            self.emit("data-generated")
            self.generating = False
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
            elif var == "machine-sdk":
                sdk_machines = event._values
                sdk_machines.sort()
                self.emit("sdk-machines-updated", sdk_machines)
        elif isinstance(event, bb.event.ConfigFilePathFound):
            path = event._path
            self.emit("config-found", path)
        elif isinstance(event, bb.event.FilesMatchingFound):
            # FIXME: hard coding, should at least be a variable shared between
            # here and the caller
            if event._pattern == "rootfs_":
                formats = []
                for match in event._matches:
                    classname, sep, cls = match.rpartition(".")
                    fs, sep, format = classname.rpartition("_")
                    formats.append(format)
                formats.sort()
                self.emit("package-formats-found", formats)
        elif isinstance(event, bb.command.CommandCompleted):
            self.run_next_command()
        elif isinstance(event, bb.command.CommandFailed):
            self.emit("error", event.error)
        elif isinstance(event, bb.event.CacheLoadStarted):
            bb.ui.crumbs.hobeventhandler.progress_total = event.total
            pbar.set_text("Loading cache: %s/%s" % (0, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.CacheLoadProgress):
            pbar.set_text("Loading cache: %s/%s" % (event.current, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.CacheLoadCompleted):
            pbar.set_text("Loading cache: %s/%s" % (bb.ui.crumbs.hobeventhandler.progress_total, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.ParseStarted):
            if event.total == 0:
                return
            bb.ui.crumbs.hobeventhandler.progress_total = event.total
            pbar.set_text("Processing recipes: %s/%s" % (0, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.ParseProgress):
            pbar.set_text("Processing recipes: %s/%s" % (event.current, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.ParseCompleted):
            pbar.set_fraction(1.0)
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

    def set_sdk_machine(self, sdk_machine):
        self.server.runCommand(["setVariable", "SDKMACHINE", sdk_machine])

    def set_distro(self, distro):
        self.server.runCommand(["setVariable", "DISTRO", distro])

    def set_package_format(self, format):
        self.server.runCommand(["setVariable", "PACKAGE_CLASSES", "package_%s" % format])

    def reload_data(self, config=None):
        img = self.model.selected_image
        selected_packages, _ = self.model.get_selected_packages()
        self.emit("reload-triggered", img, " ".join(selected_packages))
        self.server.runCommand(["reparseFiles"])
        self.current_command = "findConfigFilePathLayers"
        self.run_next_command()

    def set_bbthreads(self, threads):
        self.server.runCommand(["setVariable", "BB_NUMBER_THREADS", threads])

    def set_pmake(self, threads):
        pmake = "-j %s" % threads
        self.server.runCommand(["setVariable", "BB_NUMBER_THREADS", pmake])

    def run_build(self, tgts):
        self.building = "image"
        targets = []
        targets.append(tgts)
        if self.build_toolchain and self.build_toolchain_headers:
            targets = ["meta-toolchain-sdk"] + targets
        elif self.build_toolchain:
            targets = ["meta-toolchain"] + targets
        self.server.runCommand(["buildTargets", targets, "build"])

    def build_packages(self, pkgs):
        self.building = "packages"
        if 'meta-toolchain' in self.build_queue:
            self.build_queue.remove('meta-toolchain')
            pkgs.extend('meta-toolchain')
        self.server.runCommand(["buildTargets", pkgs, "build"])

    def build_file(self, image):
        self.building = "image"
        self.server.runCommand(["buildFile", image, "build"])

    def cancel_build(self, force=False):
        if force:
            # Force the cooker to stop as quickly as possible
            self.server.runCommand(["stateStop"])
        else:
            # Wait for tasks to complete before shutting down, this helps
            # leave the workdir in a usable state
            self.server.runCommand(["stateShutdown"])

    def toggle_gplv3(self, excluded):
        if self.gplv3_excluded != excluded:
            self.gplv3_excluded = excluded
            if excluded:
                self.server.runCommand(["setVariable", "INCOMPATIBLE_LICENSE", "GPLv3"])
            else:
                self.server.runCommand(["setVariable", "INCOMPATIBLE_LICENSE", ""])

    def toggle_toolchain(self, enabled):
        if self.build_toolchain != enabled:
            self.build_toolchain = enabled

    def toggle_toolchain_headers(self, enabled):
        if self.build_toolchain_headers != enabled:
            self.build_toolchain_headers = enabled

    def queue_image_recipe_path(self, path):
        self.build_queue.append(path)

    def build_complete_cb(self, running_build):
        if len(self.build_queue) > 0:
            next = self.build_queue.pop(0)
            if next.endswith('.bb'):
                self.build_file(next)
                self.building = 'image'
                self.build_file(next)
            else:
                self.build_packages(next.split(" "))
        else:
            self.building = None
            self.emit("build-complete")

    def set_fstypes(self, fstypes):
        self.server.runCommand(["setVariable", "IMAGE_FSTYPES", fstypes])

    def add_image_output_type(self, output_type):
        if output_type not in self.image_output_types:
            self.image_output_types.append(output_type)
            fstypes = " ".join(self.image_output_types)
            self.set_fstypes(fstypes)
        return fstypes

    def remove_image_output_type(self, output_type):
        if output_type in self.image_output_types:
            ind = self.image_output_types.index(output_type)
            self.image_output_types.pop(ind)
            fstypes = " ".join(self.image_output_types)
            self.set_fstypes(fstypes)
        return fstypes

    def get_image_deploy_dir(self):
        return self.server.runCommand(["getVariable", "DEPLOY_DIR_IMAGE"])
