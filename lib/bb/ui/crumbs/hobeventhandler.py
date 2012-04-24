#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2011        Intel Corporation
#
# Authored by Joshua Lock <josh@linux.intel.com>
# Authored by Dongxiao Xu <dongxiao.xu@intel.com>
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
from bb.ui.crumbs.runningbuild import RunningBuild
from bb.ui.crumbs.hobwidget import hcc

class HobHandler(gobject.GObject):

    """
    This object does BitBake event handling for the hob gui.
    """
    __gsignals__ = {
         "package-formats-updated" : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     (gobject.TYPE_PYOBJECT,)),
         "config-updated"          : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     (gobject.TYPE_STRING, gobject.TYPE_PYOBJECT,)),
         "command-succeeded"       : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     (gobject.TYPE_INT,)),
         "command-failed"          : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     (gobject.TYPE_STRING,)),
         "generating-data"         : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     ()),
         "data-generated"          : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     ()),
         "parsing-started"         : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     (gobject.TYPE_PYOBJECT,)),
         "parsing"                 : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     (gobject.TYPE_PYOBJECT,)),
         "parsing-completed"       : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                     (gobject.TYPE_PYOBJECT,)),
    }

    (GENERATE_CONFIGURATION, GENERATE_RECIPES, GENERATE_PACKAGES, GENERATE_IMAGE, POPULATE_PACKAGEINFO, SANITY_CHECK) = range(6)
    (SUB_PATH_LAYERS, SUB_FILES_DISTRO, SUB_FILES_MACH, SUB_FILES_SDKMACH, SUB_MATCH_CLASS, SUB_PARSE_CONFIG, SUB_SANITY_CHECK, SUB_GNERATE_TGTS, SUB_GENERATE_PKGINFO, SUB_BUILD_RECIPES, SUB_BUILD_IMAGE) = range(11)

    def __init__(self, server, recipe_model, package_model):
        super(HobHandler, self).__init__()

        self.build = RunningBuild(sequential=True)

        self.recipe_model = recipe_model
        self.package_model = package_model

        self.commands_async = []
        self.generating = False
        self.current_phase = None
        self.building = False
        self.recipe_queue = []
        self.package_queue = []

        self.server = server
        self.error_msg = ""
        self.initcmd = None

    def set_busy(self):
        if not self.generating:
            self.emit("generating-data")
            self.generating = True

    def clear_busy(self):
        if self.generating:
            self.emit("data-generated")
            self.generating = False

    def runCommand(self, commandline):
        try:
            return self.server.runCommand(commandline)
        except Exception as e:
            self.commands_async = []
            self.clear_busy()
            self.emit("command-failed", "Hob Exception - %s" % (str(e)))
            return None

    def run_next_command(self, initcmd=None):
        if initcmd != None:
            self.initcmd = initcmd

        if self.commands_async:
            self.set_busy()
            next_command = self.commands_async.pop(0)
        else:
            self.clear_busy()
            if self.initcmd != None:
                self.emit("command-succeeded", self.initcmd)
            return

        if next_command == self.SUB_PATH_LAYERS:
            self.runCommand(["findConfigFilePath", "bblayers.conf"])
        elif next_command == self.SUB_FILES_DISTRO:
            self.runCommand(["findConfigFiles", "DISTRO"])
        elif next_command == self.SUB_FILES_MACH:
            self.runCommand(["findConfigFiles", "MACHINE"])
        elif next_command == self.SUB_FILES_SDKMACH:
            self.runCommand(["findConfigFiles", "MACHINE-SDK"])
        elif next_command == self.SUB_MATCH_CLASS:
            self.runCommand(["findFilesMatchingInDir", "rootfs_", "classes"])
        elif next_command == self.SUB_PARSE_CONFIG:
            self.runCommand(["parseConfigurationFiles", "", ""])
        elif next_command == self.SUB_GNERATE_TGTS:
            self.runCommand(["generateTargetsTree", "classes/image.bbclass", []])
        elif next_command == self.SUB_GENERATE_PKGINFO:
            self.runCommand(["triggerEvent", "bb.event.RequestPackageInfo()"])
        elif next_command == self.SUB_SANITY_CHECK:
            self.runCommand(["triggerEvent", "bb.event.SanityCheck()"])
        elif next_command == self.SUB_BUILD_RECIPES:
            self.clear_busy()
            self.building = True
            self.runCommand(["buildTargets", self.recipe_queue, self.default_task])
            self.recipe_queue = []
        elif next_command == self.SUB_BUILD_IMAGE:
            self.clear_busy()
            self.building = True
            targets = [self.image]
            if self.package_queue:
                self.runCommand(["setVariable", "LINGUAS_INSTALL", ""])
                self.runCommand(["setVariable", "PACKAGE_INSTALL", " ".join(self.package_queue)])
            if self.toolchain_packages:
                self.runCommand(["setVariable", "TOOLCHAIN_TARGET_TASK", " ".join(self.toolchain_packages)])
                targets.append(self.toolchain)
            self.runCommand(["buildTargets", targets, self.default_task])

    def handle_event(self, event):
        if not event:
            return

        if self.building:
            self.current_phase = "building"
            self.build.handle_event(event)

        if isinstance(event, bb.event.PackageInfo):
            self.package_model.populate(event._pkginfolist)
            self.run_next_command()

        elif isinstance(event, bb.event.SanityCheckPassed):
            self.run_next_command()

        elif isinstance(event, logging.LogRecord):
            if event.levelno >= logging.ERROR:
                self.error_msg += event.msg + '\n'

        elif isinstance(event, bb.event.TargetsTreeGenerated):
            self.current_phase = "data generation"
            if event._model:
                self.recipe_model.populate(event._model)
        elif isinstance(event, bb.event.ConfigFilesFound):
            self.current_phase = "configuration lookup"
            var = event._variable
            values = event._values
            values.sort()
            self.emit("config-updated", var, values)
        elif isinstance(event, bb.event.ConfigFilePathFound):
            self.current_phase = "configuration lookup"
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
                self.emit("package-formats-updated", formats)
        elif isinstance(event, bb.command.CommandCompleted):
            self.current_phase = None
            self.run_next_command()
        elif isinstance(event, bb.command.CommandFailed):
            self.commands_async = []
            self.clear_busy()
            self.emit("command-failed", self.error_msg)
            self.error_msg = ""
        elif isinstance(event, (bb.event.ParseStarted,
                 bb.event.CacheLoadStarted,
                 bb.event.TreeDataPreparationStarted,
                 )):
            message = {}
            message["eventname"] = bb.event.getName(event)
            message["current"] = 0
            message["total"] = None
            message["title"] = "Parsing recipes: "
            self.emit("parsing-started", message)
        elif isinstance(event, (bb.event.ParseProgress,
                bb.event.CacheLoadProgress,
                bb.event.TreeDataPreparationProgress)):
            message = {}
            message["eventname"] = bb.event.getName(event)
            message["current"] = event.current
            message["total"] = event.total
            message["title"] = "Parsing recipes: "
            self.emit("parsing", message)
        elif isinstance(event, (bb.event.ParseCompleted,
                bb.event.CacheLoadCompleted,
                bb.event.TreeDataPreparationCompleted)):
            message = {}
            message["eventname"] = bb.event.getName(event)
            message["current"] = event.total
            message["total"] = event.total
            message["title"] = "Parsing recipes: "
            self.emit("parsing-completed", message)

        return

    def init_cooker(self):
        self.runCommand(["initCooker"])

    def set_extra_inherit(self, bbclass):
        inherits = self.runCommand(["getVariable", "INHERIT"]) or ""
        inherits = inherits + " " + bbclass
        self.runCommand(["setVariable", "INHERIT", inherits])

    def set_bblayers(self, bblayers):
        self.runCommand(["setVariable", "BBLAYERS_HOB", " ".join(bblayers)])

    def set_machine(self, machine):
        if machine:
            self.runCommand(["setVariable", "MACHINE_HOB", machine])

    def set_sdk_machine(self, sdk_machine):
        self.runCommand(["setVariable", "SDKMACHINE_HOB", sdk_machine])

    def set_image_fstypes(self, image_fstypes):
        self.runCommand(["setVariable", "IMAGE_FSTYPES", image_fstypes])

    def set_distro(self, distro):
        self.runCommand(["setVariable", "DISTRO_HOB", distro])

    def set_package_format(self, format):
        package_classes = ""
        for pkgfmt in format.split():
            package_classes += ("package_%s" % pkgfmt + " ")
        self.runCommand(["setVariable", "PACKAGE_CLASSES_HOB", package_classes])

    def set_bbthreads(self, threads):
        self.runCommand(["setVariable", "BB_NUMBER_THREADS_HOB", threads])

    def set_pmake(self, threads):
        pmake = "-j %s" % threads
        self.runCommand(["setVariable", "PARALLEL_MAKE_HOB", pmake])

    def set_dl_dir(self, directory):
        self.runCommand(["setVariable", "DL_DIR_HOB", directory])

    def set_sstate_dir(self, directory):
        self.runCommand(["setVariable", "SSTATE_DIR_HOB", directory])

    def set_sstate_mirror(self, url):
        self.runCommand(["setVariable", "SSTATE_MIRROR_HOB", url])

    def set_extra_size(self, image_extra_size):
        self.runCommand(["setVariable", "IMAGE_ROOTFS_EXTRA_SPACE", str(image_extra_size)])

    def set_rootfs_size(self, image_rootfs_size):
        self.runCommand(["setVariable", "IMAGE_ROOTFS_SIZE", str(image_rootfs_size)])

    def set_incompatible_license(self, incompat_license):
        self.runCommand(["setVariable", "INCOMPATIBLE_LICENSE_HOB", incompat_license])

    def set_extra_config(self, extra_setting):
        for key in extra_setting.keys():
            value = extra_setting[key]
            self.runCommand(["setVariable", key, value])

    def set_config_filter(self, config_filter):
        self.runCommand(["setConfFilter", config_filter])

    def set_http_proxy(self, http_proxy):
        self.runCommand(["setVariable", "http_proxy", http_proxy])

    def set_https_proxy(self, https_proxy):
        self.runCommand(["setVariable", "https_proxy", https_proxy])

    def set_ftp_proxy(self, ftp_proxy):
        self.runCommand(["setVariable", "ftp_proxy", ftp_proxy])

    def set_all_proxy(self, all_proxy):
        self.runCommand(["setVariable", "all_proxy", all_proxy])

    def set_git_proxy(self, host, port):
        self.runCommand(["setVariable", "GIT_PROXY_HOST", host])
        self.runCommand(["setVariable", "GIT_PROXY_PORT", port])

    def set_cvs_proxy(self, host, port):
        self.runCommand(["setVariable", "CVS_PROXY_HOST", host])
        self.runCommand(["setVariable", "CVS_PROXY_PORT", port])

    def request_package_info(self):
        self.commands_async.append(self.SUB_GENERATE_PKGINFO)
        self.run_next_command(self.POPULATE_PACKAGEINFO)

    def trigger_sanity_check(self):
        self.commands_async.append(self.SUB_SANITY_CHECK)
        self.run_next_command(self.SANITY_CHECK)

    def generate_configuration(self):
        self.commands_async.append(self.SUB_PARSE_CONFIG)
        self.commands_async.append(self.SUB_PATH_LAYERS)
        self.commands_async.append(self.SUB_FILES_DISTRO)
        self.commands_async.append(self.SUB_FILES_MACH)
        self.commands_async.append(self.SUB_FILES_SDKMACH)
        self.commands_async.append(self.SUB_MATCH_CLASS)
        self.run_next_command(self.GENERATE_CONFIGURATION)

    def generate_recipes(self):
        self.commands_async.append(self.SUB_PARSE_CONFIG)
        self.commands_async.append(self.SUB_GNERATE_TGTS)
        self.run_next_command(self.GENERATE_RECIPES)
                 
    def generate_packages(self, tgts, default_task="build"):
        targets = []
        targets.extend(tgts)
        self.recipe_queue = targets
        self.default_task = default_task
        self.commands_async.append(self.SUB_PARSE_CONFIG)
        self.commands_async.append(self.SUB_BUILD_RECIPES)
        self.run_next_command(self.GENERATE_PACKAGES)

    def generate_image(self, image, toolchain, image_packages=[], toolchain_packages=[], default_task="build"):
        self.image = image
        self.toolchain = toolchain
        self.package_queue = image_packages
        self.toolchain_packages = toolchain_packages
        self.default_task = default_task
        self.commands_async.append(self.SUB_PARSE_CONFIG)
        self.commands_async.append(self.SUB_BUILD_IMAGE)
        self.run_next_command(self.GENERATE_IMAGE)

    def build_succeeded_async(self):
        self.building = False

    def build_failed_async(self):
        self.initcmd = None
        self.commands_async = []
        self.building = False

    def cancel_parse(self):
        self.runCommand(["stateStop"])

    def cancel_build(self, force=False):
        if force:
            # Force the cooker to stop as quickly as possible
            self.runCommand(["stateStop"])
        else:
            # Wait for tasks to complete before shutting down, this helps
            # leave the workdir in a usable state
            self.runCommand(["stateShutdown"])

    def reset_build(self):
        self.build.reset()

    def _remove_redundant(self, string):
        ret = []
        for i in string.split():
            if i not in ret:
                ret.append(i)
        return " ".join(ret)

    def get_parameters(self):
        # retrieve the parameters from bitbake
        params = {}
        params["core_base"] = self.runCommand(["getVariable", "COREBASE"]) or ""
        hob_layer = params["core_base"] + "/meta-hob"
        params["layer"] = self.runCommand(["getVariable", "BBLAYERS"]) or ""
        if hob_layer not in params["layer"].split():
            params["layer"] += (" " + hob_layer)
        params["dldir"] = self.runCommand(["getVariable", "DL_DIR"]) or ""
        params["machine"] = self.runCommand(["getVariable", "MACHINE"]) or ""
        params["distro"] = self.runCommand(["getVariable", "DISTRO"]) or "defaultsetup"
        params["pclass"] = self.runCommand(["getVariable", "PACKAGE_CLASSES"]) or ""
        params["sstatedir"] = self.runCommand(["getVariable", "SSTATE_DIR"]) or ""
        params["sstatemirror"] = self.runCommand(["getVariable", "SSTATE_MIRROR"]) or ""

        num_threads = self.runCommand(["getCpuCount"])
        if not num_threads:
            num_threads = 1
            max_threads = 65536
        else:
            try:
                num_threads = int(num_threads)
                max_threads = 16 * num_threads
            except:
                num_threads = 1
                max_threads = 65536
        params["max_threads"] = max_threads

        bbthread = self.runCommand(["getVariable", "BB_NUMBER_THREADS"])
        if not bbthread:
            bbthread = num_threads
        else:
            try:
                bbthread = int(bbthread)
            except:
                bbthread = num_threads
        params["bbthread"] = bbthread

        pmake = self.runCommand(["getVariable", "PARALLEL_MAKE"])
        if not pmake:
            pmake = num_threads
        elif isinstance(pmake, int):
            pass
        else:
            try:
                pmake = int(pmake.lstrip("-j "))
            except:
                pmake = num_threads
        params["pmake"] = "-j %s" % pmake

        params["image_addr"] = self.runCommand(["getVariable", "DEPLOY_DIR_IMAGE"]) or ""

        image_extra_size = self.runCommand(["getVariable", "IMAGE_ROOTFS_EXTRA_SPACE"])
        if not image_extra_size:
            image_extra_size = 0
        else:
            try:
                image_extra_size = int(image_extra_size)
            except:
                image_extra_size = 0
        params["image_extra_size"] = image_extra_size

        image_rootfs_size = self.runCommand(["getVariable", "IMAGE_ROOTFS_SIZE"])
        if not image_rootfs_size:
            image_rootfs_size = 0
        else:
            try:
                image_rootfs_size = int(image_rootfs_size)
            except:
                image_rootfs_size = 0
        params["image_rootfs_size"] = image_rootfs_size

        image_overhead_factor = self.runCommand(["getVariable", "IMAGE_OVERHEAD_FACTOR"])
        if not image_overhead_factor:
            image_overhead_factor = 1
        else:
            try:
                image_overhead_factor = float(image_overhead_factor)
            except:
                image_overhead_factor = 1
        params['image_overhead_factor'] = image_overhead_factor

        params["incompat_license"] = self._remove_redundant(self.runCommand(["getVariable", "INCOMPATIBLE_LICENSE"]) or "")
        params["sdk_machine"] = self.runCommand(["getVariable", "SDKMACHINE"]) or self.runCommand(["getVariable", "SDK_ARCH"]) or ""

        params["image_fstypes"] = self._remove_redundant(self.runCommand(["getVariable", "IMAGE_FSTYPES"]) or "")

        params["image_types"] = self._remove_redundant(self.runCommand(["getVariable", "IMAGE_TYPES"]) or "")

        params["conf_version"] = self.runCommand(["getVariable", "CONF_VERSION"]) or ""
        params["lconf_version"] = self.runCommand(["getVariable", "LCONF_VERSION"]) or ""

        params["runnable_image_types"] = self._remove_redundant(self.runCommand(["getVariable", "RUNNABLE_IMAGE_TYPES"]) or "")
        params["runnable_machine_patterns"] = self._remove_redundant(self.runCommand(["getVariable", "RUNNABLE_MACHINE_PATTERNS"]) or "")
        params["deployable_image_types"] = self._remove_redundant(self.runCommand(["getVariable", "DEPLOYABLE_IMAGE_TYPES"]) or "")
        params["tmpdir"] = self.runCommand(["getVariable", "TMPDIR"]) or ""
        params["distro_version"] = self.runCommand(["getVariable", "DISTRO_VERSION"]) or ""
        params["target_os"] = self.runCommand(["getVariable", "TARGET_OS"]) or ""
        params["target_arch"] = self.runCommand(["getVariable", "TARGET_ARCH"]) or ""
        params["tune_pkgarch"] = self.runCommand(["getVariable", "TUNE_PKGARCH"])  or ""
        params["bb_version"] = self.runCommand(["getVariable", "BB_MIN_VERSION"]) or ""

        params["default_task"] = self.runCommand(["getVariable", "BB_DEFAULT_TASK"]) or "build"

        params["git_proxy_host"] = self.runCommand(["getVariable", "GIT_PROXY_HOST"]) or ""
        params["git_proxy_port"] = self.runCommand(["getVariable", "GIT_PROXY_PORT"]) or ""

        params["http_proxy"] = self.runCommand(["getVariable", "http_proxy"]) or ""
        params["ftp_proxy"] = self.runCommand(["getVariable", "ftp_proxy"]) or ""
        params["https_proxy"] = self.runCommand(["getVariable", "https_proxy"]) or ""
        params["all_proxy"] = self.runCommand(["getVariable", "all_proxy"]) or ""

        params["cvs_proxy_host"] = self.runCommand(["getVariable", "CVS_PROXY_HOST"]) or ""
        params["cvs_proxy_port"] = self.runCommand(["getVariable", "CVS_PROXY_PORT"]) or ""

        return params
