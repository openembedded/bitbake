# BitBake Graphical GTK User Interface
#
# Copyright (C) 2011-2012   Intel Corporation
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
import gobject
import os
import os.path
from bb.ui.crumbs.hobcolor import HobColors

class hwc:

    MAIN_WIN_WIDTH   = 1024
    MAIN_WIN_HEIGHT  = 700

class hic:

    HOB_ICON_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ("ui/icons/"))

    ICON_RCIPE_DISPLAY_FILE       = os.path.join(HOB_ICON_BASE_DIR, ('recipe/recipe_display.png'))
    ICON_RCIPE_HOVER_FILE         = os.path.join(HOB_ICON_BASE_DIR, ('recipe/recipe_hover.png'))
    ICON_PACKAGES_DISPLAY_FILE    = os.path.join(HOB_ICON_BASE_DIR, ('packages/packages_display.png'))
    ICON_PACKAGES_HOVER_FILE      = os.path.join(HOB_ICON_BASE_DIR, ('packages/packages_hover.png'))
    ICON_LAYERS_DISPLAY_FILE      = os.path.join(HOB_ICON_BASE_DIR, ('layers/layers_display.png'))
    ICON_LAYERS_HOVER_FILE        = os.path.join(HOB_ICON_BASE_DIR, ('layers/layers_hover.png'))
    ICON_TEMPLATES_DISPLAY_FILE   = os.path.join(HOB_ICON_BASE_DIR, ('templates/templates_display.png'))
    ICON_TEMPLATES_HOVER_FILE     = os.path.join(HOB_ICON_BASE_DIR, ('templates/templates_hover.png'))
    ICON_IMAGES_DISPLAY_FILE      = os.path.join(HOB_ICON_BASE_DIR, ('images/images_display.png'))
    ICON_IMAGES_HOVER_FILE        = os.path.join(HOB_ICON_BASE_DIR, ('images/images_hover.png'))
    ICON_SETTINGS_DISPLAY_FILE    = os.path.join(HOB_ICON_BASE_DIR, ('settings/settings_display.png'))
    ICON_SETTINGS_HOVER_FILE      = os.path.join(HOB_ICON_BASE_DIR, ('settings/settings_hover.png'))
    ICON_INFO_DISPLAY_FILE        = os.path.join(HOB_ICON_BASE_DIR, ('info/info_display.png'))
    ICON_INFO_HOVER_FILE          = os.path.join(HOB_ICON_BASE_DIR, ('info/info_hover.png'))
    ICON_INDI_CONFIRM_FILE        = os.path.join(HOB_ICON_BASE_DIR, ('indicators/confirmation.png'))
    ICON_INDI_ERROR_FILE          = os.path.join(HOB_ICON_BASE_DIR, ('indicators/error.png'))

class hcc:

    SUPPORTED_IMAGE_TYPES = {
        "jffs2"         : ["jffs2"],
        "sum.jffs2"     : ["sum.jffs2"],
        "cramfs"        : ["cramfs"],
        "ext2"          : ["ext2"],
        "ext2.gz"       : ["ext2.gz"],
        "ext2.bz2"      : ["ext2.bz2"],
        "ext3"          : ["ext3"],
        "ext3.gz"       : ["ext3.gz"],
        "ext2.lzma"     : ["ext2.lzma"],
        "btrfs"         : ["btrfs"],
        "live"          : ["hddimg", "iso"],
        "squashfs"      : ["squashfs"],
        "squashfs-lzma" : ["squashfs-lzma"],
        "ubi"           : ["ubi"],
        "tar"           : ["tar"],
        "tar.gz"        : ["tar.gz"],
        "tar.bz2"       : ["tar.bz2"],
        "tar.xz"        : ["tar.xz"],
        "cpio"          : ["cpio"],
        "cpio.gz"       : ["cpio.gz"],
        "cpio.xz"       : ["cpio.xz"],
        "cpio.lzma"     : ["cpio.lzma"],
    }

