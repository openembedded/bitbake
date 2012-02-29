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
import gobject
import hashlib
import os
import re
import subprocess
import shlex
from bb.ui.crumbs.hobcolor import HobColors
from bb.ui.crumbs.hobwidget import HobWidget, HobViewTable
from bb.ui.crumbs.progressbar import HobProgressBar

"""
The following are convenience classes for implementing GNOME HIG compliant
BitBake GUI's
In summary: spacing = 12px, border-width = 6px
"""

#
# CrumbsDialog
#
class CrumbsDialog(gtk.Dialog):
    """
    A GNOME HIG compliant dialog widget.
    Add buttons with gtk.Dialog.add_button or gtk.Dialog.add_buttons
    """
    def __init__(self, parent=None, label="", icon=gtk.STOCK_INFO):
        super(CrumbsDialog, self).__init__("", parent, gtk.DIALOG_DESTROY_WITH_PARENT)
        
        #self.set_property("has-separator", False) # note: deprecated in 2.22

        self.set_border_width(6)
        self.vbox.set_property("spacing", 12)
        self.action_area.set_property("spacing", 12)
        self.action_area.set_property("border-width", 6)

        first_row = gtk.HBox(spacing=12)
        first_row.set_property("border-width", 6)
        first_row.show()
        self.vbox.add(first_row)

        self.icon = gtk.Image()
        self.icon.set_from_stock(icon, gtk.ICON_SIZE_DIALOG)
        self.icon.set_property("yalign", 0.00)
        self.icon.show()
        first_row.add(self.icon)

        self.label = gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_line_wrap(True)
        self.label.set_markup(label)
        self.label.set_property("yalign", 0.00)
        self.label.show()
        first_row.add(self.label)

#
# Brought-in-by Dialog
#
class BinbDialog(gtk.Dialog):
    """
    A dialog widget to show "brought in by" info when a recipe/package is clicked.
    """

    def __init__(self, title, content, parent=None):
        super(BinbDialog, self).__init__(title, parent, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, None)

        self.set_position(gtk.WIN_POS_MOUSE)
        self.set_resizable(False)
        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(HobColors.DARK))

        label = gtk.Label(content)
        label.set_alignment(0, 0)
        label.set_line_wrap(True)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.Color(HobColors.WHITE))

        self.vbox.pack_start(label, expand=True, fill=True, padding=10)
        self.vbox.show_all()

