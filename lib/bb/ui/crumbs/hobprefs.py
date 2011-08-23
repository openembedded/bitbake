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

import gtk
import glib
from bb.ui.crumbs.configurator import Configurator

class HobPrefs(gtk.Dialog):
    """
    """
    def empty_combo_text(self, combo_text):
        model = combo_text.get_model()
        if model:
            model.clear()

    def output_type_toggled_cb(self, check, handler):
        ot = check.get_label()
        enabled = check.get_active()
        if enabled:
            self.selected_image_types = handler.add_image_output_type(ot)
        else:
            self.selected_image_types = handler.remove_image_output_type(ot)

        self.configurator.setLocalConfVar('IMAGE_FSTYPES', "%s" % " ".join(self.selected_image_types).lstrip(" "))

    def sdk_machine_combo_changed_cb(self, combo, handler):
        sdk_mach = combo.get_active_text()
	if sdk_mach != self.curr_sdk_mach:
            self.curr_sdk_mach = sdk_mach
            self.configurator.setLocalConfVar('SDKMACHINE', sdk_mach)
            handler.set_sdk_machine(sdk_mach)

    def update_sdk_machines(self, handler, sdk_machines):
        active = 0
        # disconnect the signal handler before updating the combo model
        if self.sdk_machine_handler_id:
            self.sdk_machine_combo.disconnect(self.sdk_machine_handler_id)
            self.sdk_machine_handler_id = None

        self.empty_combo_text(self.sdk_machine_combo)
        for sdk_machine in sdk_machines:
            self.sdk_machine_combo.append_text(sdk_machine)
            if sdk_machine == self.curr_sdk_mach:
                self.sdk_machine_combo.set_active(active)
            active = active + 1

        self.sdk_machine_handler_id = self.sdk_machine_combo.connect("changed", self.sdk_machine_combo_changed_cb, handler)

    def distro_combo_changed_cb(self, combo, handler):
        distro = combo.get_active_text()
	if distro != self.curr_distro:
            self.curr_distro = distro
            self.configurator.setLocalConfVar('DISTRO', distro)
            handler.set_distro(distro)
            self.reload_required = True

    def update_distros(self, handler, distros):
        active = 0
        # disconnect the signal handler before updating combo model
        if self.distro_handler_id:
            self.distro_combo.disconnect(self.distro_handler_id)
            self.distro_handler_id = None

        self.empty_combo_text(self.distro_combo)
	for distro in distros:
	    self.distro_combo.append_text(distro)
	    if distro == self.curr_distro:
                self.distro_combo.set_active(active)
	    active = active + 1

	self.distro_handler_id = self.distro_combo.connect("changed", self.distro_combo_changed_cb, handler)

    def package_format_combo_changed_cb(self, combo, handler):
        package_format = combo.get_active_text()
        if package_format != self.curr_package_format:
            self.curr_package_format = package_format
            self.configurator.setLocalConfVar('PACKAGE_CLASSES', 'package_%s' % package_format)
            handler.set_package_format(package_format)
            self.reload_required = True

    def update_package_formats(self, handler, formats):
        active = 0
        # disconnect the signal handler before updating the model
        if self.package_handler_id:
            self.package_combo.disconnect(self.package_handler_id)
            self.package_handler_id = None

        self.empty_combo_text(self.package_combo)
        for format in formats:
            self.package_combo.append_text(format)
            if format == self.curr_package_format:
                self.package_combo.set_active(active)
            active = active + 1

        self.package_handler_id = self.package_combo.connect("changed", self.package_format_combo_changed_cb, handler)
    
    def include_gplv3_cb(self, toggle):
        excluded = toggle.get_active()
        orig_incompatible = self.configurator.getLocalConfVar('INCOMPATIBLE_LICENSE')
        new_incompatible = ""
        if excluded:
            if not orig_incompatible:
                new_incompatible = "GPLv3"
            elif not orig_incompatible.find('GPLv3'):
                new_incompatible = "%s GPLv3" % orig_incompatible
        else:
            new_incompatible = orig_incompatible.replace('GPLv3', '')

        if new_incompatible != orig_incompatible:
            self.handler.set_incompatible_license(new_incompatible)
            self.configurator.setLocalConfVar('INCOMPATIBLE_LICENSE', new_incompatible)
            self.reload_required = True

    def change_bb_threads_cb(self, spinner):
        val = spinner.get_value_as_int()
        self.handler.set_bbthreads(val)
        self.configurator.setLocalConfVar('BB_NUMBER_THREADS', val)

    def change_make_threads_cb(self, spinner):
        val = spinner.get_value_as_int()
        self.handler.set_pmake(val)
        self.configurator.setLocalConfVar('PARALLEL_MAKE', "-j %s" % val)

    def toggle_toolchain_cb(self, check):
        enabled = check.get_active()
        toolchain = '0'
        if enabled:
            toolchain = '1'
        self.handler.toggle_toolchain(enabled)
        self.configurator.setLocalConfVar('HOB_BUILD_TOOLCHAIN', toolchain)

    def toggle_headers_cb(self, check):
        enabled = check.get_active()
        headers = '0'
        if enabled:
            headers = '1'
        self.handler.toggle_toolchain_headers(enabled)
        self.configurator.setLocalConfVar('HOB_BUILD_TOOLCHAIN_HEADERS', headers)

    def set_parent_window(self, parent):
        self.set_transient_for(parent)

    def write_changes(self):
        self.configurator.writeLocalConf()

    def prefs_response_cb(self, dialog, response):
        if self.reload_required:
            glib.idle_add(self.handler.reload_data)
            self.reload_required = False

    def __init__(self, configurator, handler, curr_sdk_mach, curr_distro, pclass,
                 pmake, bbthread, selected_image_types, all_image_types,
                 gplv3disabled, build_toolchain, build_toolchain_headers):
        """
        """
        gtk.Dialog.__init__(self, "Preferences", None,
                            gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CLOSE, gtk.RESPONSE_OK))

        self.set_border_width(6)
        self.vbox.set_property("spacing", 12)
        self.action_area.set_property("spacing", 12)
        self.action_area.set_property("border-width", 6)

        self.handler = handler
        self.configurator = configurator

        self.curr_sdk_mach = curr_sdk_mach
        self.curr_distro = curr_distro
        self.curr_package_format = pclass
        self.pmake = pmake
        self.bbthread = bbthread
        self.selected_image_types = selected_image_types.split(" ")
        self.gplv3disabled = gplv3disabled
        self.build_toolchain = build_toolchain
        self.build_toolchain_headers = build_toolchain_headers

        self.reload_required = False
        self.distro_handler_id = None
        self.sdk_machine_handler_id = None
        self.package_handler_id = None

        left = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        right = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)

        label = gtk.Label()
        label.set_markup("<b>Policy</b>")
        label.show()
        frame = gtk.Frame()
        frame.set_label_widget(label)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        frame.show()
        self.vbox.pack_start(frame)
        pbox = gtk.VBox(False, 12)
        pbox.show()
        frame.add(pbox)
        hbox = gtk.HBox(False, 12)
        hbox.show()
        pbox.pack_start(hbox, expand=False, fill=False, padding=6)
        # Distro selector
        label = gtk.Label("Distribution:")
        label.show()
        hbox.pack_start(label, expand=False, fill=False, padding=6)
        self.distro_combo = gtk.combo_box_new_text()
        self.distro_combo.set_tooltip_text("Select the Yocto distribution you would like to use")
        self.distro_combo.show()
        hbox.pack_start(self.distro_combo, expand=False, fill=False, padding=6)
        # Exclude GPLv3
        check = gtk.CheckButton("Exclude GPLv3 packages")
        check.set_tooltip_text("Check this box to prevent GPLv3 packages from being included in your image")
        check.show()
        check.set_active(self.gplv3disabled)
        check.connect("toggled", self.include_gplv3_cb)
        hbox.pack_start(check, expand=False, fill=False, padding=6)
        hbox = gtk.HBox(False, 12)
        hbox.show()
        pbox.pack_start(hbox, expand=False, fill=False, padding=6)
        # Package format selector
        label = gtk.Label("Package format:")
        label.show()
        hbox.pack_start(label, expand=False, fill=False, padding=6)
        self.package_combo = gtk.combo_box_new_text()
        self.package_combo.set_tooltip_text("""The package format is that used in creation
 of the root filesystem and also dictates the package manager used in your image""")
        self.package_combo.show()
        hbox.pack_start(self.package_combo, expand=False, fill=False, padding=6)
        if all_image_types:
            # Image output type selector
            label = gtk.Label("Image output types:")
            label.show()
            hbox.pack_start(label, expand=False, fill=False, padding=6)
            chk_cnt = 3
            for it in all_image_types.split(" "):
                chk_cnt = chk_cnt + 1
                if chk_cnt % 6 == 0:
                    hbox = gtk.HBox(False, 12)
                    hbox.show()
                    pbox.pack_start(hbox, expand=False, fill=False, padding=6)
                chk = gtk.CheckButton(it)
                if it in self.selected_image_types:
                    chk.set_active(True)
                chk.set_tooltip_text("Build an %s image" % it)
                chk.connect("toggled", self.output_type_toggled_cb, handler)
                chk.show()
                hbox.pack_start(chk, expand=False, fill=False, padding=3)
        # BitBake
        label = gtk.Label()
        label.set_markup("<b>BitBake</b>")
        label.show()
        frame = gtk.Frame()
        frame.set_label_widget(label)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        frame.show()
        self.vbox.pack_start(frame)
        pbox = gtk.VBox(False, 12)
        pbox.show()
        frame.add(pbox)
        hbox = gtk.HBox(False, 12)
        hbox.show()
        pbox.pack_start(hbox, expand=False, fill=False, padding=6)
        label = gtk.Label("BitBake threads:")
        label.show()
        # NOTE: may be a good idea in future to intelligently cap the maximum
        # values but we need more data to make an educated decision, for now
        # set a high maximum as a value for upper bounds is required by the
        # gtk.Adjustment
        spin_max = 30 # seems like a high enough arbitrary number
        hbox.pack_start(label, expand=False, fill=False, padding=6)
        bbadj = gtk.Adjustment(value=self.bbthread, lower=1, upper=spin_max, step_incr=1)
        bbspinner = gtk.SpinButton(adjustment=bbadj, climb_rate=1, digits=0)
        bbspinner.show()
        bbspinner.connect("value-changed", self.change_bb_threads_cb)
        hbox.pack_start(bbspinner, expand=False, fill=False, padding=6)
        label = gtk.Label("Make threads:")
        label.show()
        hbox.pack_start(label, expand=False, fill=False, padding=6)
        madj = gtk.Adjustment(value=self.pmake, lower=1, upper=spin_max, step_incr=1)
        makespinner = gtk.SpinButton(adjustment=madj, climb_rate=1, digits=0)
        makespinner.connect("value-changed", self.change_make_threads_cb)
        makespinner.show()
        hbox.pack_start(makespinner, expand=False, fill=False, padding=6)
        # Toolchain
        label = gtk.Label()
        label.set_markup("<b>External Toolchain</b>")
        label.show()
        frame = gtk.Frame()
        frame.set_label_widget(label)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        frame.show()
        self.vbox.pack_start(frame)
        pbox = gtk.VBox(False, 12)
        pbox.show()
        frame.add(pbox)
        hbox = gtk.HBox(False, 12)
        hbox.show()
        pbox.pack_start(hbox, expand=False, fill=False, padding=6)
        toolcheck = gtk.CheckButton("Build external development toolchain with image")
        toolcheck.show()
        toolcheck.set_active(self.build_toolchain)
        toolcheck.connect("toggled", self.toggle_toolchain_cb)
        hbox.pack_start(toolcheck, expand=False, fill=False, padding=6)
        hbox = gtk.HBox(False, 12)
        hbox.show()
        pbox.pack_start(hbox, expand=False, fill=False, padding=6)
        label = gtk.Label("Toolchain host:")
        label.show()
        hbox.pack_start(label, expand=False, fill=False, padding=6)
        self.sdk_machine_combo = gtk.combo_box_new_text()
        self.sdk_machine_combo.set_tooltip_text("Select the host architecture of the external machine")
        self.sdk_machine_combo.show()
        hbox.pack_start(self.sdk_machine_combo, expand=False, fill=False, padding=6)
        headerscheck = gtk.CheckButton("Include development headers with toolchain")
        headerscheck.show()
        headerscheck.set_active(self.build_toolchain_headers)
        headerscheck.connect("toggled", self.toggle_headers_cb)
        hbox.pack_start(headerscheck, expand=False, fill=False, padding=6)
        self.connect("response", self.prefs_response_cb)