class HobViewTable (gtk.VBox):
    """
    A VBox to contain the table for different recipe views and package view
    """
    __gsignals__ = {
         "toggled"       : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                           (gobject.TYPE_PYOBJECT,
                            gobject.TYPE_STRING,
                            gobject.TYPE_INT,
                            gobject.TYPE_PYOBJECT,)),
         "row-activated" : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                           (gobject.TYPE_PYOBJECT,
                            gobject.TYPE_PYOBJECT,)),
    }

    def __init__(self, columns):
        gtk.VBox.__init__(self, False, 6)
        self.table_tree = gtk.TreeView()
        self.table_tree.set_headers_visible(True)
        self.table_tree.set_headers_clickable(True)
        self.table_tree.set_enable_search(True)
        self.table_tree.set_rules_hint(True)
        self.table_tree.get_selection().set_mode(gtk.SELECTION_SINGLE)
        self.toggle_columns = []
        self.table_tree.connect("row-activated", self.row_activated_cb)

        for i in range(len(columns)):
            col = gtk.TreeViewColumn(columns[i]['col_name'])
            col.set_clickable(True)
            col.set_resizable(True)
            col.set_sort_column_id(columns[i]['col_id'])
            if 'col_min' in columns[i].keys():
                col.set_min_width(columns[i]['col_min'])
            if 'col_max' in columns[i].keys():
                col.set_max_width(columns[i]['col_max'])
            self.table_tree.append_column(col)

            if (not 'col_style' in columns[i].keys()) or columns[i]['col_style'] == 'text':
                cell = gtk.CellRendererText()
                col.pack_start(cell, True)
                col.set_attributes(cell, text=columns[i]['col_id'])
            elif columns[i]['col_style'] == 'check toggle':
                cell = gtk.CellRendererToggle()
                cell.set_property('activatable', True)
                cell.connect("toggled", self.toggled_cb, i, self.table_tree)
                self.toggle_id = i
                col.pack_end(cell, True)
                col.set_attributes(cell, active=columns[i]['col_id'])
                self.toggle_columns.append(columns[i]['col_name'])
            elif columns[i]['col_style'] == 'radio toggle':
                cell = gtk.CellRendererToggle()
                cell.set_property('activatable', True)
                cell.set_radio(True)
                cell.connect("toggled", self.toggled_cb, i, self.table_tree)
                self.toggle_id = i
                col.pack_end(cell, True)
                col.set_attributes(cell, active=columns[i]['col_id'])
                self.toggle_columns.append(columns[i]['col_name'])

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(self.table_tree)
        self.pack_start(scroll, True, True, 0)

    def set_model(self, tree_model):
        self.table_tree.set_model(tree_model)

    def set_search_entry(self, search_column_id, entry):
        self.table_tree.set_search_column(search_column_id)
        self.table_tree.set_search_entry(entry)

    def toggle_default(self):
        model = self.table_tree.get_model()
        if not model:
            return
        iter = model.get_iter_first()
        if iter:
            rowpath = model.get_path(iter)
            model[rowpath][self.toggle_id] = True

    def toggled_cb(self, cell, path, columnid, tree):
        self.emit("toggled", cell, path, columnid, tree)

    def row_activated_cb(self, tree, path, view_column):
        if not view_column.get_title() in self.toggle_columns:
            self.emit("row-activated", tree.get_model(), path)

