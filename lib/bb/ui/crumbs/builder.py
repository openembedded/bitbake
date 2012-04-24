#!/usr/bin/env python
#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2011-2012   Intel Corporation
#
# Authored by Joshua Lock <josh@linux.intel.com>
# Authored by Dongxiao Xu <dongxiao.xu@intel.com>
# Authored by Shane Wang <shane.wang@intel.com>
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
import copy
import os
import subprocess
import shlex
from bb.ui.crumbs.template import TemplateMgr
from bb.ui.crumbs.imageconfigurationpage import ImageConfigurationPage
from bb.ui.crumbs.recipeselectionpage import RecipeSelectionPage
from bb.ui.crumbs.packageselectionpage import PackageSelectionPage
from bb.ui.crumbs.builddetailspage import BuildDetailsPage
from bb.ui.crumbs.imagedetailspage import ImageDetailsPage
from bb.ui.crumbs.hobwidget import hwc, HobButton, HobAltButton, hcc
from bb.ui.crumbs.hig import CrumbsMessageDialog, ImageSelectionDialog, \
                             AdvancedSettingDialog, LayerSelectionDialog, \
                             DeployImageDialog
from bb.ui.crumbs.persistenttooltip import PersistentTooltip
import bb.ui.crumbs.utils

class Configuration:
    '''Represents the data structure of configuration.'''

    def __init__(self):
        self.curr_mach = ""
        # settings
        self.curr_distro = ""
        self.dldir = self.sstatedir = self.sstatemirror = ""
        self.pmake = self.bbthread = 0
        self.curr_package_format = ""
        self.image_rootfs_size = self.image_extra_size = 0
        self.image_overhead_factor = 1
        self.incompat_license = ""
        self.curr_sdk_machine = ""
        self.conf_version = self.lconf_version = ""
        self.extra_setting = {}
        self.toolchain_build = False
        self.image_fstypes = ""
        # bblayers.conf
        self.layers = []
        # image/recipes/packages
        self.clear_selection()

        self.user_selected_packages = []

        self.default_task = "build"

        # proxy settings
        self.all_proxy = self.http_proxy = self.ftp_proxy = self.https_proxy = ""
        self.git_proxy_host = self.git_proxy_port = ""
        self.cvs_proxy_host = self.cvs_proxy_port = ""

    def clear_selection(self):
        self.selected_image = None
        self.selected_recipes = []
        self.selected_packages = []

    def update(self, params):
        # settings
        self.curr_distro = params["distro"]
        self.dldir = params["dldir"]
        self.sstatedir = params["sstatedir"]
        self.sstatemirror = params["sstatemirror"]
        self.pmake = int(params["pmake"].split()[1])
        self.bbthread = params["bbthread"]
        self.curr_package_format = " ".join(params["pclass"].split("package_")).strip()
        self.image_rootfs_size = params["image_rootfs_size"]
        self.image_extra_size = params["image_extra_size"]
        self.image_overhead_factor = params['image_overhead_factor']
        self.incompat_license = params["incompat_license"]
        self.curr_sdk_machine = params["sdk_machine"]
        self.conf_version = params["conf_version"]
        self.lconf_version = params["lconf_version"]
        self.image_fstypes = params["image_fstypes"]
        # self.extra_setting/self.toolchain_build
        # bblayers.conf
        self.layers = params["layer"].split()
        self.default_task = params["default_task"]

        # proxy settings
        self.all_proxy = params["all_proxy"]
        self.http_proxy = params["http_proxy"]
        self.ftp_proxy = params["ftp_proxy"]
        self.https_proxy = params["https_proxy"]
        self.git_proxy_host = params["git_proxy_host"]
        self.git_proxy_port = params["git_proxy_port"]
        self.cvs_proxy_host = params["cvs_proxy_host"]
        self.cvs_proxy_port = params["cvs_proxy_port"]

    def load(self, template):
        self.curr_mach = template.getVar("MACHINE")
        self.curr_package_format = " ".join(template.getVar("PACKAGE_CLASSES").split("package_")).strip()
        self.curr_distro = template.getVar("DISTRO")
        self.dldir = template.getVar("DL_DIR")
        self.sstatedir = template.getVar("SSTATE_DIR")
        self.sstatemirror = template.getVar("SSTATE_MIRROR")
        try:
            self.pmake = int(template.getVar("PARALLEL_MAKE").split()[1])
        except:
            pass
        try:
            self.bbthread = int(template.getVar("BB_NUMBER_THREADS"))
        except:
            pass
        try:
            self.image_rootfs_size = int(template.getVar("IMAGE_ROOTFS_SIZE"))
        except:
            pass
        try:
            self.image_extra_size = int(template.getVar("IMAGE_EXTRA_SPACE"))
        except:
            pass
        # image_overhead_factor is read-only.
        self.incompat_license = template.getVar("INCOMPATIBLE_LICENSE")
        self.curr_sdk_machine = template.getVar("SDKMACHINE")
        self.conf_version = template.getVar("CONF_VERSION")
        self.lconf_version = template.getVar("LCONF_VERSION")
        self.extra_setting = eval(template.getVar("EXTRA_SETTING"))
        self.toolchain_build = eval(template.getVar("TOOLCHAIN_BUILD"))
        self.image_fstypes = template.getVar("IMAGE_FSTYPES")
        # bblayers.conf
        self.layers = template.getVar("BBLAYERS").split()
        # image/recipes/packages
        self.selected_image = template.getVar("__SELECTED_IMAGE__")
        self.selected_recipes = template.getVar("DEPENDS").split()
        self.selected_packages = template.getVar("IMAGE_INSTALL").split()
        # proxy
        self.all_proxy = template.getVar("all_proxy")
        self.http_proxy = template.getVar("http_proxy")
        self.ftp_proxy = template.getVar("ftp_proxy")
        self.https_proxy = template.getVar("https_proxy")
        self.git_proxy_host = template.getVar("GIT_PROXY_HOST")
        self.git_proxy_port = template.getVar("GIT_PROXY_PORT")
        self.cvs_proxy_host = template.getVar("CVS_PROXY_HOST")
        self.cvs_proxy_port = template.getVar("CVS_PROXY_PORT")

    def save(self, template, defaults=False):
        # bblayers.conf
        template.setVar("BBLAYERS", " ".join(self.layers))
        # local.conf
        if not defaults:
            template.setVar("MACHINE", self.curr_mach)
        template.setVar("DISTRO", self.curr_distro)
        template.setVar("DL_DIR", self.dldir)
        template.setVar("SSTATE_DIR", self.sstatedir)
        template.setVar("SSTATE_MIRROR", self.sstatemirror)
        template.setVar("PARALLEL_MAKE", "-j %s" % self.pmake)
        template.setVar("BB_NUMBER_THREADS", self.bbthread)
        template.setVar("PACKAGE_CLASSES", " ".join(["package_" + i for i in self.curr_package_format.split()]))
        template.setVar("IMAGE_ROOTFS_SIZE", self.image_rootfs_size)
        template.setVar("IMAGE_EXTRA_SPACE", self.image_extra_size)
        template.setVar("INCOMPATIBLE_LICENSE", self.incompat_license)
        template.setVar("SDKMACHINE", self.curr_sdk_machine)
        template.setVar("CONF_VERSION", self.conf_version)
        template.setVar("LCONF_VERSION", self.lconf_version)
        template.setVar("EXTRA_SETTING", self.extra_setting)
        template.setVar("TOOLCHAIN_BUILD", self.toolchain_build)
        template.setVar("IMAGE_FSTYPES", self.image_fstypes)
        if not defaults:
            # image/recipes/packages
            template.setVar("__SELECTED_IMAGE__", self.selected_image)
            template.setVar("DEPENDS", self.selected_recipes)
            template.setVar("IMAGE_INSTALL", self.user_selected_packages)
        # proxy
        template.setVar("all_proxy", self.all_proxy)
        template.setVar("http_proxy", self.http_proxy)
        template.setVar("ftp_proxy", self.ftp_proxy)
        template.setVar("https_proxy", self.https_proxy)
        template.setVar("GIT_PROXY_HOST", self.git_proxy_host)
        template.setVar("GIT_PROXY_PORT", self.git_proxy_port)
        template.setVar("CVS_PROXY_HOST", self.cvs_proxy_host)
        template.setVar("CVS_PROXY_PORT", self.cvs_proxy_port)

