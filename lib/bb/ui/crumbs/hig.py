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

import glob
import glib
import gtk
import gobject
import hashlib
import os
import re
import shlex
import subprocess
import tempfile
from bb.ui.crumbs.hobcolor import HobColors
from bb.ui.crumbs.hobwidget import hic, HobViewTable, HobInfoButton, HobButton, HobAltButton, HobIconChecker
from bb.ui.crumbs.progressbar import HobProgressBar
import bb.ui.crumbs.utils
import bb.process

"""
The following are convenience classes for implementing GNOME HIG compliant
BitBake GUI's
In summary: spacing = 12px, border-width = 6px
"""


class SettingsUIHelper():

    def gen_label_widget(self, content):
        label = gtk.Label()
        label.set_alignment(0, 0)
        label.set_markup(content)
        label.show()
        return label

    def gen_label_info_widget(self, content, tooltip):
        table = gtk.Table(1, 10, False)
        label = self.gen_label_widget(content)
        info = HobInfoButton(tooltip, self)
        table.attach(label, 0, 1, 0, 1, xoptions=gtk.FILL)
        table.attach(info, 1, 2, 0, 1, xoptions=gtk.FILL, xpadding=10)
        return table

    def gen_spinner_widget(self, content, lower, upper, tooltip=""):
        hbox = gtk.HBox(False, 12)
        adjust = gtk.Adjustment(value=content, lower=lower, upper=upper, step_incr=1)
        spinner = gtk.SpinButton(adjustment=adjust, climb_rate=1, digits=0)

        spinner.set_value(content)
        hbox.pack_start(spinner, expand=False, fill=False)

        info = HobInfoButton(tooltip, self)
        hbox.pack_start(info, expand=False, fill=False)

        hbox.show_all()
        return hbox, spinner

    def gen_combo_widget(self, curr_item, all_item, tooltip=""):
        hbox = gtk.HBox(False, 12)
        combo = gtk.combo_box_new_text()
        hbox.pack_start(combo, expand=False, fill=False)

        index = 0
        for item in all_item or []:
            combo.append_text(item)
            if item == curr_item:
                combo.set_active(index)
            index += 1

        info = HobInfoButton(tooltip, self)
        hbox.pack_start(info, expand=False, fill=False)

        hbox.show_all()
        return hbox, combo

    def entry_widget_select_path_cb(self, action, parent, entry):
        dialog = gtk.FileChooserDialog("", parent,
                                       gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        text = entry.get_text()
        dialog.set_current_folder(text if len(text) > 0 else os.getcwd())
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Open", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        response = dialog.run()
        if response == gtk.RESPONSE_YES:
            path = dialog.get_filename()
            entry.set_text(path)

        dialog.destroy()

    def gen_entry_widget(self, content, parent, tooltip="", need_button=True):
        hbox = gtk.HBox(False, 12)
        entry = gtk.Entry()
        entry.set_text(content)
        entry.set_size_request(350,30)

        if need_button:
            table = gtk.Table(1, 10, False)
            hbox.pack_start(table, expand=True, fill=True)
            table.attach(entry, 0, 9, 0, 1, xoptions=gtk.SHRINK)
            image = gtk.Image()
            image.set_from_stock(gtk.STOCK_OPEN,gtk.ICON_SIZE_BUTTON)
            open_button = gtk.Button()
            open_button.set_image(image)
            open_button.connect("clicked", self.entry_widget_select_path_cb, parent, entry)
            table.attach(open_button, 9, 10, 0, 1, xoptions=gtk.SHRINK)
        else:
            hbox.pack_start(entry, expand=True, fill=True)

        if tooltip != "":
            info = HobInfoButton(tooltip, self)
            hbox.pack_start(info, expand=False, fill=False)

        hbox.show_all()
        return hbox, entry

    def gen_mirror_entry_widget(self, content, index, match_content=""):
        hbox = gtk.HBox(False)
        entry = gtk.Entry()
        content = content[:-2]
        entry.set_text(content)
        entry.set_size_request(350,30)

        entry_match = gtk.Entry()
        entry_match.set_text(match_content)
        entry_match.set_size_request(100,30)

        table = gtk.Table(2, 5, False)
        table.set_row_spacings(12)
        table.set_col_spacings(6)
        hbox.pack_start(table, expand=True, fill=True)

        label_configuration = gtk.Label("Configuration")
        label_configuration.set_alignment(0.0,0.5)
        label_mirror_url = gtk.Label("Mirror URL")
        label_mirror_url.set_alignment(0.0,0.5)
        label_match = gtk.Label("Match")
        label_match.set_alignment(0.0,0.5)
        label_replace_with = gtk.Label("Replace with")
        label_replace_with.set_alignment(0.0,0.5)

        combo = gtk.combo_box_new_text()
        combo.append_text("Standard")
        combo.append_text("Custom")
        if match_content == "":
            combo.set_active(0)
        else:
            combo.set_active(1)
        combo.connect("changed", self.on_combo_changed, index)
        combo.set_size_request(100,30)

        delete_button = HobAltButton("Delete")
        delete_button.connect("clicked", self.delete_cb, index, entry)
        if content == "" and index == 0  and len(self.sstatemirrors_list) == 1:
            delete_button.set_sensitive(False)
        delete_button.set_size_request(100, 30)

        entry_match.connect("changed", self.insert_entry_match_cb, index)
        entry.connect("changed", self.insert_entry_cb, index, delete_button)

        if match_content == "":
            table.attach(label_configuration, 1, 2, 0, 1, xoptions=gtk.SHRINK|gtk.FILL)
            table.attach(label_mirror_url, 2, 3, 0, 1, xoptions=gtk.SHRINK|gtk.FILL)
            table.attach(combo, 1, 2, 1, 2, xoptions=gtk.SHRINK)
            table.attach(entry, 2, 3, 1, 2, xoptions=gtk.SHRINK)
            table.attach(delete_button, 3, 4, 1, 2, xoptions=gtk.SHRINK)
        else:
            table.attach(label_configuration, 1, 2, 0, 1, xoptions=gtk.SHRINK|gtk.FILL)
            table.attach(label_match, 2, 3, 0, 1, xoptions=gtk.SHRINK|gtk.FILL)
            table.attach(label_replace_with, 3, 4, 0, 1, xoptions=gtk.SHRINK|gtk.FILL)
            table.attach(combo, 1, 2, 1, 2, xoptions=gtk.SHRINK)
            table.attach(entry_match, 2, 3, 1, 2, xoptions=gtk.SHRINK)
            table.attach(entry, 3, 4, 1, 2, xoptions=gtk.SHRINK)
            table.attach(delete_button, 4, 5, 1, 2, xoptions=gtk.SHRINK)

        hbox.show_all()
        return hbox

    def insert_entry_match_cb(self, entry_match, index):
        self.sstatemirrors_list[index][2] = entry_match.get_text()

    def insert_entry_cb(self, entry, index, button):
        self.sstatemirrors_list[index][1] = entry.get_text()
        if entry.get_text() == "" and index == 0:
            button.set_sensitive(False)
        else:
            button.set_sensitive(True)

    def on_combo_changed(self, combo, index):
        if combo.get_active_text() == "Standard":
            self.sstatemirrors_list[index][0] = 0
            self.sstatemirrors_list[index][2] = "file://(.*)"
        else:
            self.sstatemirrors_list[index][0] = 1
        self.refresh_shared_state_page()

    def delete_cb(self, button, index, entry):
        if index == 0 and len(self.sstatemirrors_list)==1:
            entry.set_text("")
        else:
            self.sstatemirrors_list.pop(index)
            self.refresh_shared_state_page()

    def add_mirror(self, button):
        tooltip = "Select the pre-built mirror that will speed your build"
        index = len(self.sstatemirrors_list)
        sm_list = [0, "", "file://(.*)"]
        self.sstatemirrors_list.append(sm_list)
        self.refresh_shared_state_page()

#
# CrumbsDialog
#
class CrumbsDialog(gtk.Dialog):
    """
    A GNOME HIG compliant dialog widget.
    Add buttons with gtk.Dialog.add_button or gtk.Dialog.add_buttons
    """
    def __init__(self, title="", parent=None, flags=0, buttons=None):
        super(CrumbsDialog, self).__init__(title, parent, flags, buttons)

        self.set_property("has-separator", False) # note: deprecated in 2.22

        self.set_border_width(6)
        self.vbox.set_property("spacing", 12)
        self.action_area.set_property("spacing", 12)
        self.action_area.set_property("border-width", 6)

class CrumbsMessageDialog(CrumbsDialog):
    """
    A GNOME HIG compliant dialog widget.
    Add buttons with gtk.Dialog.add_button or gtk.Dialog.add_buttons
    """
    def __init__(self, parent=None, label="", icon=gtk.STOCK_INFO, msg=""):
        super(CrumbsMessageDialog, self).__init__("", parent, gtk.DIALOG_MODAL)

        self.set_border_width(6)
        self.vbox.set_property("spacing", 12)
        self.action_area.set_property("spacing", 12)
        self.action_area.set_property("border-width", 6)

        first_column = gtk.HBox(spacing=12)
        first_column.set_property("border-width", 6)
        first_column.show()
        self.vbox.add(first_column)

        self.icon = gtk.Image()
        # We have our own Info icon which should be used in preference of the stock icon
        self.icon_chk = HobIconChecker()
        self.icon.set_from_stock(self.icon_chk.check_stock_icon(icon), gtk.ICON_SIZE_DIALOG)
        self.icon.set_property("yalign", 0.00)
        self.icon.show()
        first_column.pack_start(self.icon, expand=False, fill=True, padding=0)
        
        if 0 <= len(msg) < 200:
            lbl = label + "%s" % glib.markup_escape_text(msg)
            self.label_short = gtk.Label()
            self.label_short.set_use_markup(True)
            self.label_short.set_line_wrap(True)
            self.label_short.set_markup(lbl)
            self.label_short.set_property("yalign", 0.00)
            self.label_short.show()
            first_column.add(self.label_short)
        else:
            second_row = gtk.VBox(spacing=12)
            second_row.set_property("border-width", 6)
            self.label_long = gtk.Label()
            self.label_long.set_use_markup(True)
            self.label_long.set_line_wrap(True)
            self.label_long.set_markup(label)
            self.label_long.set_alignment(0.0, 0.0)
            second_row.pack_start(self.label_long, expand=False, fill=False, padding=0)
            self.label_long.show()
            self.textWindow = gtk.ScrolledWindow()
            self.textWindow.set_shadow_type(gtk.SHADOW_IN)
            self.textWindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            self.msgView = gtk.TextView()
            self.msgView.set_editable(False)
            self.msgView.set_wrap_mode(gtk.WRAP_WORD)
            self.msgView.set_cursor_visible(False)
            self.msgView.set_size_request(300, 300)
            self.buf = gtk.TextBuffer()
            self.buf.set_text(msg)
            self.msgView.set_buffer(self.buf)
            self.textWindow.add(self.msgView)
            self.msgView.show()
            second_row.add(self.textWindow)
            self.textWindow.show()
            first_column.add(second_row)
            second_row.show()

#
# SimpleSettings Dialog
#
class SimpleSettingsDialog (CrumbsDialog, SettingsUIHelper):

    (BUILD_ENV_PAGE_ID,
     SHARED_STATE_PAGE_ID,
     PROXIES_PAGE_ID,
     OTHERS_PAGE_ID) = range(4)

    (TEST_NETWORK_NONE,
     TEST_NETWORK_INITIAL,
     TEST_NETWORK_RUNNING,
     TEST_NETWORK_PASSED,
     TEST_NETWORK_FAILED,
     TEST_NETWORK_CANCELED) = range(6)

    def __init__(self, title, configuration, all_image_types,
            all_package_formats, all_distros, all_sdk_machines,
            max_threads, parent, flags, handler, buttons=None):
        super(SimpleSettingsDialog, self).__init__(title, parent, flags, buttons)

        # class members from other objects
        # bitbake settings from Builder.Configuration
        self.configuration = configuration
        self.image_types = all_image_types
        self.all_package_formats = all_package_formats
        self.all_distros = all_distros
        self.all_sdk_machines = all_sdk_machines
        self.max_threads = max_threads

        # class members for internal use
        self.dldir_text = None
        self.sstatedir_text = None
        self.sstatemirrors_list = []
        self.sstatemirrors_changed = 0
        self.bb_spinner = None
        self.pmake_spinner = None
        self.rootfs_size_spinner = None
        self.extra_size_spinner = None
        self.gplv3_checkbox = None
        self.toolchain_checkbox = None
        self.setting_store = None
        self.image_types_checkbuttons = {}

        self.md5 = self.config_md5()
        self.proxy_md5 = self.config_proxy_md5()
        self.settings_changed = False
        self.proxy_settings_changed = False
        self.handler = handler
        self.proxy_test_ran = False

        # create visual elements on the dialog
        self.create_visual_elements()
        self.connect("response", self.response_cb)

    def _get_sorted_value(self, var):
        return " ".join(sorted(str(var).split())) + "\n"

    def config_proxy_md5(self):
        data = ("ENABLE_PROXY: "         + self._get_sorted_value(self.configuration.enable_proxy))
        if self.configuration.enable_proxy:
            for protocol in self.configuration.proxies.keys():
                data += (protocol + ": " + self._get_sorted_value(self.configuration.combine_proxy(protocol)))
        return hashlib.md5(data).hexdigest()

    def config_md5(self):
        data = ""
        for key in self.configuration.extra_setting.keys():
            data += (key + ": " + self._get_sorted_value(self.configuration.extra_setting[key]))
        return hashlib.md5(data).hexdigest()

    def gen_proxy_entry_widget(self, protocol, parent, need_button=True, line=0):
        label = gtk.Label(protocol.upper() + " proxy")
        self.proxy_table.attach(label, 0, 1, line, line+1, xpadding=24)

        proxy_entry = gtk.Entry()
        proxy_entry.set_size_request(300, -1)
        self.proxy_table.attach(proxy_entry, 1, 2, line, line+1, ypadding=4)

        self.proxy_table.attach(gtk.Label(":"), 2, 3, line, line+1, xpadding=12, ypadding=4)

        port_entry = gtk.Entry()
        port_entry.set_size_request(60, -1)
        self.proxy_table.attach(port_entry, 3, 4, line, line+1, ypadding=4)

        details_button = HobAltButton("Details")
        details_button.connect("clicked", self.details_cb, parent, protocol)
        self.proxy_table.attach(details_button, 4, 5, line, line+1, xpadding=4, yoptions=gtk.EXPAND)

        return proxy_entry, port_entry, details_button

    def refresh_proxy_components(self):
        self.same_checkbox.set_sensitive(self.configuration.enable_proxy)

        self.http_proxy.set_text(self.configuration.combine_host_only("http"))
        self.http_proxy.set_editable(self.configuration.enable_proxy)
        self.http_proxy.set_sensitive(self.configuration.enable_proxy)
        self.http_proxy_port.set_text(self.configuration.combine_port_only("http"))
        self.http_proxy_port.set_editable(self.configuration.enable_proxy)
        self.http_proxy_port.set_sensitive(self.configuration.enable_proxy)
        self.http_proxy_details.set_sensitive(self.configuration.enable_proxy)

        self.https_proxy.set_text(self.configuration.combine_host_only("https"))
        self.https_proxy.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.https_proxy.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.https_proxy_port.set_text(self.configuration.combine_port_only("https"))
        self.https_proxy_port.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.https_proxy_port.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.https_proxy_details.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))

        self.ftp_proxy.set_text(self.configuration.combine_host_only("ftp"))
        self.ftp_proxy.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.ftp_proxy.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.ftp_proxy_port.set_text(self.configuration.combine_port_only("ftp"))
        self.ftp_proxy_port.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.ftp_proxy_port.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.ftp_proxy_details.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))

        self.git_proxy.set_text(self.configuration.combine_host_only("git"))
        self.git_proxy.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.git_proxy.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.git_proxy_port.set_text(self.configuration.combine_port_only("git"))
        self.git_proxy_port.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.git_proxy_port.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.git_proxy_details.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))

        self.cvs_proxy.set_text(self.configuration.combine_host_only("cvs"))
        self.cvs_proxy.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.cvs_proxy.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.cvs_proxy_port.set_text(self.configuration.combine_port_only("cvs"))
        self.cvs_proxy_port.set_editable(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.cvs_proxy_port.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))
        self.cvs_proxy_details.set_sensitive(self.configuration.enable_proxy and (not self.configuration.same_proxy))

        if self.configuration.same_proxy:
            if self.http_proxy.get_text():
                [w.set_text(self.http_proxy.get_text()) for w in self.same_proxy_addresses]
            if self.http_proxy_port.get_text():
                [w.set_text(self.http_proxy_port.get_text()) for w in self.same_proxy_ports]

    def proxy_checkbox_toggled_cb(self, button):
        self.configuration.enable_proxy = self.proxy_checkbox.get_active()
        if not self.configuration.enable_proxy:
            self.configuration.same_proxy = False
            self.same_checkbox.set_active(self.configuration.same_proxy)
        self.save_proxy_data()
        self.refresh_proxy_components()

    def same_checkbox_toggled_cb(self, button):
        self.configuration.same_proxy = self.same_checkbox.get_active()
        self.save_proxy_data()
        self.refresh_proxy_components()

    def save_proxy_data(self):
        self.configuration.split_proxy("http", self.http_proxy.get_text() + ":" + self.http_proxy_port.get_text())
        if self.configuration.same_proxy:
            self.configuration.split_proxy("https", self.http_proxy.get_text() + ":" + self.http_proxy_port.get_text())
            self.configuration.split_proxy("ftp", self.http_proxy.get_text() + ":" + self.http_proxy_port.get_text())
            self.configuration.split_proxy("git", self.http_proxy.get_text() + ":" + self.http_proxy_port.get_text())
            self.configuration.split_proxy("cvs", self.http_proxy.get_text() + ":" + self.http_proxy_port.get_text())
        else:
            self.configuration.split_proxy("https", self.https_proxy.get_text() + ":" + self.https_proxy_port.get_text())
            self.configuration.split_proxy("ftp", self.ftp_proxy.get_text() + ":" + self.ftp_proxy_port.get_text())
            self.configuration.split_proxy("git", self.git_proxy.get_text() + ":" + self.git_proxy_port.get_text())
            self.configuration.split_proxy("cvs", self.cvs_proxy.get_text() + ":" + self.cvs_proxy_port.get_text())       

    def response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_YES:
            # Check that all proxy entries have a corresponding port
            for proxy, port in zip(self.all_proxy_addresses, self.all_proxy_ports):
                if proxy.get_text() and not port.get_text():
                    lbl = "<b>Enter all port numbers</b>\n\n"
                    msg = "Proxy servers require a port number. Please make sure you have entered a port number for each proxy server."
                    dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_WARNING, msg)
                    button = dialog.add_button("Close", gtk.RESPONSE_OK)
                    HobButton.style_button(button)
                    response = dialog.run()
                    dialog.destroy()
                    self.emit_stop_by_name("response")
                    return

        self.configuration.dldir = self.dldir_text.get_text()
        self.configuration.sstatedir = self.sstatedir_text.get_text()
        self.configuration.sstatemirror = ""
        for mirror in self.sstatemirrors_list:
            if mirror[1] != "":
                if mirror[1].endswith("\\1"):
                    smirror = mirror[2] + " " + mirror[1] + " \\n "
                else:
                    smirror = mirror[2] + " " + mirror[1] + "\\1 \\n "
                self.configuration.sstatemirror += smirror
        self.configuration.bbthread = self.bb_spinner.get_value_as_int()
        self.configuration.pmake = self.pmake_spinner.get_value_as_int()
        self.save_proxy_data()
        self.configuration.extra_setting = {}
        it = self.setting_store.get_iter_first()
        while it:
            key = self.setting_store.get_value(it, 0)
            value = self.setting_store.get_value(it, 1)
            self.configuration.extra_setting[key] = value
            it = self.setting_store.iter_next(it)

        md5 = self.config_md5()
        self.settings_changed = (self.md5 != md5)
        self.proxy_settings_changed = (self.proxy_md5 != self.config_proxy_md5())

    def create_build_environment_page(self):
        advanced_vbox = gtk.VBox(False, 6)
        advanced_vbox.set_border_width(6)

        advanced_vbox.pack_start(self.gen_label_widget('<span weight="bold">Parallel threads</span>'), expand=False, fill=False)
        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = self.gen_label_widget("BitBake parallel threads")
        tooltip = "Sets the number of threads that BitBake tasks can simultaneously run. See the <a href=\""
        tooltip += "http://www.yoctoproject.org/docs/current/poky-ref-manual/"
        tooltip += "poky-ref-manual.html#var-BB_NUMBER_THREADS\">Poky reference manual</a> for information"
        bbthread_widget, self.bb_spinner = self.gen_spinner_widget(self.configuration.bbthread, 1, self.max_threads, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(bbthread_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = self.gen_label_widget("Make parallel threads")
        tooltip = "Sets the maximum number of threads the host can use during the build. See the <a href=\""
        tooltip += "http://www.yoctoproject.org/docs/current/poky-ref-manual/"
        tooltip += "poky-ref-manual.html#var-PARALLEL_MAKE\">Poky reference manual</a> for information"
        pmake_widget, self.pmake_spinner = self.gen_spinner_widget(self.configuration.pmake, 1, self.max_threads, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(pmake_widget, expand=False, fill=False)

        advanced_vbox.pack_start(self.gen_label_widget('<span weight="bold">Downloaded source code</span>'), expand=False, fill=False)
        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = self.gen_label_widget("Downloads directory")
        tooltip = "Select a folder that caches the upstream project source code"
        dldir_widget, self.dldir_text = self.gen_entry_widget(self.configuration.dldir, self, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(dldir_widget, expand=False, fill=False)

        return advanced_vbox

    def create_shared_state_page(self):
        advanced_vbox = gtk.VBox(False)
        advanced_vbox.set_border_width(12)

        sub_vbox = gtk.VBox(False)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False, padding=24)
        content = "<span>Shared state directory</span>"
        tooltip = "Select a folder that caches your prebuilt results"
        label = self.gen_label_info_widget(content, tooltip)
        sstatedir_widget, self.sstatedir_text = self.gen_entry_widget(self.configuration.sstatedir, self)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(sstatedir_widget, expand=False, fill=False, padding=12)

        content = "<span weight=\"bold\">Shared state mirrors</span>"
        tooltip = "URLs pointing to pre-built mirrors that will speed your build. "
        tooltip += "Select the \'Standard\' configuration if the structure of your "
        tooltip += "mirror replicates the structure of your local shared state directory. "
        tooltip += "For more information on shared state mirrors, check the <a href=\""
        tooltip += "http://www.yoctoproject.org/docs/current/poky-ref-manual/"
        tooltip += "poky-ref-manual.html#shared-state\">Yocto Project Reference Manual</a>."
        table = self.gen_label_info_widget(content, tooltip)
        advanced_vbox.pack_start(table, expand=False, fill=False)

        sub_vbox = gtk.VBox(False)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add_with_viewport(sub_vbox)
        scroll.connect('size-allocate', self.scroll_changed)
        advanced_vbox.pack_start(scroll, gtk.TRUE, gtk.TRUE, 0)
        searched_string = "file://"

        if self.sstatemirrors_changed == 0:
            self.sstatemirrors_changed = 1
            sstatemirrors = self.configuration.sstatemirror
            if sstatemirrors == "":
                sm_list = [ 0, "", "file://(.*)"]
                self.sstatemirrors_list.append(sm_list)
            else:
                while sstatemirrors.find(searched_string) != -1:
                    if sstatemirrors.find(searched_string,1) != -1:
                        sstatemirror = sstatemirrors[:sstatemirrors.find(searched_string,1)]
                        sstatemirrors = sstatemirrors[sstatemirrors.find(searched_string,1):]
                    else:
                        sstatemirror = sstatemirrors
                        sstatemirrors = sstatemirrors[1:]

                    sstatemirror_fields = [x for x in sstatemirror.split(' ') if x.strip()]
                    if sstatemirror_fields[0] == "file://(.*)":
                        sm_list = [ 0, sstatemirror_fields[1], "file://(.*)"]
                    else:
                        sm_list = [ 1, sstatemirror_fields[1], sstatemirror_fields[0]]
                    self.sstatemirrors_list.append(sm_list)

        index = 0
        for mirror in self.sstatemirrors_list:
            if mirror[0] == 0:
                sstatemirror_widget = self.gen_mirror_entry_widget(mirror[1], index)
            else:
                sstatemirror_widget = self.gen_mirror_entry_widget(mirror[1], index, mirror[2])
            sub_vbox.pack_start(sstatemirror_widget, expand=False, fill=False, padding=9)
            index += 1

        table = gtk.Table(1, 1, False)
        table.set_col_spacings(6)
        add_mirror_button = HobAltButton("Add another mirror")
        add_mirror_button.connect("clicked", self.add_mirror)
        add_mirror_button.set_size_request(150,30)
        table.attach(add_mirror_button, 1, 2, 0, 1, xoptions=gtk.SHRINK)
        advanced_vbox.pack_start(table, expand=False, fill=False, padding=9)

        return advanced_vbox

    def refresh_shared_state_page(self):
        page_num = self.nb.get_current_page()
        self.nb.remove_page(page_num);
        self.nb.insert_page(self.create_shared_state_page(), gtk.Label("Shared state"),page_num)
        self.show_all()
        self.nb.set_current_page(page_num)

    def test_proxy_ended(self, passed):
        self.proxy_test_running = False
        self.set_test_proxy_state(self.TEST_NETWORK_PASSED if passed else self.TEST_NETWORK_FAILED)
        self.set_sensitive(True)
        self.refresh_proxy_components()

    def timer_func(self):
        self.test_proxy_progress.pulse()
        return self.proxy_test_running

    def test_network_button_cb(self, b):
        self.set_test_proxy_state(self.TEST_NETWORK_RUNNING)
        self.set_sensitive(False)
        self.save_proxy_data()
        if self.configuration.enable_proxy == True:
            self.handler.set_http_proxy(self.configuration.combine_proxy("http"))
            self.handler.set_https_proxy(self.configuration.combine_proxy("https"))
            self.handler.set_ftp_proxy(self.configuration.combine_proxy("ftp"))
            self.handler.set_git_proxy(self.configuration.combine_host_only("git"), self.configuration.combine_port_only("git"))
            self.handler.set_cvs_proxy(self.configuration.combine_host_only("cvs"), self.configuration.combine_port_only("cvs"))
        elif self.configuration.enable_proxy == False:
            self.handler.set_http_proxy("")
            self.handler.set_https_proxy("")
            self.handler.set_ftp_proxy("")
            self.handler.set_git_proxy("", "")
            self.handler.set_cvs_proxy("", "")
        self.proxy_test_ran = True
        self.proxy_test_running = True
        gobject.timeout_add(100, self.timer_func)
        self.handler.trigger_network_test()

    def test_proxy_focus_event(self, w, direction):
        if self.test_proxy_state in [self.TEST_NETWORK_PASSED, self.TEST_NETWORK_FAILED]:
            self.set_test_proxy_state(self.TEST_NETWORK_INITIAL)
        return False

    def http_proxy_changed(self, e):
        if not self.configuration.same_proxy:
            return
        if e == self.http_proxy:
            [w.set_text(self.http_proxy.get_text()) for w in self.same_proxy_addresses]
        else:
            [w.set_text(self.http_proxy_port.get_text()) for w in self.same_proxy_ports]

    def proxy_address_focus_out_event(self, w, direction):
        text = w.get_text()
        if not text:
            return False
        if text.find("//") == -1:
            w.set_text("http://" + text)
        return False

    def set_test_proxy_state(self, state):
        if self.test_proxy_state == state:
            return
        [self.proxy_table.remove(w) for w in self.test_gui_elements]
        if state == self.TEST_NETWORK_INITIAL:
            self.proxy_table.attach(self.test_network_button, 1, 2, 5, 6)
            self.test_network_button.show()
        elif state == self.TEST_NETWORK_RUNNING:
            self.test_proxy_progress.set_rcstyle("running")
            self.test_proxy_progress.set_text("Testing network configuration")
            self.proxy_table.attach(self.test_proxy_progress, 0, 5, 5, 6, xpadding=4)
            self.test_proxy_progress.show()
        else: # passed or failed
            self.dummy_progress.update(1.0)
            if state == self.TEST_NETWORK_PASSED:
                self.dummy_progress.set_text("Your network is properly configured")
                self.dummy_progress.set_rcstyle("running")
            else:
                self.dummy_progress.set_text("Network test failed")
                self.dummy_progress.set_rcstyle("fail")
            self.proxy_table.attach(self.dummy_progress, 0, 4, 5, 6)
            self.proxy_table.attach(self.retest_network_button, 4, 5, 5, 6, xpadding=4)
            self.dummy_progress.show()
            self.retest_network_button.show()
        self.test_proxy_state = state

    def create_network_page(self):
        advanced_vbox = gtk.VBox(False, 6)
        advanced_vbox.set_border_width(6)
        self.same_proxy_addresses = []
        self.same_proxy_ports = []
        self.all_proxy_ports = []
        self.all_proxy_addresses = []

        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = self.gen_label_widget("<span weight=\"bold\">Set the proxies used when fetching source code</span>")
        tooltip = "Set the proxies used when fetching source code.  A blank field uses a direct internet connection."
        info = HobInfoButton(tooltip, self)
        hbox = gtk.HBox(False, 12)
        hbox.pack_start(label, expand=True, fill=True)
        hbox.pack_start(info, expand=False, fill=False)
        sub_vbox.pack_start(hbox, expand=False, fill=False)

        proxy_test_focus = []
        self.direct_checkbox = gtk.RadioButton(None, "Direct network connection")
        proxy_test_focus.append(self.direct_checkbox)
        self.direct_checkbox.set_tooltip_text("Check this box to use a direct internet connection with no proxy")
        self.direct_checkbox.set_active(not self.configuration.enable_proxy)
        sub_vbox.pack_start(self.direct_checkbox, expand=False, fill=False)

        self.proxy_checkbox = gtk.RadioButton(self.direct_checkbox, "Manual proxy configuration")
        proxy_test_focus.append(self.proxy_checkbox)
        self.proxy_checkbox.set_tooltip_text("Check this box to manually set up a specific proxy")
        self.proxy_checkbox.set_active(self.configuration.enable_proxy)
        sub_vbox.pack_start(self.proxy_checkbox, expand=False, fill=False)

        self.same_checkbox = gtk.CheckButton("Use the HTTP proxy for all protocols")
        proxy_test_focus.append(self.same_checkbox)
        self.same_checkbox.set_tooltip_text("Check this box to use the HTTP proxy for all five proxies")
        self.same_checkbox.set_active(self.configuration.same_proxy)
        hbox = gtk.HBox(False, 12)
        hbox.pack_start(self.same_checkbox, expand=False, fill=False, padding=24)
        sub_vbox.pack_start(hbox, expand=False, fill=False)

        self.proxy_table = gtk.Table(6, 5, False)
        self.http_proxy, self.http_proxy_port, self.http_proxy_details = self.gen_proxy_entry_widget(
            "http", self, True, 0)
        proxy_test_focus +=[self.http_proxy, self.http_proxy_port]
        self.http_proxy.connect("changed", self.http_proxy_changed)
        self.http_proxy_port.connect("changed", self.http_proxy_changed)

        self.https_proxy, self.https_proxy_port, self.https_proxy_details = self.gen_proxy_entry_widget(
            "https", self, True, 1)
        proxy_test_focus += [self.https_proxy, self.https_proxy_port]
        self.same_proxy_addresses.append(self.https_proxy)
        self.same_proxy_ports.append(self.https_proxy_port)

        self.ftp_proxy, self.ftp_proxy_port, self.ftp_proxy_details = self.gen_proxy_entry_widget(
            "ftp", self, True, 2)
        proxy_test_focus += [self.ftp_proxy, self.ftp_proxy_port]
        self.same_proxy_addresses.append(self.ftp_proxy)
        self.same_proxy_ports.append(self.ftp_proxy_port)

        self.git_proxy, self.git_proxy_port, self.git_proxy_details = self.gen_proxy_entry_widget(
            "git", self, True, 3)
        proxy_test_focus += [self.git_proxy, self.git_proxy_port]
        self.same_proxy_addresses.append(self.git_proxy)
        self.same_proxy_ports.append(self.git_proxy_port)

        self.cvs_proxy, self.cvs_proxy_port, self.cvs_proxy_details = self.gen_proxy_entry_widget(
            "cvs", self, True, 4)
        proxy_test_focus += [self.cvs_proxy, self.cvs_proxy_port]
        self.same_proxy_addresses.append(self.cvs_proxy)
        self.same_proxy_ports.append(self.cvs_proxy_port)
        self.all_proxy_ports = self.same_proxy_ports + [self.http_proxy_port]
        self.all_proxy_addresses = self.same_proxy_addresses + [self.http_proxy]
        sub_vbox.pack_start(self.proxy_table, expand=False, fill=False)
        self.proxy_table.show_all()

        # Create the graphical elements for the network test feature, but don't display them yet
        self.test_network_button = HobAltButton("Test network configuration")
        self.test_network_button.connect("clicked", self.test_network_button_cb)
        self.test_proxy_progress = HobProgressBar()
        self.dummy_progress = HobProgressBar()
        self.retest_network_button = HobAltButton("Retest")
        self.retest_network_button.connect("clicked", self.test_network_button_cb)
        self.test_gui_elements = [self.test_network_button, self.test_proxy_progress, self.dummy_progress, self.retest_network_button]
        # Initialize the network tester
        self.test_proxy_state = self.TEST_NETWORK_NONE
        self.set_test_proxy_state(self.TEST_NETWORK_INITIAL)
        self.proxy_test_passed_id = self.handler.connect("network-passed", lambda h:self.test_proxy_ended(True))
        self.proxy_test_failed_id = self.handler.connect("network-failed", lambda h:self.test_proxy_ended(False))
        [w.connect("focus-in-event", self.test_proxy_focus_event) for w in proxy_test_focus]
        [w.connect("focus-out-event", self.proxy_address_focus_out_event) for w in self.all_proxy_addresses]

        self.direct_checkbox.connect("toggled", self.proxy_checkbox_toggled_cb)
        self.proxy_checkbox.connect("toggled", self.proxy_checkbox_toggled_cb)
        self.same_checkbox.connect("toggled", self.same_checkbox_toggled_cb)

        self.refresh_proxy_components()
        return advanced_vbox

    def switch_to_page(self, page_id):
        self.nb.set_current_page(page_id)

    def details_cb(self, button, parent, protocol):
        self.save_proxy_data()
        dialog = ProxyDetailsDialog(title = protocol.upper() + " Proxy Details",
            user = self.configuration.proxies[protocol][1],
            passwd = self.configuration.proxies[protocol][2],
            parent = parent,
            flags = gtk.DIALOG_MODAL
                    | gtk.DIALOG_DESTROY_WITH_PARENT
                    | gtk.DIALOG_NO_SEPARATOR)
        dialog.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.configuration.proxies[protocol][1] = dialog.user
            self.configuration.proxies[protocol][2] = dialog.passwd
            self.refresh_proxy_components()
        dialog.destroy()    

    def rootfs_combo_changed_cb(self, rootfs_combo, all_package_format, check_hbox):
        combo_item = self.rootfs_combo.get_active_text()
        for child in check_hbox.get_children():
            if isinstance(child, gtk.CheckButton):
                check_hbox.remove(child)
        for format in all_package_format:
            if format != combo_item:
                check_button = gtk.CheckButton(format)
                check_hbox.pack_start(check_button, expand=False, fill=False)
        check_hbox.show_all()

    def gen_pkgfmt_widget(self, curr_package_format, all_package_format, tooltip_combo="", tooltip_extra=""):
        pkgfmt_hbox = gtk.HBox(False, 24)

        rootfs_vbox = gtk.VBox(False, 6)
        pkgfmt_hbox.pack_start(rootfs_vbox, expand=False, fill=False)

        label = self.gen_label_widget("Root file system package format")
        rootfs_vbox.pack_start(label, expand=False, fill=False)

        rootfs_format = ""
        if curr_package_format:
            rootfs_format = curr_package_format.split()[0]

        rootfs_format_widget, rootfs_combo = self.gen_combo_widget(rootfs_format, all_package_format, tooltip_combo)
        rootfs_vbox.pack_start(rootfs_format_widget, expand=False, fill=False)

        extra_vbox = gtk.VBox(False, 6)
        pkgfmt_hbox.pack_start(extra_vbox, expand=False, fill=False)

        label = self.gen_label_widget("Additional package formats")
        extra_vbox.pack_start(label, expand=False, fill=False)

        check_hbox = gtk.HBox(False, 12)
        extra_vbox.pack_start(check_hbox, expand=False, fill=False)
        for format in all_package_format:
            if format != rootfs_format:
                check_button = gtk.CheckButton(format)
                is_active = (format in curr_package_format.split())
                check_button.set_active(is_active)
                check_hbox.pack_start(check_button, expand=False, fill=False)

        info = HobInfoButton(tooltip_extra, self)
        check_hbox.pack_end(info, expand=False, fill=False)

        rootfs_combo.connect("changed", self.rootfs_combo_changed_cb, all_package_format, check_hbox)

        pkgfmt_hbox.show_all()

        return pkgfmt_hbox, rootfs_combo, check_hbox

    def editable_settings_cell_edited(self, cell, path_string, new_text, model):
        it = model.get_iter_from_string(path_string)
        column = cell.get_data("column")
        model.set(it, column, new_text)

    def editable_settings_add_item_clicked(self, button, model):
        new_item = ["##KEY##", "##VALUE##"]

        iter = model.append()
        model.set (iter,
            0, new_item[0],
            1, new_item[1],
       )

    def editable_settings_remove_item_clicked(self, button, treeview):
        selection = treeview.get_selection()
        model, iter = selection.get_selected()

        if iter:
            path = model.get_path(iter)[0]
            model.remove(iter)
 
    def gen_editable_settings(self, setting, tooltip=""):
        setting_hbox = gtk.HBox(False, 12)

        vbox = gtk.VBox(False, 12)
        setting_hbox.pack_start(vbox, expand=True, fill=True)

        setting_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        for key in setting.keys():
            setting_store.set(setting_store.append(), 0, key, 1, setting[key])

        setting_tree = gtk.TreeView(setting_store)
        setting_tree.set_headers_visible(True)
        setting_tree.set_size_request(300, 100)

        col = gtk.TreeViewColumn('Key')
        col.set_min_width(100)
        col.set_max_width(150)
        col.set_resizable(True)
        col1 = gtk.TreeViewColumn('Value')
        col1.set_min_width(100)
        col1.set_max_width(150)
        col1.set_resizable(True)
        setting_tree.append_column(col)
        setting_tree.append_column(col1)
        cell = gtk.CellRendererText()
        cell.set_property('width-chars', 10)
        cell.set_property('editable', True)
        cell.set_data("column", 0)
        cell.connect("edited", self.editable_settings_cell_edited, setting_store)
        cell1 = gtk.CellRendererText()
        cell1.set_property('width-chars', 10)
        cell1.set_property('editable', True)
        cell1.set_data("column", 1)
        cell1.connect("edited", self.editable_settings_cell_edited, setting_store)
        col.pack_start(cell, True)
        col1.pack_end(cell1, True)
        col.set_attributes(cell, text=0)
        col1.set_attributes(cell1, text=1)

        scroll = gtk.ScrolledWindow()
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(setting_tree)
        vbox.pack_start(scroll, expand=True, fill=True)

        # some buttons
        hbox = gtk.HBox(True, 6)
        vbox.pack_start(hbox, False, False)

        button = gtk.Button(stock=gtk.STOCK_ADD)
        button.connect("clicked", self.editable_settings_add_item_clicked, setting_store)
        hbox.pack_start(button)

        button = gtk.Button(stock=gtk.STOCK_REMOVE)
        button.connect("clicked", self.editable_settings_remove_item_clicked, setting_tree)
        hbox.pack_start(button)

        info = HobInfoButton(tooltip, self)
        setting_hbox.pack_start(info, expand=False, fill=False)

        return setting_hbox, setting_store

    def create_others_page(self):
        advanced_vbox = gtk.VBox(False, 6)
        advanced_vbox.set_border_width(6)

        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=True, fill=True)
        label = self.gen_label_widget("<span weight=\"bold\">Add your own variables:</span>")
        tooltip = "These are key/value pairs for your extra settings. Click \'Add\' and then directly edit the key and the value"
        setting_widget, self.setting_store = self.gen_editable_settings(self.configuration.extra_setting, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(setting_widget, expand=True, fill=True)

        return advanced_vbox

    def create_visual_elements(self):
        self.nb = gtk.Notebook()
        self.nb.set_show_tabs(True)        
        self.nb.append_page(self.create_build_environment_page(), gtk.Label("Build environment"))
        self.nb.append_page(self.create_shared_state_page(), gtk.Label("Shared state"))
        self.nb.append_page(self.create_network_page(), gtk.Label("Network"))        
        self.nb.append_page(self.create_others_page(), gtk.Label("Others"))
        self.nb.set_current_page(0)
        self.vbox.pack_start(self.nb, expand=True, fill=True)
        self.vbox.pack_end(gtk.HSeparator(), expand=True, fill=True)

        self.show_all()

    def destroy(self):
        self.handler.disconnect(self.proxy_test_passed_id)
        self.handler.disconnect(self.proxy_test_failed_id)
        super(SimpleSettingsDialog, self).destroy()

    def scroll_changed(self, widget, event, data=None):
        adj = widget.get_vadjustment()
        adj.set_value(adj.upper - adj.page_size)

#
# AdvancedSettings Dialog
#
class AdvancedSettingDialog (CrumbsDialog, SettingsUIHelper):
    
    def details_cb(self, button, parent, protocol):
        dialog = ProxyDetailsDialog(title = protocol.upper() + " Proxy Details",
            user = self.configuration.proxies[protocol][1],
            passwd = self.configuration.proxies[protocol][2],
            parent = parent,
            flags = gtk.DIALOG_MODAL
                    | gtk.DIALOG_DESTROY_WITH_PARENT
                    | gtk.DIALOG_NO_SEPARATOR)
        dialog.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.configuration.proxies[protocol][1] = dialog.user
            self.configuration.proxies[protocol][2] = dialog.passwd
            self.refresh_proxy_components()
        dialog.destroy()

    def set_save_button(self, button):
        self.save_button = button

    def rootfs_combo_changed_cb(self, rootfs_combo, all_package_format, check_hbox):
        combo_item = self.rootfs_combo.get_active_text()
        modified = False
        for child in check_hbox.get_children():
            if isinstance(child, gtk.CheckButton):
                check_hbox.remove(child)
                modified = True
        for format in all_package_format:
            if format != combo_item:
                check_button = gtk.CheckButton(format)
                check_hbox.pack_start(check_button, expand=False, fill=False)
                modified = True
        if modified:
            check_hbox.remove(self.pkgfmt_info)
            check_hbox.pack_start(self.pkgfmt_info, expand=False, fill=False)
        check_hbox.show_all()

    def gen_pkgfmt_widget(self, curr_package_format, all_package_format, tooltip_combo="", tooltip_extra=""):
        pkgfmt_vbox = gtk.VBox(False, 6)

        label = self.gen_label_widget("Root file system package format")
        pkgfmt_vbox.pack_start(label, expand=False, fill=False)

        rootfs_format = ""
        if curr_package_format:
            rootfs_format = curr_package_format.split()[0]

        rootfs_format_widget, rootfs_combo = self.gen_combo_widget(rootfs_format, all_package_format, tooltip_combo)
        pkgfmt_vbox.pack_start(rootfs_format_widget, expand=False, fill=False)

        label = self.gen_label_widget("Additional package formats")
        pkgfmt_vbox.pack_start(label, expand=False, fill=False)

        check_hbox = gtk.HBox(False, 12)
        pkgfmt_vbox.pack_start(check_hbox, expand=False, fill=False)
        for format in all_package_format:
            if format != rootfs_format:
                check_button = gtk.CheckButton(format)
                is_active = (format in curr_package_format.split())
                check_button.set_active(is_active)
                check_hbox.pack_start(check_button, expand=False, fill=False)

        self.pkgfmt_info = HobInfoButton(tooltip_extra, self)
        check_hbox.pack_start(self.pkgfmt_info, expand=False, fill=False)

        rootfs_combo.connect("changed", self.rootfs_combo_changed_cb, all_package_format, check_hbox)

        pkgfmt_vbox.show_all()

        return pkgfmt_vbox, rootfs_combo, check_hbox

    def __init__(self, title, configuration, all_image_types,
            all_package_formats, all_distros, all_sdk_machines,
            max_threads, parent, flags, buttons=None):
        super(AdvancedSettingDialog, self).__init__(title, parent, flags, buttons)

        # class members from other objects
        # bitbake settings from Builder.Configuration
        self.configuration = configuration
        self.image_types = all_image_types
        self.all_package_formats = all_package_formats
        self.all_distros = all_distros[:]
        self.all_sdk_machines = all_sdk_machines
        self.max_threads = max_threads

        # class members for internal use
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
        self.image_types_checkbuttons = {}

        self.md5 = self.config_md5()
        self.settings_changed = False

        # create visual elements on the dialog
        self.save_button = None
        self.create_visual_elements()
        self.connect("response", self.response_cb)

    def _get_sorted_value(self, var):
        return " ".join(sorted(str(var).split())) + "\n"

    def config_md5(self):
        data = ""
        data += ("PACKAGE_CLASSES: "      + self.configuration.curr_package_format + '\n')
        data += ("DISTRO: "               + self._get_sorted_value(self.configuration.curr_distro))
        data += ("IMAGE_ROOTFS_SIZE: "    + self._get_sorted_value(self.configuration.image_rootfs_size))
        data += ("IMAGE_EXTRA_SIZE: "     + self._get_sorted_value(self.configuration.image_extra_size))
        data += ("INCOMPATIBLE_LICENSE: " + self._get_sorted_value(self.configuration.incompat_license))
        data += ("SDK_MACHINE: "          + self._get_sorted_value(self.configuration.curr_sdk_machine))
        data += ("TOOLCHAIN_BUILD: "      + self._get_sorted_value(self.configuration.toolchain_build))
        data += ("IMAGE_FSTYPES: "        + self._get_sorted_value(self.configuration.image_fstypes))
        return hashlib.md5(data).hexdigest()

    def create_visual_elements(self):
        self.nb = gtk.Notebook()
        self.nb.set_show_tabs(True)
        self.nb.append_page(self.create_image_types_page(), gtk.Label("Image types"))
        self.nb.append_page(self.create_output_page(), gtk.Label("Output"))
        self.nb.set_current_page(0)
        self.vbox.pack_start(self.nb, expand=True, fill=True)
        self.vbox.pack_end(gtk.HSeparator(), expand=True, fill=True)

        self.show_all()

    def get_num_checked_image_types(self):
        total = 0
        for b in self.image_types_checkbuttons.values():
            if b.get_active():
              total = total + 1
        return total

    def set_save_button_state(self):
        if self.save_button:
            self.save_button.set_sensitive(self.get_num_checked_image_types() > 0)

    def image_type_checkbutton_clicked_cb(self, button):
        self.set_save_button_state()
        if self.get_num_checked_image_types() == 0:
            # Show an error dialog
            lbl = "<b>Select an image type</b>\n\nYou need to select at least one image type."
            dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_WARNING)
            button = dialog.add_button("OK", gtk.RESPONSE_OK)
            HobButton.style_button(button)
            response = dialog.run()
            dialog.destroy()

    def create_image_types_page(self):
        main_vbox = gtk.VBox(False, 16)
        main_vbox.set_border_width(6)

        advanced_vbox = gtk.VBox(False, 6)
        advanced_vbox.set_border_width(6)

        distro_vbox = gtk.VBox(False, 6)        
        label = self.gen_label_widget("Distro:")
        tooltip = "Selects the Yocto Project distribution you want"
        try:
            i = self.all_distros.index( "defaultsetup" )
        except ValueError:
            i = -1
        if i != -1:
            self.all_distros[ i ] = "Default"
            if self.configuration.curr_distro == "defaultsetup":
                self.configuration.curr_distro = "Default"
        distro_widget, self.distro_combo = self.gen_combo_widget(self.configuration.curr_distro, self.all_distros, tooltip)
        distro_vbox.pack_start(label, expand=False, fill=False)
        distro_vbox.pack_start(distro_widget, expand=False, fill=False)
        main_vbox.pack_start(distro_vbox, expand=False, fill=False)


        rows = (len(self.image_types)+1)/3
        table = gtk.Table(rows + 1, 10, True)
        advanced_vbox.pack_start(table, expand=False, fill=False)

        tooltip = "Image file system types you want."
        info = HobInfoButton(tooltip, self)
        label = self.gen_label_widget("Image types:")
        align = gtk.Alignment(0, 0.5, 0, 0)
        table.attach(align, 0, 4, 0, 1)
        align.add(label)
        table.attach(info, 4, 5, 0, 1)

        i = 1
        j = 1
        for image_type in sorted(self.image_types):
            self.image_types_checkbuttons[image_type] = gtk.CheckButton(image_type)
            self.image_types_checkbuttons[image_type].connect("toggled", self.image_type_checkbutton_clicked_cb)
            article = ""
            if image_type.startswith(("a", "e", "i", "o", "u")):
                article = "n"
            self.image_types_checkbuttons[image_type].set_tooltip_text("Build a%s %s image" % (article, image_type))
            table.attach(self.image_types_checkbuttons[image_type], j - 1, j + 3, i, i + 1)
            if image_type in self.configuration.image_fstypes.split():
                self.image_types_checkbuttons[image_type].set_active(True)
            i += 1
            if i > rows:
                i = 1
                j = j + 4

        main_vbox.pack_start(advanced_vbox, expand=False, fill=False)
        self.set_save_button_state()
        
        return main_vbox

    def create_output_page(self):
        advanced_vbox = gtk.VBox(False, 6)
        advanced_vbox.set_border_width(6)

        advanced_vbox.pack_start(self.gen_label_widget('<span weight="bold">Package format</span>'), expand=False, fill=False)
        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        tooltip_combo = "Selects the package format used to generate rootfs."
        tooltip_extra = "Selects extra package formats to build"
        pkgfmt_widget, self.rootfs_combo, self.check_hbox = self.gen_pkgfmt_widget(self.configuration.curr_package_format, self.all_package_formats, tooltip_combo, tooltip_extra)
        sub_vbox.pack_start(pkgfmt_widget, expand=False, fill=False)

        advanced_vbox.pack_start(self.gen_label_widget('<span weight="bold">Image size</span>'), expand=False, fill=False)
        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = self.gen_label_widget("Image basic size (in MB)")
        tooltip = "Sets the basic size of your target image.\nThis is the basic size of your target image unless your selected package size exceeds this value or you select \'Image Extra Size\'."
        rootfs_size_widget, self.rootfs_size_spinner = self.gen_spinner_widget(int(self.configuration.image_rootfs_size*1.0/1024), 0, 65536, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(rootfs_size_widget, expand=False, fill=False)

        sub_vbox = gtk.VBox(False, 6)
        advanced_vbox.pack_start(sub_vbox, expand=False, fill=False)
        label = self.gen_label_widget("Additional free space (in MB)")
        tooltip = "Sets the extra free space of your target image.\nBy default, the system reserves 30% of your image size as free space. If your image contains zypper, it brings in 50MB more space. The maximum free space is 64GB."
        extra_size_widget, self.extra_size_spinner = self.gen_spinner_widget(int(self.configuration.image_extra_size*1.0/1024), 0, 65536, tooltip)
        sub_vbox.pack_start(label, expand=False, fill=False)
        sub_vbox.pack_start(extra_size_widget, expand=False, fill=False)

        advanced_vbox.pack_start(self.gen_label_widget('<span weight="bold">Licensing</span>'), expand=False, fill=False)
        self.gplv3_checkbox = gtk.CheckButton("Exclude GPLv3 packages")
        self.gplv3_checkbox.set_tooltip_text("Check this box to prevent GPLv3 packages from being included in your image")
        if "GPLv3" in self.configuration.incompat_license.split():
            self.gplv3_checkbox.set_active(True)
        else:
            self.gplv3_checkbox.set_active(False)
        advanced_vbox.pack_start(self.gplv3_checkbox, expand=False, fill=False)

        advanced_vbox.pack_start(self.gen_label_widget('<span weight="bold">Toolchain</span>'), expand=False, fill=False)
        sub_hbox = gtk.HBox(False, 6)
        advanced_vbox.pack_start(sub_hbox, expand=False, fill=False)
        self.toolchain_checkbox = gtk.CheckButton("Build toolchain")
        self.toolchain_checkbox.set_tooltip_text("Check this box to build the related toolchain with your image")
        self.toolchain_checkbox.set_active(self.configuration.toolchain_build)
        sub_hbox.pack_start(self.toolchain_checkbox, expand=False, fill=False)

        tooltip = "Selects the host platform for which you want to run the toolchain"
        sdk_machine_widget, self.sdk_machine_combo = self.gen_combo_widget(self.configuration.curr_sdk_machine, self.all_sdk_machines, tooltip)
        sub_hbox.pack_start(sdk_machine_widget, expand=False, fill=False)

        return advanced_vbox

    def response_cb(self, dialog, response_id):
        package_format = []
        package_format.append(self.rootfs_combo.get_active_text())
        for child in self.check_hbox:
            if isinstance(child, gtk.CheckButton) and child.get_active():
                package_format.append(child.get_label())
        self.configuration.curr_package_format = " ".join(package_format)

        distro = self.distro_combo.get_active_text()
        if distro == "Default":
            distro = "defaultsetup"
        self.configuration.curr_distro = distro
        self.configuration.image_rootfs_size = self.rootfs_size_spinner.get_value_as_int() * 1024
        self.configuration.image_extra_size = self.extra_size_spinner.get_value_as_int() * 1024

        self.configuration.image_fstypes = ""
        for image_type in self.image_types:
            if self.image_types_checkbuttons[image_type].get_active():
                self.configuration.image_fstypes += (" " + image_type)
        self.configuration.image_fstypes.strip()

        if self.gplv3_checkbox.get_active():
            if "GPLv3" not in self.configuration.incompat_license.split():
                self.configuration.incompat_license += " GPLv3"
        else:
            if "GPLv3" in self.configuration.incompat_license.split():
                self.configuration.incompat_license = self.configuration.incompat_license.split().remove("GPLv3")
                self.configuration.incompat_license = " ".join(self.configuration.incompat_license or [])
        self.configuration.incompat_license = self.configuration.incompat_license.strip()

        self.configuration.toolchain_build = self.toolchain_checkbox.get_active()
        self.configuration.curr_sdk_machine = self.sdk_machine_combo.get_active_text()
        md5 = self.config_md5()
        self.settings_changed = (self.md5 != md5)

#
# DeployImageDialog
#
class DeployImageDialog (CrumbsDialog):

    __dummy_usb__ = "--select a usb drive--"

    def __init__(self, title, image_path, parent, flags, buttons=None, standalone=False):
        super(DeployImageDialog, self).__init__(title, parent, flags, buttons)

        self.image_path = image_path
        self.standalone = standalone

        self.create_visual_elements()
        self.connect("response", self.response_cb)

    def create_visual_elements(self):
        self.set_size_request(600, 400)
        label = gtk.Label()
        label.set_alignment(0.0, 0.5)
        markup = "<span font_desc='12'>The image to be written into usb drive:</span>"
        label.set_markup(markup)
        self.vbox.pack_start(label, expand=False, fill=False, padding=2)

        table = gtk.Table(2, 10, False)
        table.set_col_spacings(5)
        table.set_row_spacings(5)
        self.vbox.pack_start(table, expand=True, fill=True)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        tv = gtk.TextView()
        tv.set_editable(False)
        tv.set_wrap_mode(gtk.WRAP_WORD)
        tv.set_cursor_visible(False)
        self.buf = gtk.TextBuffer()
        self.buf.set_text(self.image_path)
        tv.set_buffer(self.buf)
        scroll.add(tv)
        table.attach(scroll, 0, 10, 0, 1)

        # There are 2 ways to use DeployImageDialog
        # One way is that called by HOB when the 'Deploy Image' button is clicked
        # The other way is that called by a standalone script.
        # Following block of codes handles the latter way. It adds a 'Select Image' button and
        # emit a signal when the button is clicked.
        if self.standalone:
                gobject.signal_new("select_image_clicked", self, gobject.SIGNAL_RUN_FIRST,
                                   gobject.TYPE_NONE, ())
                icon = gtk.Image()
                pix_buffer = gtk.gdk.pixbuf_new_from_file(hic.ICON_IMAGES_DISPLAY_FILE)
                icon.set_from_pixbuf(pix_buffer)
                button = gtk.Button("Select Image")
                button.set_image(icon)
                #button.set_size_request(140, 50)
                table.attach(button, 9, 10, 1, 2, gtk.FILL, 0, 0, 0)
                button.connect("clicked", self.select_image_button_clicked_cb)

        separator = gtk.HSeparator()
        self.vbox.pack_start(separator, expand=False, fill=False, padding=10)

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
        self.vbox.pack_start(self.usb_combo, expand=False, fill=False)
        self.vbox.pack_start(self.usb_desc, expand=False, fill=False, padding=2)

        self.progress_bar = HobProgressBar()
        self.vbox.pack_start(self.progress_bar, expand=False, fill=False)
        separator = gtk.HSeparator()
        self.vbox.pack_start(separator, expand=False, fill=True, padding=10)

        self.vbox.show_all()
        self.progress_bar.hide()

    def set_image_text_buffer(self, image_path):
        self.buf.set_text(image_path)

    def set_image_path(self, image_path):
        self.image_path = image_path

    def popen_read(self, cmd):
        tmpout, errors = bb.process.run("%s" % cmd)
        return tmpout.strip()

    def find_all_usb_devices(self):
        usb_devs = [ os.readlink(u)
            for u in glob.glob('/dev/disk/by-id/usb*')
            if not re.search(r'part\d+', u) ]
        return [ '%s' % u[u.rfind('/')+1:] for u in usb_devs ]

    def get_usb_info(self, dev):
        return "%s %s" % \
            (self.popen_read('cat /sys/class/block/%s/device/vendor' % dev),
            self.popen_read('cat /sys/class/block/%s/device/model' % dev))

    def select_image_button_clicked_cb(self, button):
            self.emit('select_image_clicked')

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
            lbl = ''
            combo_item = self.usb_combo.get_active_text()
            if combo_item and combo_item != self.__dummy_usb__ and self.image_path:
                cmdline = bb.ui.crumbs.utils.which_terminal()
                if cmdline:
                    tmpfile = tempfile.NamedTemporaryFile()
                    cmdline += "\"sudo dd if=" + self.image_path + \
                                " of=" + combo_item + "; echo $? > " + tmpfile.name + "\""
                    subprocess.call(shlex.split(cmdline))

                    if int(tmpfile.readline().strip()) == 0:
                        lbl = "<b>Deploy image successfully.</b>"
                    else:
                        lbl = "<b>Failed to deploy image.</b>\nPlease check image <b>%s</b> exists and USB device <b>%s</b> is writable." % (self.image_path, combo_item)
                    tmpfile.close()
            else:
                if not self.image_path:
                    lbl = "<b>No selection made.</b>\nYou have not selected an image to deploy."
                else:
                    lbl = "<b>No selection made.</b>\nYou have not selected a USB device."
            if len(lbl):
                crumbs_dialog = CrumbsMessageDialog(self, lbl, gtk.STOCK_DIALOG_INFO)
                button = crumbs_dialog.add_button("Close", gtk.RESPONSE_OK)
                HobButton.style_button(button)
                crumbs_dialog.run()
                crumbs_dialog.destroy()

    def update_progress_bar(self, title, fraction, status=None):
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

class CellRendererPixbufActivatable(gtk.CellRendererPixbuf):
    """
    A custom CellRenderer implementation which is activatable
    so that we can handle user clicks
    """
    __gsignals__    = { 'clicked' : (gobject.SIGNAL_RUN_LAST,
                                     gobject.TYPE_NONE,
                                     (gobject.TYPE_STRING,)), }

    def __init__(self):
        gtk.CellRendererPixbuf.__init__(self)
        self.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
        self.set_property('follow-state', True)

    """
    Respond to a user click on a cell
    """
    def do_activate(self, even, widget, path, background_area, cell_area, flags):
        self.emit('clicked', path)

#
# LayerSelectionDialog
#
class LayerSelectionDialog (CrumbsDialog):

    def gen_label_widget(self, content):
        label = gtk.Label()
        label.set_alignment(0, 0)
        label.set_markup(content)
        label.show()
        return label

    def layer_widget_toggled_cb(self, cell, path, layer_store):
        name = layer_store[path][0]
        toggle = not layer_store[path][1]
        layer_store[path][1] = toggle

    def layer_widget_add_clicked_cb(self, action, layer_store, parent):
        dialog = gtk.FileChooserDialog("Add new layer", parent,
                                       gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Open", gtk.RESPONSE_YES)
        HobButton.style_button(button)
        label = gtk.Label("Select the layer you wish to add")
        label.show()
        dialog.set_extra_widget(label)
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()

        lbl = "<b>Error</b>\nUnable to load layer <i>%s</i> because " % path
        if response == gtk.RESPONSE_YES:
            import os
            import os.path
            layers = []
            it = layer_store.get_iter_first()
            while it:
                layers.append(layer_store.get_value(it, 0))
                it = layer_store.iter_next(it)

            if not path:
                lbl += "it is an invalid path."
            elif not os.path.exists(path+"/conf/layer.conf"):
                lbl += "there is no layer.conf inside the directory."
            elif path in layers:
                lbl += "it is already in loaded layers."
            else:
                layer_store.append([path])
                return
            dialog = CrumbsMessageDialog(parent, lbl)
            dialog.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
            response = dialog.run()
            dialog.destroy()

    def layer_widget_del_clicked_cb(self, action, tree_selection, layer_store):
        model, iter = tree_selection.get_selected()
        if iter:
            layer_store.remove(iter)


    def gen_layer_widget(self, layers, layers_avail, window, tooltip=""):
        hbox = gtk.HBox(False, 6)

        layer_tv = gtk.TreeView()
        layer_tv.set_rules_hint(True)
        layer_tv.set_headers_visible(False)
        tree_selection = layer_tv.get_selection()
        tree_selection.set_mode(gtk.SELECTION_NONE)

        col0= gtk.TreeViewColumn('Path')
        cell0 = gtk.CellRendererText()
        cell0.set_padding(5,2)
        col0.pack_start(cell0, True)
        col0.set_cell_data_func(cell0, self.draw_layer_path_cb)
        layer_tv.append_column(col0)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(layer_tv)

        table_layer = gtk.Table(2, 10, False)
        hbox.pack_start(table_layer, expand=True, fill=True)

        table_layer.attach(scroll, 0, 10, 0, 1)

        layer_store = gtk.ListStore(gobject.TYPE_STRING)
        for layer in layers:
            layer_store.append([layer])

        col1 = gtk.TreeViewColumn('Enabled')
        layer_tv.append_column(col1)

        cell1 = CellRendererPixbufActivatable()
        cell1.set_fixed_size(-1,35)
        cell1.connect("clicked", self.del_cell_clicked_cb, layer_store)
        col1.pack_start(cell1, True)
        col1.set_cell_data_func(cell1, self.draw_delete_button_cb, layer_tv)

        add_button = gtk.Button()
        add_button.set_relief(gtk.RELIEF_NONE)
        box = gtk.HBox(False, 6)
        box.show()
        add_button.add(box)
        add_button.connect("enter-notify-event", self.add_hover_cb)
        add_button.connect("leave-notify-event", self.add_leave_cb)
        self.im = gtk.Image()
        self.im.set_from_file(hic.ICON_INDI_ADD_FILE)
        self.im.show()
        box.pack_start(self.im, expand=False, fill=False, padding=6)
        lbl = gtk.Label("Add layer")
        lbl.set_alignment(0.0, 0.5)
        lbl.show()
        box.pack_start(lbl, expand=True, fill=True, padding=6)
        add_button.connect("clicked", self.layer_widget_add_clicked_cb, layer_store, window)
        table_layer.attach(add_button, 0, 10, 1, 2, gtk.EXPAND | gtk.FILL, 0, 0, 6)
        layer_tv.set_model(layer_store)

        hbox.show_all()

        return hbox, layer_store

    def add_hover_cb(self, button, event):
        self.im.set_from_file(hic.ICON_INDI_ADD_HOVER_FILE)

    def add_leave_cb(self, button, event):
        self.im.set_from_file(hic.ICON_INDI_ADD_FILE)

    def __init__(self, title, layers, all_layers, parent, flags, buttons=None):
        super(LayerSelectionDialog, self).__init__(title, parent, flags, buttons)

        # class members from other objects
        self.layers = layers
        self.all_layers = all_layers
        self.layers_changed = False

        # icon for remove button in TreeView
        im = gtk.Image()
        im.set_from_file(hic.ICON_INDI_REMOVE_FILE)
        self.rem_icon = im.get_pixbuf()

        # class members for internal use
        self.layer_store = None

        # create visual elements on the dialog
        self.create_visual_elements()
        self.connect("response", self.response_cb)

    def create_visual_elements(self):
        layer_widget, self.layer_store = self.gen_layer_widget(self.layers, self.all_layers, self, None)
        layer_widget.set_size_request(450, 250)
        self.vbox.pack_start(layer_widget, expand=True, fill=True)
        self.show_all()

    def response_cb(self, dialog, response_id):
        model = self.layer_store
        it = model.get_iter_first()
        layers = []
        while it:
            layers.append(model.get_value(it, 0))
            it = model.iter_next(it)

        self.layers_changed = (self.layers != layers)
        self.layers = layers

    """
    A custom cell_data_func to draw a delete 'button' in the TreeView for layers
    other than the meta layer. The deletion of which is prevented so that the
    user can't shoot themselves in the foot too badly.
    """
    def draw_delete_button_cb(self, col, cell, model, it, tv):
        path =  model.get_value(it, 0)
        # Trailing slashes are uncommon in bblayers.conf but confuse os.path.basename
        path.rstrip('/')
        name = os.path.basename(path)
        if name == "meta" or name == "meta-hob":
            cell.set_sensitive(False)
            cell.set_property('pixbuf', None)
            cell.set_property('mode', gtk.CELL_RENDERER_MODE_INERT)
        else:
            cell.set_property('pixbuf', self.rem_icon)
            cell.set_sensitive(True)
            cell.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)

        return True

    """
    A custom cell_data_func to write an extra message into the layer path cell
    for the meta layer. We should inform the user that they can't remove it for
    their own safety.
    """
    def draw_layer_path_cb(self, col, cell, model, it):
        path = model.get_value(it, 0)
        name = os.path.basename(path)
        if name == "meta":
            cell.set_property('markup', "<b>Core layer for images: it cannot be removed</b>\n%s" % path)
        elif name == "meta-hob":
            cell.set_property('markup', "<b>Core layer for Hob: it cannot be removed</b>\n%s" % path)
        else:
            cell.set_property('text', path)

    def del_cell_clicked_cb(self, cell, path, model):
        it = model.get_iter_from_string(path)
        model.remove(it)

class ImageSelectionDialog (CrumbsDialog):

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


    def __init__(self, image_folder, image_types, title, parent, flags, buttons=None, image_extension = {}):
        super(ImageSelectionDialog, self).__init__(title, parent, flags, buttons)
        self.connect("response", self.response_cb)

        self.image_folder = image_folder
        self.image_types  = image_types
        self.image_list = []
        self.image_names = []
        self.image_extension = image_extension

        # create visual elements on the dialog
        self.create_visual_elements()

        self.image_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        self.fill_image_store()

    def create_visual_elements(self):
        hbox = gtk.HBox(False, 6)

        self.vbox.pack_start(hbox, expand=False, fill=False)

        entry = gtk.Entry()
        entry.set_text(self.image_folder)
        table = gtk.Table(1, 10, True)
        table.set_size_request(560, -1)
        hbox.pack_start(table, expand=False, fill=False)
        table.attach(entry, 0, 9, 0, 1)
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
        open_button = gtk.Button()
        open_button.set_image(image)
        open_button.connect("clicked", self.select_path_cb, self, entry)
        table.attach(open_button, 9, 10, 0, 1)

        self.image_table = HobViewTable(self.__columns__)
        self.image_table.set_size_request(-1, 300)
        self.image_table.connect("toggled", self.toggled_cb)
        self.image_table.connect_group_selection(self.table_selected_cb)
        self.image_table.connect("row-activated", self.row_actived_cb)
        self.vbox.pack_start(self.image_table, expand=True, fill=True)

        self.show_all()

    def change_image_cb(self, model, path, columnid):
        if not model:
            return
        iter = model.get_iter_first()
        while iter:
            rowpath = model.get_path(iter)
            model[rowpath][columnid] = False
            iter = model.iter_next(iter)

        model[path][columnid] = True

    def toggled_cb(self, table, cell, path, columnid, tree):
        model = tree.get_model()
        self.change_image_cb(model, path, columnid)

    def table_selected_cb(self, selection):
        model, paths = selection.get_selected_rows()
        if paths:
            self.change_image_cb(model, paths[0], 1)

    def row_actived_cb(self, tab, model, path):
        self.change_image_cb(model, path, 1)
        self.emit('response', gtk.RESPONSE_YES)

    def select_path_cb(self, action, parent, entry):
        dialog = gtk.FileChooserDialog("", parent,
                                       gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        text = entry.get_text()
        dialog.set_current_folder(text if len(text) > 0 else os.getcwd())
        button = dialog.add_button("Cancel", gtk.RESPONSE_NO)
        HobAltButton.style_button(button)
        button = dialog.add_button("Open", gtk.RESPONSE_YES)
        HobButton.style_button(button)
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
                    if image_type in self.image_extension:
                        real_types = self.image_extension[image_type]
                    else:
                        real_types = [image_type]
                    for real_image_type in real_types:
                        if f.endswith('.' + real_image_type):
                            imageset.add(f.rsplit('.' + real_image_type)[0].rsplit('.rootfs')[0])
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

#
# ProxyDetailsDialog
#
class ProxyDetailsDialog (CrumbsDialog):

    def __init__(self, title, user, passwd, parent, flags, buttons=None):
        super(ProxyDetailsDialog, self).__init__(title, parent, flags, buttons)
        self.connect("response", self.response_cb)

        self.auth = not (user == None or passwd == None or user == "")
        self.user = user or ""
        self.passwd = passwd or ""

        # create visual elements on the dialog
        self.create_visual_elements()

    def create_visual_elements(self):
        self.auth_checkbox = gtk.CheckButton("Use authentication")
        self.auth_checkbox.set_tooltip_text("Check this box to set the username and the password")
        self.auth_checkbox.set_active(self.auth)
        self.auth_checkbox.connect("toggled", self.auth_checkbox_toggled_cb)
        self.vbox.pack_start(self.auth_checkbox, expand=False, fill=False)

        hbox = gtk.HBox(False, 6)
        self.user_label = gtk.Label("Username:")
        self.user_text = gtk.Entry()
        self.user_text.set_text(self.user)
        hbox.pack_start(self.user_label, expand=False, fill=False)
        hbox.pack_end(self.user_text, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)

        hbox = gtk.HBox(False, 6)
        self.passwd_label = gtk.Label("Password:")
        self.passwd_text = gtk.Entry()
        self.passwd_text.set_text(self.passwd)
        hbox.pack_start(self.passwd_label, expand=False, fill=False)
        hbox.pack_end(self.passwd_text, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)

        self.refresh_auth_components()
        self.show_all()

    def refresh_auth_components(self):
        self.user_label.set_sensitive(self.auth)
        self.user_text.set_editable(self.auth)
        self.user_text.set_sensitive(self.auth)
        self.passwd_label.set_sensitive(self.auth)
        self.passwd_text.set_editable(self.auth)
        self.passwd_text.set_sensitive(self.auth)

    def auth_checkbox_toggled_cb(self, button):
        self.auth = self.auth_checkbox.get_active()
        self.refresh_auth_components()

    def response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_OK:
            if self.auth:
                self.user = self.user_text.get_text()
                self.passwd = self.passwd_text.get_text()
            else:
                self.user = None
                self.passwd = None


#
# OpeningLogDialog
#
class OpeningLogDialog (CrumbsDialog):

    def __init__(self, title, parent, flags, buttons=None):
        super(OpeningLogDialog, self).__init__(title, parent, flags, buttons)

        self.running = False
        # create visual elements on the dialog
        self.create_visual_elements()

    def start(self):
        if not self.running:
          self.running = True
          gobject.timeout_add(100, self.pulse)

    def pulse(self):
        self.progress_bar.pulse()
        return self.running

    def create_visual_elements(self):
        hbox = gtk.HBox(False, 12)
        self.user_label = gtk.Label("The log will open in a text editor")
        hbox.pack_start(self.user_label, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)

        hbox = gtk.HBox(False, 12)
        # Progress bar
        self.progress_bar = HobProgressBar()
        hbox.pack_start(self.progress_bar)
        self.start()
        self.vbox.pack_start(hbox, expand=False, fill=False)

        button = self.add_button("Cancel", gtk.RESPONSE_CANCEL)
        HobAltButton.style_button(button)
        self.show_all()