class HobViewBar (gtk.EventBox):
    """
    A EventBox with the specified gray background color is associated with a notebook.
    And the toolbar to simulate the tabs.
    """

    def __init__(self, notebook):
        if not notebook:
            return
        self.notebook = notebook

        # setup an event box
        gtk.EventBox.__init__(self)
        self.set_border_width(2)
        style = self.get_style().copy()
        style.bg[gtk.STATE_NORMAL] = self.get_colormap().alloc_color (HobColors.GRAY, False, False)
        self.set_style(style)

        hbox = gtk.HBox()
        self.add(hbox)

        # setup a tool bar in the event box
        self.toolbar = gtk.Toolbar()
        self.toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.toolbar.set_style(gtk.TOOLBAR_TEXT)
        self.toolbar.set_border_width(5)

        self.toolbuttons = []
        for index in range(self.notebook.get_n_pages()):
            child = self.notebook.get_nth_page(index)
            label = self.notebook.get_tab_label_text(child)
            tip_text = 'switch to ' + label + ' page'
            toolbutton = self.toolbar.append_element(gtk.TOOLBAR_CHILD_RADIOBUTTON, None,
                                label, tip_text, "Private text", None,
                                self.toolbutton_cb, index)
            toolbutton.set_size_request(200, 100)
            self.toolbuttons.append(toolbutton)

        # set the default current page
        self.modify_toolbuttons_bg(0)
        self.notebook.set_current_page(0)

        self.toolbar.append_space()

        # add the tool bar into the event box
        hbox.pack_start(self.toolbar, expand=False, fill=False)

        self.search = gtk.Entry()
        self.align = gtk.Alignment(xalign=0.5, yalign=0.5)
        self.align.add(self.search)
        hbox.pack_end(self.align, expand=False, fill=False)

        self.label = gtk.Label(" Search: ")
        self.label.set_alignment(0.5, 0.5)
        hbox.pack_end(self.label, expand=False, fill=False)

    def toolbutton_cb(self, widget, index):
        if index >= self.notebook.get_n_pages():
            return
        self.notebook.set_current_page(index)
        self.modify_toolbuttons_bg(index)

    def modify_toolbuttons_bg(self, index):
        if index >= len(self.toolbuttons):
            return
        for i in range(0, len(self.toolbuttons)):
            toolbutton = self.toolbuttons[i]
            if i == index:
                self.modify_toolbutton_bg(toolbutton, True)
            else:
                self.modify_toolbutton_bg(toolbutton)

    def modify_toolbutton_bg(self, toolbutton, active=False):
        if active:
            toolbutton.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(HobColors.WHITE))
            toolbutton.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color(HobColors.WHITE))
            toolbutton.modify_bg(gtk.STATE_SELECTED, gtk.gdk.Color(HobColors.WHITE))
            toolbutton.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color(HobColors.WHITE))
        else:
            toolbutton.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(HobColors.GRAY))
            toolbutton.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.Color(HobColors.GRAY))
            toolbutton.modify_bg(gtk.STATE_SELECTED, gtk.gdk.Color(HobColors.GRAY))
            toolbutton.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color(HobColors.GRAY))

class HobXpmLabelButtonBox(gtk.EventBox):
    """ label: name of buttonbox
        description: the simple  description
    """

    def __init__(self, display_file="", hover_file="", label="", description=""):
        gtk.EventBox.__init__(self)
        self._base_state_flags = gtk.STATE_NORMAL
        self.set_events(gtk.gdk.MOTION_NOTIFY | gtk.gdk.BUTTON_PRESS | gtk.gdk.EXPOSE)

        self.connect("expose-event", self.cb)
        self.connect("enter-notify-event", self.pointer_enter_cb)
        self.connect("leave-notify-event", self.pointer_leave_cb)

        self.icon_hover = gtk.Image()
        self.icon_hover.set_name("icon_image")
        if type(hover_file) == str:
            pixbuf = gtk.gdk.pixbuf_new_from_file(hover_file)
            self.icon_hover.set_from_pixbuf(pixbuf)

        self.icon_display = gtk.Image()
        self.icon_display.set_name("icon_image")
        if type(display_file) == str:
            pixbuf = gtk.gdk.pixbuf_new_from_file(display_file)
            self.icon_display.set_from_pixbuf(pixbuf)

        self.tb = gtk.Table(2, 10, True)
        self.tb.set_row_spacing(1, False)
        self.tb.set_col_spacing(1, False)
        self.add(self.tb)
        self.tb.attach(self.icon_display, 0, 2, 0, 2, 0, 0)
        self.tb.attach(self.icon_hover, 0, 2, 0, 2, 0, 0)

        lbl = gtk.Label()
        lbl.set_alignment(0.0, 0.5)
        lbl.set_markup("<span foreground=\'#1C1C1C\' font_desc=\'18px\'>%s</span>" % label)
        self.tb.attach(lbl, 2, 10, 0, 1)

        lbl = gtk.Label()
        lbl.set_alignment(0.0, 0.5)
        lbl.set_markup("<span foreground=\'#1C1C1C\' font_desc=\'14px\'>%s</span>" % description)
        self.tb.attach(lbl, 2, 10, 1, 2)

    def pointer_enter_cb(self, *args):
        #if not self.is_focus():
        self.set_state(gtk.STATE_PRELIGHT)
        self._base_state_flags = gtk.STATE_PRELIGHT
        self.icon_hover.show()
        self.icon_display.hide()

    def pointer_leave_cb(self, *args):
        self.set_state(gtk.STATE_NORMAL)
        self._base_state_flags = gtk.STATE_NORMAL
        self.icon_display.show()
        self.icon_hover.hide()

    def cb(self, w,e):
        """ Hide items - first time """
        pass

