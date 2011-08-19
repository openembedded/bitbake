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
import logging
import tempfile
import datetime

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
         "fatal-error"         : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,)),
         "command-failed"      : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_STRING,)),
         "reload-triggered"    : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                  (gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,)),
    }

    (CFG_PATH_LOCAL, CFG_PATH_HOB, CFG_PATH_LAYERS, CFG_FILES_DISTRO, CFG_FILES_MACH, CFG_FILES_SDK, FILES_MATCH_CLASS, GENERATE_TGTS, REPARSE_FILES, BUILD_IMAGE) = range(10)

    def __init__(self, taskmodel, server):
        gobject.GObject.__init__(self)

        self.current_command = None
        self.building = None
        self.build_toolchain = False
        self.build_toolchain_headers = False
        self.generating = False
        self.build_queue = []
        self.current_phase = None
        self.image_dir = None

        self.model = taskmodel
        self.server = server

        self.image_output_types = self.server.runCommand(["getVariable", "IMAGE_FSTYPES"]).split(" ")

    def run_next_command(self):
        if self.current_command and not self.generating:
            self.emit("generating-data")
            self.generating = True

        if self.current_command == self.CFG_PATH_LOCAL:
            self.current_command = self.CFG_PATH_HOB
            self.server.runCommand(["findConfigFilePath", "hob.local.conf"])
        elif self.current_command == self.CFG_PATH_HOB:
            self.current_command = self.CFG_PATH_LAYERS
            self.server.runCommand(["findConfigFilePath", "bblayers.conf"])
        elif self.current_command == self.CFG_PATH_LAYERS:
            self.current_command = self.CFG_FILES_DISTRO
            self.server.runCommand(["findConfigFiles", "DISTRO"])
        elif self.current_command == self.CFG_FILES_DISTRO:
            self.current_command = self.CFG_FILES_MACH
            self.server.runCommand(["findConfigFiles", "MACHINE"])
        elif self.current_command == self.CFG_FILES_MACH:
            self.current_command = self.CFG_FILES_SDK
            self.server.runCommand(["findConfigFiles", "MACHINE-SDK"])
        elif self.current_command == self.CFG_FILES_SDK:
            self.current_command = self.FILES_MATCH_CLASS
            self.server.runCommand(["findFilesMatchingInDir", "rootfs_", "classes"])
        elif self.current_command == self.FILES_MATCH_CLASS:
            self.current_command = self.GENERATE_TGTS
            self.server.runCommand(["generateTargetsTree", "classes/image.bbclass"])
        elif self.current_command == self.GENERATE_TGTS:
            if self.generating:
                self.emit("data-generated")
                self.generating = False
            self.current_command = None
        elif self.current_command == self.REPARSE_FILES:
            if self.build_queue:
                self.current_command = self.BUILD_IMAGE
            else:
                self.current_command = self.CFG_PATH_LAYERS
            self.server.runCommand(["resetCooker"])
            self.server.runCommand(["reparseFiles"])
        elif self.current_command == self.BUILD_IMAGE:
            self.building = "image"
            if self.generating:
                self.emit("data-generated")
                self.generating = False
            self.server.runCommand(["buildTargets", self.build_queue, "build"])
            self.build_queue = []
            self.current_command = None

    def handle_event(self, event, running_build, pbar):
        if not event:
	    return

        # If we're running a build, use the RunningBuild event handler
        if self.building:
            self.current_phase = "building"
            running_build.handle_event(event)
        elif isinstance(event, bb.event.TargetsTreeGenerated):
            self.current_phase = "data generation"
            if event._model:
                self.model.populate(event._model)
        elif isinstance(event, bb.event.ConfigFilesFound):
            self.current_phase = "configuration lookup"
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
            self.current_phase = "configuration lookup"
            path = event._path
            self.emit("config-found", path)
        elif isinstance(event, bb.event.FilesMatchingFound):
            self.current_phase = "configuration lookup"
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
            self.current_phase = None
            self.run_next_command()
        elif isinstance(event, bb.command.CommandFailed):
            self.emit("command-failed", event.error)
        elif isinstance(event, bb.event.CacheLoadStarted):
            self.current_phase = "cache loading"
            bb.ui.crumbs.hobeventhandler.progress_total = event.total
            pbar.set_text("Loading cache: %s/%s" % (0, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.CacheLoadProgress):
            self.current_phase = "cache loading"
            pbar.set_text("Loading cache: %s/%s" % (event.current, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.CacheLoadCompleted):
            self.current_phase = None
            pbar.set_text("Loading...")
        elif isinstance(event, bb.event.ParseStarted):
            self.current_phase = "recipe parsing"
            if event.total == 0:
                return
            bb.ui.crumbs.hobeventhandler.progress_total = event.total
            pbar.set_text("Processing recipes: %s/%s" % (0, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.ParseProgress):
            self.current_phase = "recipe parsing"
            pbar.set_text("Processing recipes: %s/%s" % (event.current, bb.ui.crumbs.hobeventhandler.progress_total))
        elif isinstance(event, bb.event.ParseCompleted):
            self.current_phase = None
            pbar.set_fraction(1.0)
            pbar.set_text("Loading...")
        elif isinstance(event, logging.LogRecord):
            format = bb.msg.BBLogFormatter("%(levelname)s: %(message)s")
            if event.levelno >= format.CRITICAL:
                self.emit("fatal-error", event.getMessage(), self.current_phase)
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
        self.current_command = self.REPARSE_FILES
        self.run_next_command()

    def set_bbthreads(self, threads):
        self.server.runCommand(["setVariable", "BB_NUMBER_THREADS", threads])

    def set_pmake(self, threads):
        pmake = "-j %s" % threads
        self.server.runCommand(["setVariable", "BB_NUMBER_THREADS", pmake])

    def build_image(self, image, configurator):
        targets = []
        targets.append(image)
        if self.build_toolchain and self.build_toolchain_headers:
            targets.append("meta-toolchain-sdk")
        elif self.build_toolchain:
            targets.append("meta-toolchain")
        self.build_queue = targets

        bbpath_ok = False
        bbpath = self.server.runCommand(["getVariable", "BBPATH"])
        if self.image_dir in bbpath.split(":"):
            bbpath_ok = True

        bbfiles_ok = False
        bbfiles = self.server.runCommand(["getVariable", "BBFILES"]).split(" ")
        for files in bbfiles:
            import re
            pattern = "%s/\*.bb" % self.image_dir
            if re.match(pattern, files):
                bbfiles_ok = True

        if not bbpath_ok:
            nbbp = self.image_dir
        else:
            nbbp = None

        if not bbfiles_ok:
            nbbf = "%s/*.bb" % self.image_dir
        else:
            nbbf = None

        if not bbfiles_ok or not bbpath_ok:
            configurator.insertTempBBPath(nbbp, nbbf)

        self.current_command = self.REPARSE_FILES
        self.run_next_command()

    def build_packages(self, pkgs):
        self.building = "packages"
        self.server.runCommand(["buildTargets", pkgs, "build"])

    def cancel_build(self, force=False):
        if force:
            # Force the cooker to stop as quickly as possible
            self.server.runCommand(["stateStop"])
        else:
            # Wait for tasks to complete before shutting down, this helps
            # leave the workdir in a usable state
            self.server.runCommand(["stateShutdown"])

    def set_incompatible_license(self, incompatible):
        self.server.runCommand(["setVariable", "INCOMPATIBLE_LICENSE", incompatible])

    def toggle_toolchain(self, enabled):
        if self.build_toolchain != enabled:
            self.build_toolchain = enabled

    def toggle_toolchain_headers(self, enabled):
        if self.build_toolchain_headers != enabled:
            self.build_toolchain_headers = enabled

    def set_fstypes(self, fstypes):
        self.server.runCommand(["setVariable", "IMAGE_FSTYPES", fstypes])

    def add_image_output_type(self, output_type):
        if output_type not in self.image_output_types:
            self.image_output_types.append(output_type)
            fstypes = " ".join(self.image_output_types).lstrip(" ")
            self.set_fstypes(fstypes)
        return self.image_output_types

    def remove_image_output_type(self, output_type):
        if output_type in self.image_output_types:
            ind = self.image_output_types.index(output_type)
            self.image_output_types.pop(ind)
            fstypes = " ".join(self.image_output_types).lstrip(" ")
            self.set_fstypes(fstypes)
        return self.image_output_types

    def get_image_deploy_dir(self):
        return self.server.runCommand(["getVariable", "DEPLOY_DIR_IMAGE"])

    def make_temp_dir(self):
        self.image_dir = os.path.join(tempfile.gettempdir(), 'hob-images')
        bb.utils.mkdirhier(self.image_dir)

    def remove_temp_dir(self):
        bb.utils.remove(self.image_dir, True)

    def get_temp_recipe_path(self, name):
        timestamp = datetime.date.today().isoformat()
        image_file = "hob-%s-variant-%s.bb" % (name, timestamp)
        recipepath =  os.path.join(self.image_dir, image_file)
        return recipepath