#
# AdvancedSettings Dialog
#
class AdvancedSettingDialog (gtk.Dialog):

    def __init__(self, title, configuration, all_image_types,
            all_package_formats, all_distros, all_sdk_machines,
            max_threads, split_model, parent, flags, buttons):
        super(AdvancedSettingDialog, self).__init__(title, parent, flags, buttons)

        # class members from other objects
        # bitbake settings from Builder.Configuration
        self.configuration = configuration
        self.image_types = all_image_types
        self.all_package_formats = all_package_formats
        self.all_distros = all_distros
        self.all_sdk_machines = all_sdk_machines
        self.max_threads = max_threads
        self.split_model = split_model 

        # class members for internal use
        self.pkgfmt_store = None
        self.distro_combo = None
        self.dldir_text = None
        self.sstatedir_text = None
        self.sstatemirror_text = None
        self.bb_spinner = None
        self.pmake_spinner = None
        self.rootfs_size_spinner = None
        self.extra_size_spinner = None
        self.gplv3_checkbox = None
        self.toolchain_checkbox = None
        self.setting_store = None
        self.image_types_checkbuttons = {}

        self.variables = {}
        self.variables["PACKAGE_FORMAT"] = self.configuration.curr_package_format
        self.variables["INCOMPATIBLE_LICENSE"] = self.configuration.incompat_license
        self.variables["IMAGE_FSTYPES"] = self.configuration.image_fstypes
        self.md5 = hashlib.md5(str(sorted(self.variables.items()))).hexdigest()
        self.settings_changed = False

        # create visual elements on the dialog
        self.create_visual_elements()
        self.connect("response", self.response_cb)

    def create_visual_elements(self):
        self.set_size_request(500, 500)

        self.nb = gtk.Notebook()
        self.nb.set_show_tabs(True)
        self.nb.append_page(self.create_image_types_page(), gtk.Label("Image types"))
        self.nb.append_page(self.create_output_page(), gtk.Label("Output"))
        self.nb.append_page(self.create_build_environment_page(), gtk.Label("Build environment"))
        self.nb.append_page(self.create_others_page(), gtk.Label("Others"))
        self.nb.set_current_page(0)
        self.vbox.pack_start(self.nb, expand=True, fill=True)
        self.vbox.pack_end(gtk.HSeparator(), expand=True, fill=True)

        self.show_all()

    def create_image_types_page(self):
        advanced_vbox = gtk.VBox(False, 15)
        advanced_vbox.set_border_width(20)

        rows = (len(self.image_types)+1)/2
        table = gtk.Table(rows + 1, 10, True)
        advanced_vbox.pack_start(table, expand=False, fill=False)

        tooltip = "Select image file system types that will be used."
        image = gtk.Image()
        image.show()
        image.set_from_stock(gtk.STOCK_INFO, gtk.ICON_SIZE_BUTTON)
        image.set_tooltip_text(tooltip)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Select image types:</span>")
        table.attach(label, 0, 9, 0, 1)
        table.attach(image, 9, 10, 0, 1)

        i = 1
        j = 1
        for image_type in self.image_types:
            self.image_types_checkbuttons[image_type] = gtk.CheckButton(image_type)
            self.image_types_checkbuttons[image_type].set_tooltip_text("Build an %s image" % image_type)
            table.attach(self.image_types_checkbuttons[image_type], j, j + 4, i, i + 1)
            if image_type in self.configuration.image_fstypes:
                self.image_types_checkbuttons[image_type].set_active(True)
            i += 1
            if i > rows:
                i = 1
                j = j + 4

        return advanced_vbox

    def create_output_page(self):
        advanced_vbox = gtk.VBox(False, 15)
        advanced_vbox.set_border_width(20)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Packaging Format:</span>")
        tooltip = "Select package formats that will be used. "
        tooltip += "The first format will be used for final image"
        pkgfmt_widget, self.pkgfmt_store = HobWidget.gen_pkgfmt_widget(self.configuration.curr_package_format, self.all_package_formats, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(pkgfmt_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Image Rootfs Size: (MB)</span>")
        tooltip = "Sets the size of your target image.\nThis is the basic size of your target image, unless your selected package size exceeds this value, or you set value to \"Image Extra Size\"."
        rootfs_size_widget, self.rootfs_size_spinner = HobWidget.gen_spinner_widget(int(self.configuration.image_rootfs_size*1.0/1024), 0, 1024, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(rootfs_size_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Image Extra Size: (MB)</span>")
        tooltip = "Sets the extra free space of your target image.\nDefaultly, system will reserve 30% of your image size as your free space. If your image contains zypper, it will bring in 50MB more space. The maximum free space is 1024MB."
        extra_size_widget, self.extra_size_spinner = HobWidget.gen_spinner_widget(int(self.configuration.image_extra_size*1.0/1024), 0, 1024, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(extra_size_widget, expand=False, fill=False)

        self.gplv3_checkbox = gtk.CheckButton("Exclude GPLv3 packages")
        self.gplv3_checkbox.set_tooltip_text("Check this box to prevent GPLv3 packages from being included in your image")
        if "GPLv3" in self.configuration.incompat_license.split():
            self.gplv3_checkbox.set_active(True)
        else:
            self.gplv3_checkbox.set_active(False)
        advanced_vbox.pack_start(self.gplv3_checkbox, expand=False, fill=False)

        sub_hbox = gtk.HBox(False, 5)
        advanced_vbox.pack_start(sub_hbox, expand=False, fill=False)
        self.toolchain_checkbox = gtk.CheckButton("Build Toolchain")
        self.toolchain_checkbox.set_tooltip_text("Check this box to build the related toolchain with your image")
        self.toolchain_checkbox.set_active(self.configuration.toolchain_build)
        sub_hbox.pack_start(self.toolchain_checkbox, expand=False, fill=False)

        tooltip = "This is the Host platform you would like to run the toolchain"
        sdk_machine_widget, self.sdk_machine_combo = HobWidget.gen_combo_widget(self.configuration.curr_sdk_machine, self.all_sdk_machines, tooltip)
        sub_hbox.pack_start(sdk_machine_widget, expand=False, fill=False)

        return advanced_vbox

    def create_build_environment_page(self):
        advanced_vbox = gtk.VBox(False, 15)
        advanced_vbox.set_border_width(20)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Select Distro:</span>")
        tooltip = "This is the Yocto distribution you would like to use"
        distro_widget, self.distro_combo = HobWidget.gen_combo_widget(self.configuration.curr_distro, self.all_distros, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(distro_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">BB_NUMBER_THREADS:</span>")
        tooltip = "Sets the number of threads that bitbake tasks can run simultaneously"
        bbthread_widget, self.bb_spinner = HobWidget.gen_spinner_widget(self.configuration.bbthread, 1, self.max_threads, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(bbthread_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">PARALLEL_MAKE:</span>")
        tooltip = "Sets the make parallism, as known as 'make -j'"
        pmake_widget, self.pmake_spinner = HobWidget.gen_spinner_widget(self.configuration.pmake, 1, self.max_threads, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(pmake_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Set Download Directory:</span>")
        tooltip = "Select a folder that caches the upstream project source code"
        dldir_widget, self.dldir_text = HobWidget.gen_entry_widget(self.split_model, self.configuration.dldir, self, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(dldir_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Select SSTATE Directory:</span>")
        tooltip = "Select a folder that caches your prebuilt results"
        sstatedir_widget, self.sstatedir_text = HobWidget.gen_entry_widget(self.split_model, self.configuration.sstatedir, self, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(sstatedir_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Select SSTATE Mirror:</span>")
        tooltip = "Select the prebuilt mirror that will fasten your build speed"
        sstatemirror_widget, self.sstatemirror_text = HobWidget.gen_entry_widget(self.split_model, self.configuration.sstatemirror, self, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(sstatemirror_widget, expand=False, fill=False)

        return advanced_vbox

    def create_others_page(self):
        advanced_vbox = gtk.VBox(False, 15)
        advanced_vbox.set_border_width(20)

        sub_vbox = gtk.VBox(False, 5)
        advanced_vbox.pack_start(sub_vbox, expand=True, fill=True)
        label = HobWidget.gen_label_widget("<span weight=\"bold\">Add your own variables:</span>")
        tooltip = "This is the key/value pair for your extra settings"
        setting_widget, self.setting_store = HobWidget.gen_editable_settings(self.configuration.extra_setting, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(setting_widget, expand=True, fill=True)

        return advanced_vbox

    def response_cb(self, dialog, response_id):
        self.variables = {}

        self.configuration.curr_package_format = ""
        it = self.pkgfmt_store.get_iter_first()
        while it:
            value = self.pkgfmt_store.get_value(it, 2)
            if value:
                self.configuration.curr_package_format += (self.pkgfmt_store.get_value(it, 1) + " ")
            it = self.pkgfmt_store.iter_next(it)
        self.configuration.curr_package_format = self.configuration.curr_package_format.strip()
        self.variables["PACKAGE_FORMAT"] = self.configuration.curr_package_format

        self.configuration.curr_distro = self.distro_combo.get_active_text()
        self.configuration.dldir = self.dldir_text.get_text()
        self.configuration.sstatedir = self.sstatedir_text.get_text()
        self.configuration.sstatemirror = self.sstatemirror_text.get_text()
        self.configuration.bbthread = self.bb_spinner.get_value_as_int()
        self.configuration.pmake = self.pmake_spinner.get_value_as_int()
        self.configuration.image_rootfs_size = self.rootfs_size_spinner.get_value_as_int() * 1024
        self.configuration.image_extra_size = self.extra_size_spinner.get_value_as_int() * 1024

        self.configuration.image_fstypes = []
        for image_type in self.image_types:
            if self.image_types_checkbuttons[image_type].get_active():
                self.configuration.image_fstypes.append(image_type)
        self.variables["IMAGE_FSTYPES"] = self.configuration.image_fstypes

        if self.gplv3_checkbox.get_active():
            if "GPLv3" not in self.configuration.incompat_license.split():
                self.configuration.incompat_license += " GPLv3"
        else:
            if "GPLv3" in self.configuration.incompat_license.split():
                self.configuration.incompat_license = self.configuration.incompat_license.split().remove("GPLv3")
                self.configuration.incompat_license = " ".join(self.configuration.incompat_license or [])
        self.configuration.incompat_license = self.configuration.incompat_license.strip()
        self.variables["INCOMPATIBLE_LICENSE"] = self.configuration.incompat_license

        self.configuration.toolchain_build = self.toolchain_checkbox.get_active()

        self.configuration.extra_setting = {}
        it = self.setting_store.get_iter_first()
        while it:
            key = self.setting_store.get_value(it, 0)
            value = self.setting_store.get_value(it, 1)
            self.configuration.extra_setting[key] = value
            self.variables[key] = value
            it = self.setting_store.iter_next(it)

        md5 = hashlib.md5(str(sorted(self.variables.items()))).hexdigest()
        self.settings_changed = (self.md5 != md5)

#
# DeployImageDialog
#
class DeployImageDialog (gtk.Dialog):

    __dummy_usb__ = "--select a usb drive--"

    def __init__(self, title, image_path, parent, flags, buttons):
        super(DeployImageDialog, self).__init__(title, parent, flags, buttons)

        self.image_path = image_path

        self.create_visual_elements()
        self.connect("response", self.response_cb)

    def create_visual_elements(self):
        self.set_border_width(20)
        self.set_default_size(500, 250)

        label = gtk.Label()
        label.set_alignment(0.0, 0.5)
        markup = "<span font_desc='12'>The image to be written into usb drive:</span>"
        label.set_markup(markup)
        self.vbox.pack_start(label, expand=False, fill=False, padding=2)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        tv = gtk.TextView()
        tv.set_editable(False)
        tv.set_wrap_mode(gtk.WRAP_WORD)
        tv.set_cursor_visible(False)
        buf = gtk.TextBuffer()
        buf.set_text(self.image_path)
        tv.set_buffer(buf)
        scroll.add(tv)
        self.vbox.pack_start(scroll, expand=True, fill=True)

        self.usb_desc = gtk.Label()
        self.usb_desc.set_alignment(0.0, 0.5)
        markup = "<span font_desc='12'>You haven't chosen any USB drive.</span>"
        self.usb_desc.set_markup(markup)

        self.usb_combo = gtk.combo_box_new_text()
        self.usb_combo.connect("changed", self.usb_combo_changed_cb)
        model = self.usb_combo.get_model()
        model.clear()
        self.usb_combo.append_text(self.__dummy_usb__)
        for usb in self.find_all_usb_devices():
            self.usb_combo.append_text("/dev/" + usb)
        self.usb_combo.set_active(0)
        self.vbox.pack_start(self.usb_combo, expand=True, fill=True)
        self.vbox.pack_start(self.usb_desc, expand=False, fill=False, padding=2)

        self.progress_bar = HobProgressBar()
        self.vbox.pack_start(self.progress_bar, expand=False, fill=False)
        separator = gtk.HSeparator()
        self.vbox.pack_start(separator, expand=False, fill=True, padding=10)

        self.vbox.show_all()
        self.progress_bar.hide()

    def popen_read(self, cmd):
        return os.popen("%s 2>/dev/null" % cmd).read().strip()

    def find_all_usb_devices(self):
        usb_devs = [ os.readlink(u)
            for u in self.popen_read('ls /dev/disk/by-id/usb*').split()
            if not re.search(r'part\d+', u) ]
        return [ '%s' % u[u.rfind('/')+1:] for u in usb_devs ]

    def get_usb_info(self, dev):
        return "%s %s" % \
            (self.popen_read('cat /sys/class/block/%s/device/vendor' % dev),
            self.popen_read('cat /sys/class/block/%s/device/model' % dev))

    def usb_combo_changed_cb(self, usb_combo):
        combo_item = self.usb_combo.get_active_text()
        if not combo_item or combo_item == self.__dummy_usb__:
            markup = "<span font_desc='12'>You haven't chosen any USB drive.</span>"
            self.usb_desc.set_markup(markup)
        else:
            markup = "<span font_desc='12'>" + self.get_usb_info(combo_item.lstrip("/dev/")) + "</span>"
            self.usb_desc.set_markup(markup)

    def response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_YES:
            combo_item = self.usb_combo.get_active_text()
            if combo_item and combo_item != self.__dummy_usb__:
                cmdline = "/usr/bin/xterm -e "
                cmdline += "\"sudo dd if=" + self.image_path + " of=" + combo_item + "; bash\""
                subprocess.Popen(args=shlex.split(cmdline))

    def update_progress_bar(self, title, fraction, status=True):
        self.progress_bar.update(fraction)
        self.progress_bar.set_title(title)
        self.progress_bar.set_rcstyle(status)

    def write_file(self, ifile, ofile):
        self.progress_bar.reset()
        self.progress_bar.show()

        f_from = os.open(ifile, os.O_RDONLY)
        f_to = os.open(ofile, os.O_WRONLY)

        total_size = os.stat(ifile).st_size
        written_size = 0

        while True:
            buf = os.read(f_from, 1024*1024)
            if not buf:
                break
            os.write(f_to, buf)
            written_size += 1024*1024
            self.update_progress_bar("Writing to usb:", written_size * 1.0/total_size)

        self.update_progress_bar("Writing completed:", 1.0)
        os.close(f_from)
        os.close(f_to)
        self.progress_bar.hide()
#
# LayerSelectionDialog
#
class LayerSelectionDialog (gtk.Dialog):

    def __init__(self, title, layers, all_layers, split_model,
            parent, flags, buttons):
        super(LayerSelectionDialog, self).__init__(title, parent, flags, buttons)

        # class members from other objects
        self.layers = layers
        self.all_layers = all_layers
        self.split_model = split_model
        self.layers_changed = False

        # class members for internal use
        self.layer_store = None

        # create visual elements on the dialog
        self.create_visual_elements()
        self.connect("response", self.response_cb)
                
    def create_visual_elements(self):
        self.set_border_width(20)
        self.set_default_size(400, 250)

        hbox_top = gtk.HBox()
        self.set_border_width(12)
        self.vbox.pack_start(hbox_top, expand=False, fill=False)

        if self.split_model:
            label = HobWidget.gen_label_widget("<span weight=\"bold\" font_desc='12'>Select Layers:</span>\n(Available layers under '${COREBASE}/layers/' directory)")
        else:
            label = HobWidget.gen_label_widget("<span weight=\"bold\" font_desc='12'>Select Layers:</span>")
        hbox_top.pack_start(label, expand=False, fill=False)

        tooltip = "Layer is a collection of bb files and conf files"
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_INFO, gtk.ICON_SIZE_BUTTON)
        image.set_tooltip_text(tooltip)
        hbox_top.pack_end(image, expand=False, fill=False)

        layer_widget, self.layer_store = HobWidget.gen_layer_widget(self.split_model, self.layers, self.all_layers, self, None)

        self.vbox.pack_start(layer_widget, expand=True, fill=True)

        separator = gtk.HSeparator()
        self.vbox.pack_start(separator, False, True, 5)
        separator.show()

        hbox_button = gtk.HBox()
        self.vbox.pack_end(hbox_button, expand=False, fill=False)
        hbox_button.show()

        label = HobWidget.gen_label_widget("<i>'meta' is Core layer for Yocto images</i>\n"
        "<span weight=\"bold\">Please do not remove it</span>")
        hbox_button.pack_start(label, expand=False, fill=False)

        self.show_all()

    def response_cb(self, dialog, response_id):
        model = self.layer_store
        it = model.get_iter_first()
        layers = []
        while it:
            if self.split_model:
                inc = model.get_value(it, 1)
                if inc:
                    layers.append(model.get_value(it, 0))
            else:
                layers.append(model.get_value(it, 0))
            it = model.iter_next(it)

        self.layers_changed = (self.layers != layers)
        self.layers = layers

class ImageSelectionDialog (gtk.Dialog):

    __columns__ = [{
            'col_name' : 'Image name',
            'col_id'   : 0,
            'col_style': 'text',
            'col_min'  : 400,
            'col_max'  : 400
        }, {
            'col_name' : 'Select',
            'col_id'   : 1,
            'col_style': 'radio toggle',
            'col_min'  : 160,
            'col_max'  : 160
    }]


    def __init__(self, image_folder, image_types, title, parent, flags, buttons):
        super(ImageSelectionDialog, self).__init__(title, parent, flags, buttons)
        self.connect("response", self.response_cb)

        self.image_folder = image_folder
        self.image_types  = image_types
        self.image_list = []
        self.image_names = []

        # create visual elements on the dialog
        self.create_visual_elements()

        self.image_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        self.fill_image_store()

    def create_visual_elements(self):
        self.set_border_width(20)
        self.set_default_size(600, 300)
        self.vbox.set_spacing(10)

        hbox = gtk.HBox(False, 10)
        self.vbox.pack_start(hbox, expand=False, fill=False)

        entry = gtk.Entry()
        entry.set_text(self.image_folder)
        table = gtk.Table(1, 10, True)
        table.set_size_request(560, -1)
        hbox.pack_start(table, expand=False, fill=False)
        table.attach(entry, 0, 9, 0, 1)
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_OPEN,gtk.ICON_SIZE_BUTTON)
        open_button = gtk.Button()
        open_button.set_image(image)
        open_button.connect("clicked", self.select_path_cb, self, entry)
        table.attach(open_button, 9, 10, 0, 1)

        self.image_table = HobViewTable(self.__columns__)
        self.image_table.connect("toggled", self.toggled_cb)
        self.vbox.pack_start(self.image_table, expand=True, fill=True)

        self.show_all()

    def toggled_cb(self, table, cell, path, columnid, tree):
        model = tree.get_model()
        if not model:
            return
        iter = model.get_iter_first()
        while iter:
            rowpath = model.get_path(iter)
            model[rowpath][columnid] = False
            iter = model.iter_next(iter)

        model[path][columnid] = True

        
    def select_path_cb(self, action, parent, entry):
        dialog = gtk.FileChooserDialog("", parent,
                                       gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                       (gtk.STOCK_OK, gtk.RESPONSE_YES,
                                        gtk.STOCK_CANCEL, gtk.RESPONSE_NO))
        response = dialog.run()
        if response == gtk.RESPONSE_YES:
            path = dialog.get_filename()
            entry.set_text(path)
            self.image_folder = path
            self.fill_image_store()

        dialog.destroy()

    def fill_image_store(self):
        self.image_list = []
        self.image_store.clear()
        imageset = set()
        for root, dirs, files in os.walk(self.image_folder):
            # ignore the sub directories
            dirs[:] = []
            for f in files:
                for image_type in self.image_types:
                    if f.endswith('.' + image_type):
                        imageset.add(f.rsplit('.' + image_type)[0])
                        self.image_list.append(f)
        
        for image in imageset:
            self.image_store.set(self.image_store.append(), 0, image, 1, False)

        self.image_table.set_model(self.image_store)

    def response_cb(self, dialog, response_id):
        self.image_names = []
        if response_id == gtk.RESPONSE_YES:
            iter = self.image_store.get_iter_first()
            while iter:
                path = self.image_store.get_path(iter)
                if self.image_store[path][1]:
                    for f in self.image_list:
                        if f.startswith(self.image_store[path][0] + '.'):
                            self.image_names.append(f)
                    break            
                iter = self.image_store.iter_next(iter)
