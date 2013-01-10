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
import os
from bb.ui.crumbs.hobwidget import HobInfoButton, HobButton, HobAltButton

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
