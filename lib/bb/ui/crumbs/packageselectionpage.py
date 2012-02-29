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
from bb.ui.crumbs.hobwidget import HobViewBar, HobViewTable
from bb.ui.crumbs.hoblistmodel import PackageListModel
from bb.ui.crumbs.hobpages import HobPage

#
# PackageSelectionPage
#
class PackageSelectionPage (HobPage):

    pages = [
        {
         'name'    : 'All packages',
         'filter'  : {},
         'columns' : [{
                       'col_name' : 'Name',
                       'col_id'   : PackageListModel.COL_NAME,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400
                      }, {
                       'col_name' : 'size',
                       'col_id'   : PackageListModel.COL_SIZE,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 500
                      }, {
                       'col_name' : 'Included',
                       'col_id'   : PackageListModel.COL_INC,
                       'col_style': 'check toggle',
                       'col_min'  : 50,
                       'col_max'  : 50
                      }]
        }, {
         'name'    : 'Included',
         'filter'  : { PackageListModel.COL_INC : [True] },
         'columns' : [{
                       'col_name' : 'Name',
                       'col_id'   : PackageListModel.COL_NAME,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 300
                      }, {
                       'col_name' : 'Brought by',
                       'col_id'   : PackageListModel.COL_BINB,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 350
                      }, {
                       'col_name' : 'size',
                       'col_id'   : PackageListModel.COL_SIZE,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 300
                      }, {
                       'col_name' : 'Included',
                       'col_id'   : PackageListModel.COL_INC,
                       'col_style': 'check toggle',
                       'col_min'  : 50,
                       'col_max'  : 50
                     }]
        }
    ]

    def __init__(self, builder):
        super(PackageSelectionPage, self).__init__(builder, "Package Selection")

        # set invisiable members
        self.package_model = self.builder.package_model

        # create visual elements
        self.create_visual_elements()

    def create_visual_elements(self):
        self.label = gtk.Label("Packages included: 0\nSelected packages size: 0 MB")
        self.eventbox = self.add_onto_top_bar(self.label, 73)
        self.pack_start(self.eventbox, expand=False, fill=False)
        self.pack_start(self.group_align, expand=True, fill=True)

        # set visiable members
        self.grid = gtk.Table(10, 1, True)
        self.grid.set_col_spacings(3)

        self.ins = gtk.Notebook()
        self.ins.set_show_tabs(False)
        self.tables = [] # we need to modify table when the dialog is shown
        # append the tab
        for i in range(len(self.pages)):
            columns = self.pages[i]['columns']
            tab = HobViewTable(columns)
            filter = self.pages[i]['filter']
            tab.set_model(self.package_model.tree_model(filter))
            tab.connect("toggled", self.table_toggled_cb)
            if self.pages[i]['name'] == "Included":
                tab.connect("row-activated", self.tree_row_activated_cb)

            reset_button = gtk.Button("Reset")
            reset_button.connect("clicked", self.reset_clicked_cb)
            hbox = gtk.HBox(False, 5)
            hbox.pack_end(reset_button, expand=False, fill=False)
            tab.pack_start(hbox, expand=False, fill=False)

            label = gtk.Label(self.pages[i]['name'])
            self.ins.append_page(tab, label)
            self.tables.append(tab)

        self.grid.attach(self.ins, 0, 1, 1, 10, gtk.FILL | gtk.EXPAND, gtk.FILL | gtk.EXPAND, 1, 1)
        # a black bar associated with the notebook
        self.topbar = HobViewBar(self.ins) 
        self.grid.attach(self.topbar, 0, 1, 0, 1, gtk.FILL | gtk.EXPAND, gtk.FILL | gtk.EXPAND, 1, 1)
        # set the search entry for each table
        for tab in self.tables:
            tab.set_search_entry(0, self.topbar.search)

        # add all into the dialog
        self.box_group_area.add(self.grid)

        button_box = gtk.HBox(False, 5)
        self.box_group_area.pack_start(button_box, expand=False, fill=False)

        self.build_image_button = gtk.Button()
        label = gtk.Label()
        mark = "<span %s>Build image</span>" % self.span_tag('24px', 'bold')
        label.set_markup(mark)
        self.build_image_button.set_image(label)
        self.build_image_button.set_size_request(205, 49)
        self.build_image_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(HobColors.ORANGE))
        self.build_image_button.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color(HobColors.ORANGE))
        self.build_image_button.modify_bg(gtk.STATE_SELECTED, gtk.gdk.Color(HobColors.ORANGE))
        self.build_image_button.set_tooltip_text("Build image to get your target image")
        self.build_image_button.set_flags(gtk.CAN_DEFAULT)
        self.build_image_button.grab_default()
        self.build_image_button.connect("clicked", self.build_image_clicked_cb)
        button_box.pack_end(self.build_image_button, expand=False, fill=False)

        self.back_button = gtk.LinkButton("Go back to Image Configuration screen", "<< Back to image configuration")
        self.back_button.connect("clicked", self.back_button_clicked_cb)
        button_box.pack_start(self.back_button, expand=False, fill=False)

    def tree_row_activated_cb(self, table, tree_model, path):
        binb = tree_model.get_value(tree_model.get_iter(path), PackageListModel.COL_BINB)
        if binb:
            self.builder.show_binb_dialog(binb)

    def build_image_clicked_cb(self, button):
        self.builder.build_image()

    def back_button_clicked_cb(self, button):
        self.builder.show_configuration()

    def _expand_all(self):
        for tab in self.tables:
            tab.table_tree.expand_all()

    def refresh_selection(self):
        self._expand_all()

        self.builder.configuration.selected_packages = self.package_model.get_selected_packages()
        selected_packages_num = len(self.builder.configuration.selected_packages)
        selected_packages_size = float(self.package_model.get_packages_size())
        selected_packages_size_str = self._size_to_string(selected_packages_size)

        image_overhead_factor = self.builder.configuration.image_overhead_factor
        image_rootfs_size = self.builder.configuration.image_rootfs_size
        image_extra_size = self.builder.configuration.image_extra_size
        base_size = image_overhead_factor * selected_packages_size
        image_total_size = max(base_size, image_rootfs_size) + image_extra_size
        image_total_size_str = self._size_to_string(image_total_size)

        self.label.set_text("Packages included: %s\nSelected packages size: %s\nTotal image size: %s" %
                            (selected_packages_num, selected_packages_size_str, image_total_size_str))

    """
    Helper function to convert the package size to string format.
    The unit of size is KB
    """
    def _size_to_string(self, size):
        if len(str(int(size))) > 3:
            size_str = '%.1f' % (size*1.0/1024) + ' MB'
        else:
            size_str = str(size) + ' KB'
        return size_str

    # Callback functions
    def reset_clicked_cb(self, button):
        self.package_model.reset()
        self.builder.reset_package_model()

    def toggle_item_idle_cb(self, path):
        if not self.package_model.path_included(path):
            self.package_model.include_item(item_path=path, binb="User Selected")
        else:
            self.package_model.exclude_item(item_path=path)

        self.builder.window_sensitive(True)

    def table_toggled_cb(self, table, cell, view_path, toggled_columnid, view_tree):
        # Click to include a package
        self.builder.window_sensitive(False)
        view_model = view_tree.get_model()
        path = self.package_model.convert_vpath_to_path(view_model, view_path)
        glib.idle_add(self.toggle_item_idle_cb, path)
