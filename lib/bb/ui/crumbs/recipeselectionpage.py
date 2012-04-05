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
from bb.ui.crumbs.hoblistmodel import RecipeListModel
from bb.ui.crumbs.hobpages import HobPage

#
# RecipeSelectionPage
#
class RecipeSelectionPage (HobPage):
    pages = [
        {
         'name'    : 'Included',
         'filter'  : { RecipeListModel.COL_INC  : [True],
                       RecipeListModel.COL_TYPE : ['recipe', 'task'] },
         'columns' : [{
                       'col_name' : 'Recipe name',
                       'col_id'   : RecipeListModel.COL_NAME,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Brought in by',
                       'col_id'   : RecipeListModel.COL_BINB,
                       'col_style': 'binb',
                       'col_min'  : 100,
                       'col_max'  : 500,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Group',
                       'col_id'   : RecipeListModel.COL_GROUP,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 300,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Included',
                       'col_id'   : RecipeListModel.COL_INC,
                       'col_style': 'check toggle',
                       'col_min'  : 100,
                       'col_max'  : 100
                      }]
        }, {
         'name'    : 'All recipes',
         'filter'  : { RecipeListModel.COL_TYPE : ['recipe'] },
         'columns' : [{
                       'col_name' : 'Recipe name',
                       'col_id'   : RecipeListModel.COL_NAME,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'License',
                       'col_id'   : RecipeListModel.COL_LIC,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Group',
                       'col_id'   : RecipeListModel.COL_GROUP,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Included',
                       'col_id'   : RecipeListModel.COL_INC,
                       'col_style': 'check toggle',
                       'col_min'  : 100,
                       'col_max'  : 100
                      }]
        }, {
         'name'    : 'Tasks',
         'filter'  : { RecipeListModel.COL_TYPE : ['task'] },
         'columns' : [{
                       'col_name' : 'Task name',
                       'col_id'   : RecipeListModel.COL_NAME,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Description',
                       'col_id'   : RecipeListModel.COL_DESC,
                       'col_style': 'text',
                       'col_min'  : 100,
                       'col_max'  : 400,
                       'expand'   : 'True'
                      }, {
                       'col_name' : 'Included',
                       'col_id'   : RecipeListModel.COL_INC,
                       'col_style': 'check toggle',
                       'col_min'  : 100,
                       'col_max'  : 100
                      }]
        }
    ]

    def __init__(self, builder = None):
        super(RecipeSelectionPage, self).__init__(builder, "Recipes")

        # set invisiable members
        self.recipe_model = self.builder.recipe_model

        # create visual elements
        self.create_visual_elements()

    def create_visual_elements(self):
        self.label = gtk.Label()
        self.eventbox = self.add_onto_top_bar(self.label, 73)
        self.pack_start(self.eventbox, expand=False, fill=False)
        self.pack_start(self.group_align, expand=True, fill=True)

        # set visiable members
        self.ins = HobNotebook()
        self.tables = [] # we need modify table when the dialog is shown
        # append the tabs in order
        for page in self.pages:
            columns = page['columns']
            tab = HobViewTable(columns)
            filter = page['filter']
            tab.set_model(self.recipe_model.tree_model(filter))
            tab.connect("toggled", self.table_toggled_cb)
            if page['name'] == "Included":
                tab.connect("button-release-event", self.button_click_cb)

            label = gtk.Label(page['name'])
            self.ins.append_page(tab, label)
            self.tables.append(tab)

        self.ins.set_entry("Search recipes:")
        # set the search entry for each table
        for tab in self.tables:
            tab.set_search_entry(0, self.ins.search)

        # add all into the window
        self.box_group_area.pack_start(self.ins, expand=True, fill=True)

        button_box = gtk.HBox(False, 6)
        self.box_group_area.pack_end(button_box, expand=False, fill=False)

        self.build_packages_button = HobButton('Build packages')
        self.build_packages_button.set_size_request(205, 49)
        self.build_packages_button.set_tooltip_text("Build packages for customization")
        self.build_packages_button.set_flags(gtk.CAN_DEFAULT)
        self.build_packages_button.grab_default()
        self.build_packages_button.connect("clicked", self.build_packages_clicked_cb)
        button_box.pack_end(self.build_packages_button, expand=False, fill=False)

        self.back_button = HobAltButton("<< Back to image configuration")
        self.back_button.connect("clicked", self.back_button_clicked_cb)
        button_box.pack_start(self.back_button, expand=False, fill=False)

    def button_click_cb(self, widget, event):
        path, col = widget.table_tree.get_cursor()
        tree_model = widget.table_tree.get_model()
        if path: # else activation is likely a removal
            binb = tree_model.get_value(tree_model.get_iter(path), RecipeListModel.COL_BINB)
            if binb:
                self.builder.show_binb_dialog(binb)

    def build_packages_clicked_cb(self, button):
        self.builder.build_packages()

    def back_button_clicked_cb(self, button):
        self.builder.show_configuration()

    def refresh_selection(self):
        self.builder.configuration.selected_image = self.recipe_model.get_selected_image()
        _, self.builder.configuration.selected_recipes = self.recipe_model.get_selected_recipes()
        self.label.set_text("Recipes included: %s" % len(self.builder.configuration.selected_recipes))
        self.ins.show_indicator_icon("Included", len(self.builder.configuration.selected_recipes))

    def toggle_item_idle_cb(self, path):
        if not self.recipe_model.path_included(path):
            self.recipe_model.include_item(item_path=path, binb="User Selected", image_contents=False)
        else:
            self.recipe_model.exclude_item(item_path=path)

        self.refresh_selection()
        self.builder.window_sensitive(True)

    def table_toggled_cb(self, table, cell, view_path, toggled_columnid, view_tree):
        # Click to include a recipe
        self.builder.window_sensitive(False)
        view_model = view_tree.get_model()
        path = self.recipe_model.convert_vpath_to_path(view_model, view_path)
        glib.idle_add(self.toggle_item_idle_cb, path)