class Parameters:
    '''Represents other variables like available machines, etc.'''

    def __init__(self):
        # Variables
        self.max_threads = 65535
        self.core_base = ""
        self.image_addr = ""
        self.image_types = []
        self.runnable_image_types = []
        self.runnable_machine_patterns = []
        self.deployable_image_types = []
        self.tmpdir = ""

        self.all_machines = []
        self.all_package_formats = []
        self.all_distros = []
        self.all_sdk_machines = []
        self.all_layers = []
        self.image_names = []
        self.enable_proxy = False

        # for build log to show
        self.bb_version = ""
        self.target_arch = ""
        self.target_os = ""
        self.distro_version = ""
        self.tune_pkgarch = ""

    def update(self, params):
        self.max_threads = params["max_threads"]
        self.core_base = params["core_base"]
        self.image_addr = params["image_addr"]
        self.image_types = params["image_types"].split()
        self.runnable_image_types = params["runnable_image_types"].split()
        self.runnable_machine_patterns = params["runnable_machine_patterns"].split()
        self.deployable_image_types = params["deployable_image_types"].split()
        self.tmpdir = params["tmpdir"]
        # for build log to show
        self.bb_version = params["bb_version"]
        self.target_arch = params["target_arch"]
        self.target_os = params["target_os"]
        self.distro_version = params["distro_version"]
        self.tune_pkgarch = params["tune_pkgarch"]

def hob_conf_filter(fn, data):
    if fn.endswith("/local.conf"):
        distro = data.getVar("DISTRO_HOB")
        if distro:
            if distro != "defaultsetup":
                data.setVar("DISTRO", distro)
            else:
                data.delVar("DISTRO")

        keys = ["MACHINE_HOB", "SDKMACHINE_HOB", "PACKAGE_CLASSES_HOB", \
                "BB_NUMBER_THREADS_HOB", "PARALLEL_MAKE_HOB", "DL_DIR_HOB", \
                "SSTATE_DIR_HOB", "SSTATE_MIRROR_HOB", "INCOMPATIBLE_LICENSE_HOB"]
        for key in keys:
            var_hob = data.getVar(key)
            if var_hob:
                data.setVar(key.split("_HOB")[0], var_hob)
        return

    if fn.endswith("/bblayers.conf"):
        layers = data.getVar("BBLAYERS_HOB")
        if layers:
            data.setVar("BBLAYERS", layers)
        return

