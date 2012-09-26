#!/usr/bin/env python
#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2012        Intel Corporation
#
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
import glib
from bb.ui.crumbs.hobcolor import HobColors
from bb.ui.crumbs.hobwidget import HobViewTable, HobNotebook, HobAltButton, HobButton
from bb.ui.crumbs.hoblistmodel import PackageListModel
from bb.ui.crumbs.hobpages import HobPage

#
# PackageSelectionPage
#
class PackageSelectionPage (HobPage):

    pages = [
        {
         'name'    : 'Included packages',
         'tooltip' : 'The packages currently included for your image',
         'filter'  : { PackageListModel.COL_INC : [True] },
         'columns' : [{
                       'col_name' : 'Package name',
                       'col_id'   : PackageListModel.COL_NAME,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 300,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Size',
                       'col_id'   : PackageListModel.COL_SIZE,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 300,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Brought in by',
                       'col_id'   : PackageListModel.COL_BINB,
                       'col_style': 'binb',
                       'col_min'  : 100,
                       'col_max'  : 350,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Included',
                       'col_id'   : PackageListModel.COL_INC,
                       'col_style': 'check toggle',
                       'col_min'  : 100,
                       'col_max'  : 100
                     }]
        }, {
         'name'    : 'All packages',
         'tooltip' : 'All packages that have been built',
         'filter'  : {},
         'columns' : [{
                       'col_name' : 'Package name',
                       'col_id'   : PackageListModel.COL_NAME,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Size',
                       'col_id'   : PackageListModel.COL_SIZE,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 500,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Included',
                       'col_id'   : PackageListModel.COL_INC,
                       'col_style': 'check toggle',
                       'col_min'  : 100,
                       'col_max'  : 100
                      }]
        }
    ]
    
    (INCLUDED,
     ALL) = range(2)

    def __init__(self, builder):
        super(PackageSelectionPage, self).__init__(builder, "Edit packages")

        # set invisiable members
        self.recipe_model = self.builder.recipe_model
        self.package_model = self.builder.package_model

        # create visual elements
        self.create_visual_elements()

    def included_clicked_cb(self, button):
        self.ins.set_current_page(self.INCLUDED)

    def create_visual_elements(self):
        self.label = gtk.Label("Packages included: 0\nSelected packages size: 0 MB")
        self.eventbox = self.add_onto_top_bar(self.label, 73)
        self.pack_start(self.eventbox, expand=False, fill=False)
        self.pack_start(self.group_align, expand=True, fill=True)

        # set visible members
        self.ins = HobNotebook()
        self.tables = [] # we need to modify table when the dialog is shown
        # append the tab
        for page in self.pages:
            columns = page['columns']
            tab = HobViewTable(columns)
            filter = page['filter']
            tab.set_model(self.package_model.tree_model(filter))
            tab.connect("toggled", self.table_toggled_cb, page['name'])
            if page['name'] == "Included packages":
                tab.connect("button-release-event", self.button_click_cb)
                tab.connect("cell-fadeinout-stopped", self.after_fadeout_checkin_include)
            self.ins.append_page(tab, page['name'], page['tooltip'])
            self.tables.append(tab)

        self.ins.set_entry("Search packages:")
        # set the search entry for each table
        for tab in self.tables:
            search_tip = "Enter a package name to find it"
            self.ins.search.set_tooltip_text(search_tip)
            self.ins.search.props.has_tooltip = True
            tab.set_search_entry(0, self.ins.search)

        # add all into the dialog
        self.box_group_area.pack_start(self.ins, expand=True, fill=True)

        self.button_box = gtk.HBox(False, 6)
        self.box_group_area.pack_start(self.button_box, expand=False, fill=False)

        self.build_image_button = HobButton('Build image')
        #self.build_image_button.set_size_request(205, 49)
        self.build_image_button.set_tooltip_text("Build target image")
        self.build_image_button.set_flags(gtk.CAN_DEFAULT)
        self.build_image_button.grab_default()
        self.build_image_button.connect("clicked", self.build_image_clicked_cb)
        self.button_box.pack_end(self.build_image_button, expand=False, fill=False)

        self.back_button = HobAltButton('Cancel')
        self.back_button.connect("clicked", self.back_button_clicked_cb)
        self.button_box.pack_end(self.back_button, expand=False, fill=False)

    def button_click_cb(self, widget, event):
        path, col = widget.table_tree.get_cursor()
        tree_model = widget.table_tree.get_model()
        if path: # else activation is likely a removal
            binb = tree_model.get_value(tree_model.get_iter(path), PackageListModel.COL_BINB)
            if binb:
                self.builder.show_binb_dialog(binb)

    def open_log_clicked_cb(self, button, log_file):
        if log_file:
            os.system("xdg-open /%s" % log_file)

    def show_page(self, log_file):
        children = self.button_box.get_children() or []
        for child in children:
            self.button_box.remove(child)
        # re-packed the buttons as request, add the 'open log' button if build success
        self.button_box.pack_end(self.build_image_button, expand=False, fill=False)
        if log_file:
            open_log_button = HobAltButton("Open log")
            open_log_button.connect("clicked", self.open_log_clicked_cb, log_file)
            open_log_button.set_tooltip_text("Open the build's log file")
            self.button_box.pack_end(open_log_button, expand=False, fill=False)
        self.button_box.pack_end(self.back_button, expand=False, fill=False)
        self.show_all()

    def build_image_clicked_cb(self, button):
        self.builder.build_image()

    def back_button_clicked_cb(self, button):
        if self.builder.previous_step ==  self.builder.IMAGE_GENERATED:
            self.builder.restore_initial_selected_packages()
            self.refresh_selection()
            self.builder.show_image_details()
        else:
            self.builder.show_configuration()

    def _expand_all(self):
        for tab in self.tables:
            tab.table_tree.expand_all()

    def refresh_selection(self):
        self._expand_all()

        self.builder.configuration.selected_packages = self.package_model.get_selected_packages()
        self.builder.configuration.user_selected_packages = self.package_model.get_user_selected_packages()
        selected_packages_num = len(self.builder.configuration.selected_packages)
        selected_packages_size = self.package_model.get_packages_size()
        selected_packages_size_str = HobPage._size_to_string(selected_packages_size)

        image_overhead_factor = self.builder.configuration.image_overhead_factor
        image_rootfs_size = self.builder.configuration.image_rootfs_size * 1024 # image_rootfs_size is KB
        image_extra_size = self.builder.configuration.image_extra_size * 1024 # image_extra_size is KB
        base_size = image_overhead_factor * selected_packages_size
        image_total_size = max(base_size, image_rootfs_size) + image_extra_size
        if "zypper" in self.builder.configuration.selected_packages:
            image_total_size += (51200 * 1024)
        image_total_size_str = HobPage._size_to_string(image_total_size)

        self.label.set_label("Packages included: %s\nSelected packages size: %s\nTotal image size: %s" %
                            (selected_packages_num, selected_packages_size_str, image_total_size_str))
        self.ins.show_indicator_icon("Included packages", selected_packages_num)

    def toggle_item_idle_cb(self, path, view_tree, cell, pagename):
        if not self.package_model.path_included(path):
            self.package_model.include_item(item_path=path, binb="User Selected")
        else:
            if pagename == "Included packages":
                self.pre_fadeout_checkout_include(view_tree)
                self.package_model.exclude_item(item_path=path)
                self.render_fadeout(view_tree, cell)
            else:
                self.package_model.exclude_item(item_path=path)

        self.refresh_selection()
        if not self.builder.customized:
            self.builder.customized = True
            self.builder.configuration.selected_image = self.recipe_model.__custom_image__
            self.builder.rcppkglist_populated()

        self.builder.window_sensitive(True)

    def table_toggled_cb(self, table, cell, view_path, toggled_columnid, view_tree, pagename):
        # Click to include a package
        self.builder.window_sensitive(False)
        view_model = view_tree.get_model()
        path = self.package_model.convert_vpath_to_path(view_model, view_path)
        glib.idle_add(self.toggle_item_idle_cb, path, view_tree, cell, pagename)

    def pre_fadeout_checkout_include(self, tree):
        self.package_model.resync_fadeout_column(self.package_model.get_iter_first())
        # Check out a model which base on the column COL_FADE_INC,
        # it's save the prev state of column COL_INC before do exclude_item
        filter = { PackageListModel.COL_FADE_INC  : [True]}
        new_model = self.package_model.tree_model(filter)
        tree.set_model(new_model)
        tree.expand_all()

    def get_excluded_rows(self, to_render_cells, model, it):
        while it:
            path = model.get_path(it)
            prev_cell_is_active = model.get_value(it, PackageListModel.COL_FADE_INC)
            curr_cell_is_active = model.get_value(it, PackageListModel.COL_INC)
            if (prev_cell_is_active == True) and (curr_cell_is_active == False):
                to_render_cells.append(path)
            if model.iter_has_child(it):
                self.get_excluded_rows(to_render_cells, model, model.iter_children(it))
            it = model.iter_next(it)

        return to_render_cells

    def render_fadeout(self, tree, cell):
        if (not cell) or (not tree):
            return
        to_render_cells = []
        view_model = tree.get_model()
        self.get_excluded_rows(to_render_cells, view_model, view_model.get_iter_first())

        cell.fadeout(tree, 1000, to_render_cells)

    def after_fadeout_checkin_include(self, table, ctrl, cell, tree):
        tree.set_model(self.package_model.tree_model(self.pages[0]['filter']))
        tree.expand_all()

    def set_packages_curr_tab(self, curr_page):
        self.ins.set_current_page(curr_page)