class Builder(gtk.Window):

    (MACHINE_SELECTION,
     RCPPKGINFO_POPULATING,
     RCPPKGINFO_POPULATED,
     BASEIMG_SELECTED,
     RECIPE_SELECTION,
     PACKAGE_GENERATING,
     PACKAGE_GENERATED,
     PACKAGE_SELECTION,
     FAST_IMAGE_GENERATING,
     IMAGE_GENERATING,
     IMAGE_GENERATED,
     MY_IMAGE_OPENED,
     BACK,
     END_NOOP) = range(14)

    (IMAGE_CONFIGURATION,
     RECIPE_DETAILS,
     BUILD_DETAILS,
     PACKAGE_DETAILS,
     IMAGE_DETAILS,
     END_TAB) = range(6)

    __step2page__ = {
        MACHINE_SELECTION     : IMAGE_CONFIGURATION,
        RCPPKGINFO_POPULATING : IMAGE_CONFIGURATION,
        RCPPKGINFO_POPULATED  : IMAGE_CONFIGURATION,
        BASEIMG_SELECTED      : IMAGE_CONFIGURATION,
        RECIPE_SELECTION      : RECIPE_DETAILS,
        PACKAGE_GENERATING    : BUILD_DETAILS,
        PACKAGE_GENERATED     : PACKAGE_DETAILS,
        PACKAGE_SELECTION     : PACKAGE_DETAILS,
        FAST_IMAGE_GENERATING : BUILD_DETAILS,
        IMAGE_GENERATING      : BUILD_DETAILS,
        IMAGE_GENERATED       : IMAGE_DETAILS,
        MY_IMAGE_OPENED       : IMAGE_DETAILS,
        END_NOOP              : None,
    }

    def __init__(self, hobHandler, recipe_model, package_model):
        super(Builder, self).__init__()

        self.hob_image = "hob-image"
        self.hob_toolchain = "hob-toolchain"

        # handler
        self.handler = hobHandler

        self.template = None

        # configuration and parameters
        self.configuration = Configuration()
        self.parameters = Parameters()

        # build step
        self.current_step = None
        self.previous_step = None

        self.stopping = False

        # recipe model and package model
        self.recipe_model = recipe_model
        self.package_model = package_model

        # Indicate whether user has customized the image
        self.customized = False

        # Indicate whether the UI is working
        self.sensitive = True

        # create visual elements
        self.create_visual_elements()

        # connect the signals to functions
        self.connect("delete-event", self.destroy_window_cb)
        self.recipe_model.connect ("recipe-selection-changed",  self.recipelist_changed_cb)
        self.package_model.connect("package-selection-changed", self.packagelist_changed_cb)
        self.handler.connect("config-updated",           self.handler_config_updated_cb)
        self.handler.connect("package-formats-updated",  self.handler_package_formats_updated_cb)
        self.handler.connect("parsing-started",          self.handler_parsing_started_cb)
        self.handler.connect("parsing",                  self.handler_parsing_cb)
        self.handler.connect("parsing-completed",        self.handler_parsing_completed_cb)
        self.handler.build.connect("build-started",      self.handler_build_started_cb)
        self.handler.build.connect("build-succeeded",    self.handler_build_succeeded_cb)
        self.handler.build.connect("build-failed",       self.handler_build_failed_cb)
        self.handler.build.connect("task-started",       self.handler_task_started_cb)
        self.handler.build.connect("log-error",          self.handler_build_failure_cb)
        self.handler.build.connect("no-provider",        self.handler_no_provider_cb)
        self.handler.connect("generating-data",          self.handler_generating_data_cb)
        self.handler.connect("data-generated",           self.handler_data_generated_cb)
        self.handler.connect("command-succeeded",        self.handler_command_succeeded_cb)
        self.handler.connect("command-failed",           self.handler_command_failed_cb)

        self.handler.set_config_filter(hob_conf_filter)

        self.initiate_new_build_async()

    def create_visual_elements(self):
        self.set_title("Hob")
        self.set_icon_name("applications-development")
        self.set_resizable(True)
        window_width = self.get_screen().get_width()
        window_height = self.get_screen().get_height()
        if window_width >= hwc.MAIN_WIN_WIDTH:
            window_width = hwc.MAIN_WIN_WIDTH
            window_height = hwc.MAIN_WIN_HEIGHT
        self.set_size_request(window_width, window_height)

        self.vbox = gtk.VBox(False, 0)
        self.vbox.set_border_width(0)
        self.add(self.vbox)

        # create pages
        self.image_configuration_page = ImageConfigurationPage(self)
        self.recipe_details_page      = RecipeSelectionPage(self)
        self.build_details_page       = BuildDetailsPage(self)
        self.package_details_page     = PackageSelectionPage(self)
        self.image_details_page       = ImageDetailsPage(self)

        self.nb = gtk.Notebook()
        self.nb.set_show_tabs(False)
        self.nb.insert_page(self.image_configuration_page, None, self.IMAGE_CONFIGURATION)
        self.nb.insert_page(self.recipe_details_page,      None, self.RECIPE_DETAILS)
        self.nb.insert_page(self.build_details_page,       None, self.BUILD_DETAILS)
        self.nb.insert_page(self.package_details_page,     None, self.PACKAGE_DETAILS)
        self.nb.insert_page(self.image_details_page,       None, self.IMAGE_DETAILS)
        self.vbox.pack_start(self.nb, expand=True, fill=True)

        self.show_all()
        self.nb.set_current_page(0)

    def initiate_new_build_async(self):
        self.switch_page(self.MACHINE_SELECTION)
        if self.load_template(TemplateMgr.convert_to_template_pathfilename("default", ".hob/")) == None:
            self.handler.init_cooker()
            self.handler.set_extra_inherit("image_types")
            self.handler.generate_configuration()

    def update_config_async(self):
        self.switch_page(self.MACHINE_SELECTION)
        self.set_user_config()
        self.handler.generate_configuration()

    def sanity_check(self):
        self.handler.trigger_sanity_check()

    def populate_recipe_package_info_async(self):
        self.switch_page(self.RCPPKGINFO_POPULATING)
        # Parse recipes
        self.set_user_config()
        self.handler.generate_recipes()

    def generate_packages_async(self):
        self.switch_page(self.PACKAGE_GENERATING)
        # Build packages
        _, all_recipes = self.recipe_model.get_selected_recipes()
        self.set_user_config()
        self.handler.reset_build()
        self.handler.generate_packages(all_recipes, self.configuration.default_task)

    def fast_generate_image_async(self):
        self.switch_page(self.FAST_IMAGE_GENERATING)
        # Build packages
        _, all_recipes = self.recipe_model.get_selected_recipes()
        self.set_user_config()
        self.handler.reset_build()
        self.handler.generate_packages(all_recipes, self.configuration.default_task)

    def generate_image_async(self):
        self.switch_page(self.IMAGE_GENERATING)
        self.handler.reset_build()
        # Build image
        self.set_user_config()
        toolchain_packages = []
        if self.configuration.toolchain_build:
            toolchain_packages = self.package_model.get_selected_packages_toolchain()
        if self.configuration.selected_image == self.recipe_model.__dummy_image__:
            packages = self.package_model.get_selected_packages()
            image = self.hob_image
        else:
            packages = []
            image = self.configuration.selected_image
        self.handler.generate_image(image,
                                    self.hob_toolchain,
                                    packages,
                                    toolchain_packages,
                                    self.configuration.default_task)

    def get_parameters_sync(self):
        return self.handler.get_parameters()

    def request_package_info_async(self):
        self.handler.request_package_info()

    def cancel_build_sync(self, force=False):
        self.handler.cancel_build(force)

    def cancel_parse_sync(self):
        self.handler.cancel_parse()

    def load_template(self, path):
        if not os.path.isfile(path):
            return None

        self.template = TemplateMgr()
        try:
            self.template.load(path)
            self.configuration.load(self.template)
        except Exception as e:
            self.show_error_dialog("Hob Exception - %s" % (str(e)))
            self.reset()
        finally:
            self.template.destroy()
            self.template = None

        for layer in self.configuration.layers:
            if not os.path.exists(layer+'/conf/layer.conf'):
                return False

        self.save_defaults() # remember layers and settings
        self.update_config_async()
        return True

    def save_template(self, path, defaults=False):
        if path.rfind("/") == -1:
            filename = "default"
            path = "."
        else:
            filename = path[path.rfind("/") + 1:len(path)]
            path = path[0:path.rfind("/")]

        self.template = TemplateMgr()
        try:
            self.template.open(filename, path)
            self.configuration.save(self.template, defaults)

            self.template.save()
        except Exception as e:
            self.show_error_dialog("Hob Exception - %s" % (str(e)))
            self.reset()
        finally:
            self.template.destroy()
            self.template = None

    def save_defaults(self):
        if not os.path.exists(".hob/"):
            os.mkdir(".hob/")
        self.save_template(".hob/default", True)

    def switch_page(self, next_step):
        # Main Workflow (Business Logic)
        self.nb.set_current_page(self.__step2page__[next_step])

        if next_step == self.MACHINE_SELECTION: # init step
            self.image_configuration_page.show_machine()

        elif next_step == self.RCPPKGINFO_POPULATING:
            # MACHINE CHANGED action or SETTINGS CHANGED
            # show the progress bar
            self.image_configuration_page.show_info_populating()

        elif next_step == self.RCPPKGINFO_POPULATED:
            self.image_configuration_page.show_info_populated()

        elif next_step == self.BASEIMG_SELECTED:
            self.image_configuration_page.show_baseimg_selected()

        elif next_step == self.RECIPE_SELECTION:
            pass

        elif next_step == self.PACKAGE_SELECTION:
            pass

        elif next_step == self.PACKAGE_GENERATING or next_step == self.FAST_IMAGE_GENERATING:
            # both PACKAGE_GENEATING and FAST_IMAGE_GENERATING share the same page
            self.build_details_page.show_page(next_step)

        elif next_step == self.PACKAGE_GENERATED:
            pass

        elif next_step == self.IMAGE_GENERATING:
            # after packages are generated, selected_packages need to
            # be updated in package_model per selected_image in recipe_model
            self.build_details_page.show_page(next_step)

        elif next_step == self.IMAGE_GENERATED:
            self.image_details_page.show_page(next_step)

        elif next_step == self.MY_IMAGE_OPENED:
            self.image_details_page.show_page(next_step)

        self.previous_step = self.current_step
        self.current_step = next_step

    def set_user_config(self):
        self.handler.init_cooker()
        # set bb layers
        self.handler.set_bblayers(self.configuration.layers)
        # set local configuration
        self.handler.set_machine(self.configuration.curr_mach)
        self.handler.set_package_format(self.configuration.curr_package_format)
        self.handler.set_distro(self.configuration.curr_distro)
        self.handler.set_dl_dir(self.configuration.dldir)
        self.handler.set_sstate_dir(self.configuration.sstatedir)
        self.handler.set_sstate_mirror(self.configuration.sstatemirror)
        self.handler.set_pmake(self.configuration.pmake)
        self.handler.set_bbthreads(self.configuration.bbthread)
        self.handler.set_rootfs_size(self.configuration.image_rootfs_size)
        self.handler.set_extra_size(self.configuration.image_extra_size)
        self.handler.set_incompatible_license(self.configuration.incompat_license)
        self.handler.set_sdk_machine(self.configuration.curr_sdk_machine)
        self.handler.set_image_fstypes(self.configuration.image_fstypes)
        self.handler.set_extra_config(self.configuration.extra_setting)
        self.handler.set_extra_inherit("packageinfo")
        self.handler.set_extra_inherit("image_types")
        # set proxies
        if self.parameters.enable_proxy:
            self.handler.set_http_proxy(self.configuration.http_proxy)
            self.handler.set_https_proxy(self.configuration.https_proxy)
            self.handler.set_ftp_proxy(self.configuration.ftp_proxy)
            self.handler.set_all_proxy(self.configuration.all_proxy)
            self.handler.set_git_proxy(self.configuration.git_proxy_host, self.configuration.git_proxy_port)
            self.handler.set_cvs_proxy(self.configuration.cvs_proxy_host, self.configuration.cvs_proxy_port)

    def update_recipe_model(self, selected_image, selected_recipes):
        self.recipe_model.set_selected_image(selected_image)
        self.recipe_model.set_selected_recipes(selected_recipes)

    def update_package_model(self, selected_packages):
        left = self.package_model.set_selected_packages(selected_packages)
        self.configuration.selected_packages += left

    def update_configuration_parameters(self, params):
        if params:
            self.configuration.update(params)
            self.parameters.update(params)

    def reset(self):
        self.configuration.curr_mach = ""
        self.configuration.clear_selection()
        self.image_configuration_page.switch_machine_combo()
        self.switch_page(self.MACHINE_SELECTION)

    # Callback Functions
    def handler_config_updated_cb(self, handler, which, values):
        if which == "distro":
            self.parameters.all_distros = values
        elif which == "machine":
            self.parameters.all_machines = values
            self.image_configuration_page.update_machine_combo()
        elif which == "machine-sdk":
            self.parameters.all_sdk_machines = values

    def handler_package_formats_updated_cb(self, handler, formats):
        self.parameters.all_package_formats = formats

    def handler_command_succeeded_cb(self, handler, initcmd):
        if initcmd == self.handler.GENERATE_CONFIGURATION:
            self.update_configuration_parameters(self.get_parameters_sync())
            self.sanity_check()
        elif initcmd == self.handler.SANITY_CHECK:
            self.image_configuration_page.switch_machine_combo()
        elif initcmd in [self.handler.GENERATE_RECIPES,
                         self.handler.GENERATE_PACKAGES,
                         self.handler.GENERATE_IMAGE]:
            self.update_configuration_parameters(self.get_parameters_sync())
            self.request_package_info_async()
        elif initcmd == self.handler.POPULATE_PACKAGEINFO:
            if self.current_step == self.RCPPKGINFO_POPULATING:
                self.switch_page(self.RCPPKGINFO_POPULATED)
                self.rcppkglist_populated()
                return

            self.rcppkglist_populated()
            if self.current_step == self.FAST_IMAGE_GENERATING:
                self.generate_image_async()

    def show_error_dialog(self, msg):
        lbl = "<b>Error</b>\n"
        lbl = lbl + "%s\n\n" % msg
        dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_ERROR)
        button = dialog.add_button("Close", gtk.RESPONSE_OK)
        HobButton.style_button(button)
        response = dialog.run()
        dialog.destroy()

    def handler_command_failed_cb(self, handler, msg):
        if msg:
            msg = msg.replace("your local.conf", "Settings")
            self.show_error_dialog(msg)
        self.reset()

    def window_sensitive(self, sensitive):
        self.image_configuration_page.machine_combo.set_sensitive(sensitive)
        self.image_configuration_page.image_combo.set_sensitive(sensitive)
        self.image_configuration_page.layer_button.set_sensitive(sensitive)
        self.image_configuration_page.layer_info_icon.set_sensitive(sensitive)
        self.image_configuration_page.toolbar.set_sensitive(sensitive)
        self.image_configuration_page.view_recipes_button.set_sensitive(sensitive)
        self.image_configuration_page.view_packages_button.set_sensitive(sensitive)
        self.image_configuration_page.config_build_button.set_sensitive(sensitive)

        self.recipe_details_page.set_sensitive(sensitive)
        self.package_details_page.set_sensitive(sensitive)
        self.build_details_page.set_sensitive(sensitive)
        self.image_details_page.set_sensitive(sensitive)

        if sensitive:
            self.get_root_window().set_cursor(gtk.gdk.Cursor(gtk.gdk.LEFT_PTR))
        else:
            self.get_root_window().set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
        self.sensitive = sensitive


    def handler_generating_data_cb(self, handler):
        self.window_sensitive(False)

    def handler_data_generated_cb(self, handler):
        self.window_sensitive(True)

    def rcppkglist_populated(self):
        selected_image = self.configuration.selected_image
        selected_recipes = self.configuration.selected_recipes[:]
        selected_packages = self.configuration.selected_packages[:]

        self.image_configuration_page.update_image_combo(self.recipe_model, selected_image)
        self.image_configuration_page.update_image_desc(selected_image)
        self.update_recipe_model(selected_image, selected_recipes)
        self.update_package_model(selected_packages)

    def recipelist_changed_cb(self, recipe_model):
        self.recipe_details_page.refresh_selection()

    def packagelist_changed_cb(self, package_model):
        self.package_details_page.refresh_selection()

    def handler_parsing_started_cb(self, handler, message):
        if self.current_step != self.RCPPKGINFO_POPULATING:
            return

        fraction = 0
        if message["eventname"] == "TreeDataPreparationStarted":
            fraction = 0.6 + fraction
            self.image_configuration_page.stop_button.set_sensitive(False)
        else:
            self.image_configuration_page.stop_button.set_sensitive(True)

        self.image_configuration_page.update_progress_bar(message["title"], fraction)

    def handler_parsing_cb(self, handler, message):
        if self.current_step != self.RCPPKGINFO_POPULATING:
            return

        fraction = message["current"] * 1.0/message["total"]
        if message["eventname"] == "TreeDataPreparationProgress":
            fraction = 0.6 + 0.4 * fraction
        else:
            fraction = 0.6 * fraction
        self.image_configuration_page.update_progress_bar(message["title"], fraction)

    def handler_parsing_completed_cb(self, handler, message):
        if self.current_step != self.RCPPKGINFO_POPULATING:
            return

        if message["eventname"] == "TreeDataPreparationCompleted":
            fraction = 1.0
        else:
            fraction = 0.6
        self.image_configuration_page.update_progress_bar(message["title"], fraction)

    def handler_build_started_cb(self, running_build):
        if self.current_step == self.FAST_IMAGE_GENERATING:
            fraction = 0
        elif self.current_step == self.IMAGE_GENERATING:
            if self.previous_step == self.FAST_IMAGE_GENERATING:
                fraction = 0.9
            else:
                fraction = 0
        elif self.current_step == self.PACKAGE_GENERATING:
            fraction = 0
        self.build_details_page.update_progress_bar("Build Started: ", fraction)
        self.build_details_page.show_configurations(self.configuration, self.parameters)

    def build_succeeded(self):
        if self.current_step == self.FAST_IMAGE_GENERATING:
            fraction = 0.9
        elif self.current_step == self.IMAGE_GENERATING:
            fraction = 1.0
            self.parameters.image_names = []
            selected_image = self.recipe_model.get_selected_image()
            if selected_image == self.recipe_model.__dummy_image__:
                linkname = 'hob-image-' + self.configuration.curr_mach
            else:
                linkname = selected_image + '-' + self.configuration.curr_mach
            for image_type in self.parameters.image_types:
                for real_image_type in hcc.SUPPORTED_IMAGE_TYPES[image_type]:
                    linkpath = self.parameters.image_addr + '/' + linkname + '.' + real_image_type
                    if os.path.exists(linkpath):
                        self.parameters.image_names.append(os.readlink(linkpath))
        elif self.current_step == self.PACKAGE_GENERATING:
            fraction = 1.0
        self.build_details_page.update_progress_bar("Build Completed: ", fraction)
        self.handler.build_succeeded_async()
        self.stopping = False

        if self.current_step == self.PACKAGE_GENERATING:
            self.switch_page(self.PACKAGE_GENERATED)
        elif self.current_step == self.IMAGE_GENERATING:
            self.switch_page(self.IMAGE_GENERATED)

    def build_failed(self):
        if self.stopping:
            status = "stop"
            message = "Build stopped: "
            fraction = self.build_details_page.progress_bar.get_fraction()
        else:
            if self.current_step == self.FAST_IMAGE_GENERATING:
                fraction = 0.9
            elif self.current_step == self.IMAGE_GENERATING:
                fraction = 1.0
            elif self.current_step == self.PACKAGE_GENERATING:
                fraction = 1.0
            status = "fail"
            message = "Build failed: "
        self.build_details_page.update_progress_bar(message, fraction, status)
        self.build_details_page.show_back_button()
        self.build_details_page.hide_stop_button()
        self.handler.build_failed_async()
        self.stopping = False

    def handler_build_succeeded_cb(self, running_build):
        if not self.stopping:
            self.build_succeeded()
        else:
            self.build_failed()


    def handler_build_failed_cb(self, running_build):
        self.build_failed()

    def handler_no_provider_cb(self, running_build, msg):
        dialog = CrumbsMessageDialog(self, msg, gtk.STOCK_DIALOG_INFO)
        button = dialog.add_button("Close", gtk.RESPONSE_OK)
        HobButton.style_button(button)
        dialog.run()
        dialog.destroy()
        self.build_failed()

    def handler_task_started_cb(self, running_build, message): 
        fraction = message["current"] * 1.0/message["total"]
        title = "Build packages"
        if self.current_step == self.FAST_IMAGE_GENERATING:
            if message["eventname"] == "sceneQueueTaskStarted":
                fraction = 0.27 * fraction
            elif message["eventname"] == "runQueueTaskStarted":
                fraction = 0.27 + 0.63 * fraction
        elif self.current_step == self.IMAGE_GENERATING:
            title = "Build image"
            if self.previous_step == self.FAST_IMAGE_GENERATING:
                if message["eventname"] == "sceneQueueTaskStarted":
                    fraction = 0.27 + 0.63 + 0.03 * fraction
                elif message["eventname"] == "runQueueTaskStarted":
                    fraction = 0.27 + 0.63 + 0.03 + 0.07 * fraction
            else:
                if message["eventname"] == "sceneQueueTaskStarted":
                    fraction = 0.2 * fraction
                elif message["eventname"] == "runQueueTaskStarted":
                    fraction = 0.2 + 0.8 * fraction
        elif self.current_step == self.PACKAGE_GENERATING:
            if message["eventname"] == "sceneQueueTaskStarted":
                fraction = 0.2 * fraction
            elif message["eventname"] == "runQueueTaskStarted":
                fraction = 0.2 + 0.8 * fraction
        self.build_details_page.update_progress_bar(title + ": ", fraction)
        self.build_details_page.update_build_status(message["current"], message["total"], message["task"])

    def handler_build_failure_cb(self, running_build):
        self.build_details_page.show_issues()

    def destroy_window_cb(self, widget, event):
        if not self.sensitive:
            return True
        lbl = "<b>Do you really want to exit the Hob image creator?</b>"
        dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Exit Hob", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        dialog.set_default_response(gtk.RESPONSE_YES)
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            gtk.main_quit()
            return False
        else:
            return True

    def build_packages(self):
        _, all_recipes = self.recipe_model.get_selected_recipes()
        if not all_recipes:
            lbl = "<b>No selections made</b>\nYou have not made any selections"
            lbl = lbl + " so there isn't anything to bake at this time."
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
            button = dialog.add_button("Close", gtk.RESPONSE_OK)
            HobButton.style_button(button)
            dialog.run()
            dialog.destroy()
            return
        self.generate_packages_async()

    def build_image(self):
        selected_packages = self.package_model.get_selected_packages()
        if not selected_packages:      
            lbl = "<b>No selections made</b>\nYou have not made any selections"
            lbl = lbl + " so there isn't anything to bake at this time."
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
            button = dialog.add_button("Close", gtk.RESPONSE_OK)
            HobButton.style_button(button)
            dialog.run()
            dialog.destroy()
            return
        self.generate_image_async()

    def just_bake(self):
        selected_image = self.recipe_model.get_selected_image()
        selected_packages = self.package_model.get_selected_packages() or []

        # If no base image and no selected packages don't build anything
        if not (selected_packages or selected_image != self.recipe_model.__dummy_image__):
            lbl = "<b>No selections made</b>\nYou have not made any selections"
            lbl = lbl + " so there isn't anything to bake at this time."
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
            button = dialog.add_button("Close", gtk.RESPONSE_OK)
            HobButton.style_button(button)
            dialog.run()
            dialog.destroy()
            return

        self.fast_generate_image_async()

    def show_binb_dialog(self, binb):
        markup = "<b>Brought in by:</b>\n%s" % binb
        ptip = PersistentTooltip(markup, self)

        ptip.show()

    def show_layer_selection_dialog(self):
        dialog = LayerSelectionDialog(title = "Layers",
                     layers = copy.deepcopy(self.configuration.layers),
                     all_layers = self.parameters.all_layers,
                     parent = self,
                     flags = gtk.DIALOG_MODAL
                         | gtk.DIALOG_DESTROY_WITH_PARENT
                         | gtk.DIALOG_NO_SEPARATOR)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("OK", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        response = dialog.run()
        if response == gtk.RESPONSE_YES:
            self.configuration.layers = dialog.layers
            self.save_defaults() # remember layers
            # DO refresh layers
            if dialog.layers_changed:
                self.update_config_async()
        dialog.destroy()

    def show_load_template_dialog(self):
        dialog = gtk.FileChooserDialog("Load Template Files", self,
                                       gtk.FILE_CHOOSER_ACTION_OPEN)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Open", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        filter = gtk.FileFilter()
        filter.set_name("Hob Files")
        filter.add_pattern("*.hob")
        dialog.add_filter(filter)

        response = dialog.run()
        path = None
        if response == gtk.RESPONSE_YES:
            path = dialog.get_filename()
        dialog.destroy()
        return response == gtk.RESPONSE_YES, path

    def show_save_template_dialog(self):
        dialog = gtk.FileChooserDialog("Save Template Files", self,
                                       gtk.FILE_CHOOSER_ACTION_SAVE)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Save", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        dialog.set_current_name("hob")
        response = dialog.run()
        if response == gtk.RESPONSE_YES:
            path = dialog.get_filename()
            self.save_template(path)
        dialog.destroy()

    def show_load_my_images_dialog(self):
        dialog = ImageSelectionDialog(self.parameters.image_addr, self.parameters.image_types,
                                      "Open My Images", self,
                                       gtk.FILE_CHOOSER_ACTION_SAVE)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Open", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        response = dialog.run()
        if response == gtk.RESPONSE_YES:
            if not dialog.image_names:
                lbl = "<b>No selections made</b>\nYou have not made any selections"
                crumbs_dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
                button = crumbs_dialog.add_button("Close", gtk.RESPONSE_OK)
                HobButton.style_button(button)
                crumbs_dialog.run()
                crumbs_dialog.destroy()
                dialog.destroy()
                return

            self.parameters.image_addr = dialog.image_folder
            self.parameters.image_names = dialog.image_names[:]
            self.switch_page(self.MY_IMAGE_OPENED)

        dialog.destroy()

    def show_adv_settings_dialog(self):
        dialog = AdvancedSettingDialog(title = "Settings",
            configuration = copy.deepcopy(self.configuration),
            all_image_types = self.parameters.image_types,
            all_package_formats = self.parameters.all_package_formats,
            all_distros = self.parameters.all_distros,
            all_sdk_machines = self.parameters.all_sdk_machines,
            max_threads = self.parameters.max_threads,
            enable_proxy = self.parameters.enable_proxy,
            parent = self,
            flags = gtk.DIALOG_MODAL
                    | gtk.DIALOG_DESTROY_WITH_PARENT
                    | gtk.DIALOG_NO_SEPARATOR)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Save", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        response = dialog.run()
        settings_changed = False
        if response == gtk.RESPONSE_YES:
            self.parameters.enable_proxy = dialog.enable_proxy
            self.configuration = dialog.configuration
            self.save_defaults() # remember settings
            settings_changed = dialog.settings_changed
        dialog.destroy()
        return response == gtk.RESPONSE_YES, settings_changed

    def reparse_post_adv_settings(self):
        if not self.configuration.curr_mach:
            self.update_config_async()
        else:
            self.configuration.clear_selection()
            # DO reparse recipes
            self.populate_recipe_package_info_async()

    def deploy_image(self, image_name):
        if not image_name:
            lbl = "<b>Please select an image to deploy.</b>"
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
            button = dialog.add_button("Close", gtk.RESPONSE_OK)
            HobButton.style_button(button)
            dialog.run()
            dialog.destroy()
            return

        image_path = os.path.join(self.parameters.image_addr, image_name)
        dialog = DeployImageDialog(title = "Usb Image Maker",
            image_path = image_path,
            parent = self,
            flags = gtk.DIALOG_MODAL
                    | gtk.DIALOG_DESTROY_WITH_PARENT
                    | gtk.DIALOG_NO_SEPARATOR)
        button = dialog.add_button("Close", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Make usb image", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        response = dialog.run()
        dialog.destroy()

    def runqemu_image(self, image_name):
        if not image_name:
            lbl = "<b>Please select an image to launch in QEMU.</b>"
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
            button = dialog.add_button("Close", gtk.RESPONSE_OK)
            HobButton.style_button(button)
            dialog.run()
            dialog.destroy()
            return

        dialog = gtk.FileChooserDialog("Load Kernel Files", self,
                                       gtk.FILE_CHOOSER_ACTION_SAVE)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Open", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        filter = gtk.FileFilter()
        filter.set_name("Kernel Files")
        filter.add_pattern("*.bin")
        dialog.add_filter(filter)

        dialog.set_current_folder(self.parameters.image_addr)

        response = dialog.run()
        if response == gtk.RESPONSE_YES:
            kernel_path = dialog.get_filename()
            image_path = os.path.join(self.parameters.image_addr, image_name)
        dialog.destroy()

        if response == gtk.RESPONSE_YES:
            source_env_path = os.path.join(self.parameters.core_base, "oe-init-build-env")
            tmp_path = self.parameters.tmpdir
            cmdline = bb.ui.crumbs.utils.which_terminal()
            if os.path.exists(image_path) and os.path.exists(kernel_path) \
               and os.path.exists(source_env_path) and os.path.exists(tmp_path) \
               and cmdline:
                cmdline += "\' bash -c \"export OE_TMPDIR=" + tmp_path + "; "
                cmdline += "source " + source_env_path + " " + os.getcwd() + "; "
                cmdline += "runqemu " + kernel_path + " " + image_path + "\"\'"
                subprocess.Popen(shlex.split(cmdline))
            else:
                lbl = "<b>Path error</b>\nOne of your paths is wrong,"
                lbl = lbl + " please make sure the following paths exist:\n"
                lbl = lbl + "image path:" + image_path + "\n"
                lbl = lbl + "kernel path:" + kernel_path + "\n"
                lbl = lbl + "source environment path:" + source_env_path + "\n"
                lbl = lbl + "tmp path: " + tmp_path + "."
                lbl = lbl + "You may be missing either xterm or vte for terminal services."
                dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_ERROR)
                button = dialog.add_button("Close", gtk.RESPONSE_OK)
                HobButton.style_button(button)
                dialog.run()
                dialog.destroy()

    def show_packages(self, ask=True):
        _, selected_recipes = self.recipe_model.get_selected_recipes()
        if selected_recipes and ask:
            lbl = "<b>Package list may be incomplete!</b>\nDo you want to build selected recipes"
            lbl = lbl + " to get a full list or just view the existing packages?"
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
            button = dialog.add_button("View packages", gtk.RESPONSE_NO)
            HobAltButton.style_button(button)
            button = dialog.add_button("Build packages", gtk.RESPONSE_YES)
            HobButton.style_button(button)
            dialog.set_default_response(gtk.RESPONSE_YES)
            response = dialog.run()
            dialog.destroy()
            if response == gtk.RESPONSE_YES:
                self.generate_packages_async()
            else:
                self.switch_page(self.PACKAGE_SELECTION)
        else:
            self.switch_page(self.PACKAGE_SELECTION)

    def show_recipes(self):
        self.switch_page(self.RECIPE_SELECTION)

    def show_configuration(self):
        self.switch_page(self.BASEIMG_SELECTED)

    def stop_build(self):
        if self.stopping:
            lbl = "<b>Force Stop build?</b>\nYou've already selected Stop once,"
            lbl = lbl + " would you like to 'Force Stop' the build?\n\n"
            lbl = lbl + "This will stop the build as quickly as possible but may"
            lbl = lbl + " well leave your build directory in an  unusable state"
            lbl = lbl + " that requires manual steps to fix.\n"
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_WARNING)
            button = dialog.add_button("Cancel", gtk.RESPONSE_CANCEL)
            HobAltButton.style_button(button)
            button = dialog.add_button("Force Stop", gtk.RESPONSE_YES)
            HobButton.style_button(button)
        else:
            lbl = "<b>Stop build?</b>\n\nAre you sure you want to stop this"
            lbl = lbl + " build?\n\n'Force Stop' will stop the build as quickly as"
            lbl = lbl + " possible but may well leave your build directory in an"
            lbl = lbl + " unusable state that requires manual steps to fix.\n\n"
            lbl = lbl + "'Stop' will stop the build as soon as all in"
            lbl = lbl + " progress build tasks are finished. However if a"
            lbl = lbl + " lengthy compilation phase is in progress this may take"
            lbl = lbl + " some time."
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_WARNING)
            button = dialog.add_button("Cancel", gtk.RESPONSE_CANCEL)
            HobAltButton.style_button(button)
            button = dialog.add_button("Stop", gtk.RESPONSE_OK)
            HobAltButton.style_button(button)
            button = dialog.add_button("Force Stop", gtk.RESPONSE_YES)
            HobButton.style_button(button)
        response = dialog.run()
        dialog.destroy()
        if response != gtk.RESPONSE_CANCEL:
            self.stopping = True
        if response == gtk.RESPONSE_OK:
            self.cancel_build_sync()
        elif response == gtk.RESPONSE_YES:
            self.cancel_build_sync(True)
