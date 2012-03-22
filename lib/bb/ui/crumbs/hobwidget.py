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
import sys
import pango, pangocairo
import math

from bb.ui.crumbs.hobcolor import HobColors
from bb.ui.crumbs.persistenttooltip import PersistentTooltip

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
    ICON_INDI_REMOVE_FILE         = os.path.join(HOB_ICON_BASE_DIR, ('indicators/remove.png'))
    ICON_INDI_REMOVE_HOVER_FILE   = os.path.join(HOB_ICON_BASE_DIR, ('indicators/remove-hover.png'))
    ICON_INDI_ADD_FILE            = os.path.join(HOB_ICON_BASE_DIR, ('indicators/add.png'))
    ICON_INDI_ADD_HOVER_FILE      = os.path.join(HOB_ICON_BASE_DIR, ('indicators/add-hover.png'))

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

        for i, column in enumerate(columns):
            col = gtk.TreeViewColumn(column['col_name'])
            col.set_clickable(True)
            col.set_resizable(True)
            col.set_sort_column_id(column['col_id'])
            if 'col_min' in column.keys():
                col.set_min_width(column['col_min'])
            if 'col_max' in column.keys():
                col.set_max_width(column['col_max'])
            self.table_tree.append_column(col)

            if (not 'col_style' in column.keys()) or column['col_style'] == 'text':
                cell = gtk.CellRendererText()
                col.pack_start(cell, True)
                col.set_attributes(cell, text=column['col_id'])
            elif column['col_style'] == 'check toggle':
                cell = gtk.CellRendererToggle()
                cell.set_property('activatable', True)
                cell.connect("toggled", self.toggled_cb, i, self.table_tree)
                self.toggle_id = i
                col.pack_end(cell, True)
                col.set_attributes(cell, active=column['col_id'])
                self.toggle_columns.append(column['col_name'])
            elif column['col_style'] == 'radio toggle':
                cell = gtk.CellRendererToggle()
                cell.set_property('activatable', True)
                cell.set_radio(True)
                cell.connect("toggled", self.toggled_cb, i, self.table_tree)
                self.toggle_id = i
                col.pack_end(cell, True)
                col.set_attributes(cell, active=column['col_id'])
                self.toggle_columns.append(column['col_name'])

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

"""
A method to calculate a softened value for the colour of widget when in the
provided state.

widget: the widget whose style to use
state: the state of the widget to use the style for

Returns a string value representing the softened colour
"""
def soften_color(widget, state=gtk.STATE_NORMAL):
    # this colour munging routine is heavily inspired bu gdu_util_get_mix_color()
    # from gnome-disk-utility:
    # http://git.gnome.org/browse/gnome-disk-utility/tree/src/gdu-gtk/gdu-gtk.c?h=gnome-3-0
    blend = 0.7
    style = widget.get_style()
    color = style.text[state]
    color.red = color.red * blend + style.base[state].red * (1.0 - blend)
    color.green = color.green * blend + style.base[state].green * (1.0 - blend)
    color.blue = color.blue * blend + style.base[state].blue * (1.0 - blend)
    return color.to_string()

class HobAltButton(gtk.Button):
    """
    A gtk.Button subclass which has no relief, and so is more discrete
    """
    def __init__(self, label=None):
        gtk.Button.__init__(self, label)
        self.set_relief(gtk.RELIEF_NONE)

class HobImageButton(gtk.Button):
    """
    A gtk.Button with an icon and two rows of text, the second of which is
    displayed in a blended colour.

    primary_text: the main button label
    secondary_text: optional second line of text
    icon_path: path to the icon file to display on the button
    """
    def __init__(self, primary_text, secondary_text="", icon_path="", hover_icon_path=""):
        gtk.Button.__init__(self)
        self.set_relief(gtk.RELIEF_NONE)

        self.icon_path = icon_path
        self.hover_icon_path = hover_icon_path

        hbox = gtk.HBox(False, 3)
        hbox.show()
        self.add(hbox)
        self.icon = gtk.Image()
        self.icon.set_from_file(self.icon_path)
        self.icon.set_alignment(0.5, 0.0)
        self.icon.show()
        if self.hover_icon_path and len(self.hover_icon_path):
            self.connect("enter-notify-event", self.set_hover_icon_cb)
            self.connect("leave-notify-event", self.set_icon_cb)
        hbox.pack_start(self.icon, False, False, 0)
        label = gtk.Label()
        label.set_alignment(0.0, 0.5)
        colour = soften_color(label)
        mark = "%s\n<span fgcolor='%s'><small>%s</small></span>" % (primary_text, colour, secondary_text)
        label.set_markup(mark)
        label.show()
        hbox.pack_start(label, True, True, 0)

    def set_hover_icon_cb(self, widget, event):
        self.icon.set_from_file(self.hover_icon_path)

    def set_icon_cb(self, widget, event):
        self.icon.set_from_file(self.icon_path)

class HobInfoButton(gtk.EventBox):
    """
    This class implements a button-like widget per the Hob visual and UX designs
    which will display a persistent tooltip, with the contents of tip_markup, when
    clicked.

    tip_markup: the Pango Markup to be displayed in the persistent tooltip
    """
    def __init__(self, tip_markup, parent=None):
        gtk.EventBox.__init__(self)
        self.image = gtk.Image()
        self.image.set_from_file(hic.ICON_INFO_DISPLAY_FILE)
        self.image.show()
        self.add(self.image)

        self.set_events(gtk.gdk.BUTTON_RELEASE |
                        gtk.gdk.ENTER_NOTIFY_MASK |
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self.ptip = PersistentTooltip(tip_markup)

        if parent:
            self.ptip.set_parent(parent)
            self.ptip.set_transient_for(parent)
            self.ptip.set_destroy_with_parent(True)

        self.connect("button-release-event", self.button_release_cb)
        self.connect("enter-notify-event", self.mouse_in_cb)
        self.connect("leave-notify-event", self.mouse_out_cb)

    """
    When the mouse click is released emulate a button-click and show the associated
    PersistentTooltip
    """
    def button_release_cb(self, widget, event):
        self.ptip.show()

    """
    Change to the prelight image when the mouse enters the widget
    """
    def mouse_in_cb(self, widget, event):
        self.image.set_from_file(hic.ICON_INFO_HOVER_FILE)

    """
    Change to the stock image when the mouse enters the widget
    """
    def mouse_out_cb(self, widget, event):
        self.image.set_from_file(hic.ICON_INFO_DISPLAY_FILE)

class HobTabBar(gtk.DrawingArea):
    __gsignals__ = {
        "blank-area-changed" : (gobject.SIGNAL_RUN_LAST,
                                gobject.TYPE_NONE,
                               (gobject.TYPE_INT,
                                gobject.TYPE_INT,
                                gobject.TYPE_INT,
                                gobject.TYPE_INT,)),

        "tab-switched" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE,
                         (gobject.TYPE_INT,)),
    }

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.children = []

        self.tab_width = 140
        self.tab_height = 52
        self.tab_x = 10
        self.tab_y = 0

        self.width = 500
        self.height = 53
        self.tab_w_ratio = 140 * 1.0/500
        self.tab_h_ratio = 52 * 1.0/53
        self.set_size_request(self.width, self.height)

        self.current_child = None
        self.font = self.get_style().font_desc
        self.font.set_size(pango.SCALE * 13) 
        self.update_children_text_layout_and_bg_color()

        self.blank_rectangle = None
        self.tab_pressed = False

        self.set_property('can-focus', True)
        self.set_events(gtk.gdk.EXPOSURE_MASK | gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.BUTTON1_MOTION_MASK | gtk.gdk.BUTTON_PRESS_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK)

        self.connect("expose-event", self.on_draw)
        self.connect("button-press-event", self.button_pressed_cb)
        self.connect("button-release-event", self.button_released_cb)
        self.show_all()

    def button_released_cb(self, widget, event):
        self.tab_pressed = False
        self.queue_draw()

    def button_pressed_cb(self, widget, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            return

        result = False
        if self.is_focus() or event.type == gtk.gdk.BUTTON_PRESS:
            x, y = event.get_coords()
            # check which tab be clicked
            for child in self.children:
               if      (child["x"] < x) and (x < child["x"] + self.tab_width) \
                   and (child["y"] < y) and (y < child["y"] + self.tab_height):
                   self.current_child = child
                   result = True
                   self.grab_focus()
                   break

            # check the blank area is focus in or not
            if (self.blank_rectangle) and (self.blank_rectangle.x > 0) and (self.blank_rectangle.y > 0):
                if      (self.blank_rectangle.x < x) and (x < self.blank_rectangle.x + self.blank_rectangle.width) \
                    and (self.blank_rectangle.y < y) and (y < self.blank_rectangle.y + self.blank_rectangle.height):
                   self.grab_focus()

        if result == True:
            page = self.current_child["toggled_page"]
            self.emit("tab-switched", page)
            self.tab_pressed = True
            self.queue_draw()

    def update_children_size(self):
        # calculate the size of tabs
        self.tab_width = int(self.width * self.tab_w_ratio)
        self.tab_height = int(self.height * self.tab_h_ratio)
        for i, child in enumerate(self.children):
            child["x"] = self.tab_x + i * self.tab_width
            child["y"] = self.tab_y

        if self.blank_rectangle:
            self.resize_blank_rectangle()

    def resize_blank_rectangle(self):
        width = self.width - self.tab_width * len(self.children) - self.tab_x
        x = self.tab_x + self.tab_width * len(self.children)
        hpadding = vpadding = 5
        self.blank_rectangle = self.set_blank_size(x + hpadding, self.tab_y + vpadding,
            width - 2 * hpadding, self.tab_height - 2 * vpadding)

    def update_children_text_layout_and_bg_color(self):
        style = self.get_style().copy()
        color = style.base[gtk.STATE_NORMAL]
        for child in self.children:
            pangolayout = self.create_pango_layout(child["title"])
            pangolayout.set_font_description(self.font)
            child["title_layout"] = pangolayout
            child["r"] = color.red
            child["g"] = color.green
            child["b"] = color.blue

    def append_tab_child(self, title, page):
        num = len(self.children) + 1
        self.tab_width = self.tab_width * len(self.children) / num

        i = 0
        for i, child in enumerate(self.children):
            child["x"] = self.tab_x + i * self.tab_width
            i += 1

        x = self.tab_x + i * self.tab_width
        y = self.tab_y
        pangolayout = self.create_pango_layout(title)
        pangolayout.set_font_description(self.font)
        color = self.style.base[gtk.STATE_NORMAL]
        new_one = {
            "x" : x,
            "y" : y,
            "r" : color.red,
            "g" : color.green,
            "b" : color.blue,
            "title_layout" : pangolayout,
            "toggled_page" : page,
            "title"        : title,
            "indicator_show"   : False,
            "indicator_number" : 0,
        }
        self.children.append(new_one)
        # set the default current child
        if not self.current_child:
            self.current_child = new_one

    def on_draw(self, widget, event):
        cr = widget.window.cairo_create()

        self.width = self.allocation.width
        self.height = self.allocation.height

        self.update_children_size()

        self.draw_background(cr)
        self.draw_toggled_tab(cr)

        for child in self.children:
            if child["indicator_show"] == True:
                self.draw_indicator(cr, child)

        self.draw_tab_text(cr)

    def draw_background(self, cr):
        style = self.get_style()

        if self.is_focus():
            cr.set_source_color(style.base[gtk.STATE_SELECTED])
        else:
            cr.set_source_color(style.base[gtk.STATE_NORMAL])

        y = 6
        h = self.height - 6 - 1
        gap = 1

        w = self.children[0]["x"]
        cr.set_source_color(gtk.gdk.color_parse(HobColors.GRAY))
        cr.rectangle(0, y, w - gap, h) # start rectangle
        cr.fill()

        cr.set_source_color(style.base[gtk.STATE_NORMAL])
        cr.rectangle(w - gap, y, w, h) #first gap
        cr.fill()

        w = self.tab_width
        for child in self.children:
            x = child["x"]
            cr.set_source_color(gtk.gdk.color_parse(HobColors.GRAY))
            cr.rectangle(x, y, w - gap, h) # tab rectangle
            cr.fill()
            cr.set_source_color(style.base[gtk.STATE_NORMAL])
            cr.rectangle(x + w - gap, y, w, h) # gap
            cr.fill()

        cr.set_source_color(gtk.gdk.color_parse(HobColors.GRAY))
        cr.rectangle(x + w, y, self.width - x - w, h) # last rectangle
        cr.fill()

    def draw_tab_text(self, cr):
        style = self.get_style()

        for child in self.children:
            pangolayout = child["title_layout"]
            if pangolayout:
                fontw, fonth = pangolayout.get_pixel_size()
                # center pos
                off_x = (self.tab_width - fontw) / 2
                off_y = (self.tab_height - fonth) / 2
                x = child["x"] + off_x
                y = child["y"] + off_y
                self.window.draw_layout(self.style.fg_gc[gtk.STATE_NORMAL], int(x), int(y), pangolayout)

    def draw_toggled_tab(self, cr):
        if not self.current_child:
            return
        x = self.current_child["x"]
        y = self.current_child["y"]
        width = self.tab_width
        height = self.tab_height
        style = self.get_style()
        color = style.base[gtk.STATE_NORMAL]

        r = height / 10
        if self.tab_pressed == True:
            for xoff, yoff, c1, c2 in [(1, 0, HobColors.SLIGHT_DARK, HobColors.DARK), (2, 0, HobColors.GRAY, HobColors.LIGHT_GRAY)]:
                cr.set_source_color(gtk.gdk.color_parse(c1))
                cr.move_to(x + xoff, y + height + yoff)
                cr.line_to(x + xoff, r + yoff)
                cr.arc(x + r + xoff, y + r + yoff, r, math.pi, 1.5*math.pi)
                cr.move_to(x + r + xoff, y + yoff)
                cr.line_to(x + width - r + xoff, y + yoff)
                cr.arc(x + width - r + xoff, y + r + yoff, r, 1.5*math.pi, 2*math.pi)
                cr.stroke()
                cr.set_source_color(gtk.gdk.color_parse(c2))
                cr.move_to(x + width + xoff, r + yoff)
                cr.line_to(x + width + xoff, y + height + yoff)
                cr.line_to(x + xoff, y + height + yoff)
                cr.stroke()
            x = x + 2
            y = y + 2
        cr.set_source_rgba(color.red, color.green, color.blue, 1)
        cr.move_to(x + r, y)
        cr.line_to(x + width - r , y)
        cr.arc(x + width - r, y + r, r, 1.5*math.pi, 2*math.pi)
        cr.move_to(x + width, r)
        cr.line_to(x + width, y + height)
        cr.line_to(x, y + height)
        cr.line_to(x, r)
        cr.arc(x + r, y + r, r, math.pi, 1.5*math.pi)
        cr.fill()

    def draw_indicator(self, cr, child):
        text = ("%d" % child["indicator_number"])
        layout = self.create_pango_layout(text)
        layout.set_font_description(self.font)
        textw, texth = layout.get_pixel_size()
        # draw the back round area
        tab_x = child["x"]
        tab_y = child["y"]
        dest_w = int(32 * self.tab_w_ratio)
        dest_h = int(32 * self.tab_h_ratio)
        if dest_h < self.tab_height:
            dest_w = dest_h
        # x position is offset(tab_width*3/4 - icon_width/2) + start_pos(tab_x)
        x = tab_x + self.tab_width * 3/4 - dest_w/2
        y = tab_y + self.tab_height/2 - dest_h/2

        r = min(dest_w, dest_h)/2
        color = cr.set_source_color(gtk.gdk.color_parse(HobColors.ORANGE))
        # check round back area can contain the text or not
        back_round_can_contain_width = float(2 * r * 0.707)
        if float(textw) > back_round_can_contain_width:
            xoff = (textw - int(back_round_can_contain_width)) / 2
            cr.move_to(x + r - xoff, y + r + r)
            cr.arc((x + r - xoff), (y + r), r, 0.5*math.pi, 1.5*math.pi)
            cr.fill() # left half round
            cr.rectangle((x + r - xoff), y, 2 * xoff, 2 * r)
            cr.fill() # center rectangle
            cr.arc((x + r + xoff), (y + r), r, 1.5*math.pi, 0.5*math.pi)
            cr.fill() # right half round
        else:
            cr.arc((x + r), (y + r), r, 0, 2*math.pi)
            cr.fill()
        # draw the number text
        x = x + (dest_w/2)-(textw/2)
        y = y + (dest_h/2) - (texth/2)
        cr.move_to(x, y)
        self.window.draw_layout(self.style.fg_gc[gtk.STATE_NORMAL], int(x), int(y), layout)

    def show_indicator_icon(self, child, number):
        child["indicator_show"] = True
        child["indicator_number"] = number
        self.queue_draw()

    def hide_indicator_icon(self, child):
        child["indicator_show"] = False
        self.queue_draw()

    def set_blank_size(self, x, y, w, h):
        if not self.blank_rectangle or self.blank_rectangle.x != x or self.blank_rectangle.width != w:
            self.emit("blank-area-changed", x, y, w, h)

        return gtk.gdk.Rectangle(x, y, w, h)

class HobNotebook(gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self, False, 0)

        self.notebook = gtk.Notebook()
        self.notebook.set_property('homogeneous', True)
        self.notebook.set_property('show-tabs', False)

        self.tabbar = HobTabBar()
        self.tabbar.connect("tab-switched",   self.tab_switched_cb)
        self.notebook.connect("page-added",   self.page_added_cb)
        self.notebook.connect("page-removed", self.page_removed_cb)

        self.search = None
        self.search_name = ""

        self.tb = gtk.Table(1, 100, False)
        self.hbox= gtk.HBox(False, 0)
        self.hbox.pack_start(self.tabbar, True, True)
        self.tb.attach(self.hbox, 0, 100, 0, 1)

        self.pack_start(self.tb, False, False)
        self.pack_start(self.notebook)

        self.show_all()

    def append_page(self, child, tab_label):
        self.notebook.set_current_page(self.notebook.append_page(child, tab_label))

    def set_entry(self, name="Search:"):
        for child in self.tb.get_children(): 
            if child:
                self.tb.remove(child)

        hbox_entry = gtk.HBox(False, 0)
        hbox_entry.show()

        self.search = gtk.Entry()
        self.search_name = name
        style = self.search.get_style()
        style.text[gtk.STATE_NORMAL] = self.get_colormap().alloc_color(HobColors.GRAY, False, False)
        self.search.set_style(style)
        self.search.set_text(name)
        self.search.set_editable(False)
        self.search.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY, gtk.STOCK_CLEAR)
        self.search.connect("icon-release", self.set_search_entry_clear_cb)
        self.search.show()
        self.align = gtk.Alignment(xalign=1.0, yalign=0.7)
        self.align.add(self.search)
        self.align.show()
        hbox_entry.pack_end(self.align, False, False)
        self.tabbar.resize_blank_rectangle()

        self.tb.attach(hbox_entry, 75, 100, 0, 1, xpadding=5)
        self.tb.attach(self.hbox, 0, 100, 0, 1)

        self.tabbar.connect("blank-area-changed", self.blank_area_resize_cb)
        self.search.connect("focus-in-event", self.set_search_entry_editable_cb)
        self.search.connect("focus-out-event", self.set_search_entry_reset_cb)
 
        self.tb.show()

    def show_indicator_icon(self, title, number):
        for child in self.tabbar.children:
            if child["toggled_page"] == -1:
                continue
            if child["title"] == title:
                self.tabbar.show_indicator_icon(child, number)

    def hide_indicator_icon(self, title):
        for child in self.tabbar.children:
            if child["toggled_page"] == -1:
                continue
            if child["title"] == title:
                self.tabbar.hide_indicator_icon(child)

    def tab_switched_cb(self, widget, page):
        self.notebook.set_current_page(page)

    def page_added_cb(self, notebook, notebook_child, page):
        if not notebook:
            return
        title = notebook.get_tab_label_text(notebook_child)
        if not title:
            return
        for child in self.tabbar.children:
            if child["title"] == title:
                child["toggled_page"] = page
                return
        self.tabbar.append_tab_child(title, page)

    def page_removed_cb(self, notebook, notebook_child, page, title=""):
        for child in self.tabbar.children:
            if child["title"] == title:
                child["toggled_page"] = -1

    def blank_area_resize_cb(self, widget, request_x, request_y, request_width, request_height):
        self.search.set_size_request(request_width, request_height)

    def set_search_entry_editable_cb(self, search, event):
        search.set_editable(True)
        search.set_text("")
        style = self.search.get_style()
        style.text[gtk.STATE_NORMAL] = self.get_colormap().alloc_color(HobColors.BLACK, False, False)
        search.set_style(style)

    def reset_entry(self, entry):
        style = entry.get_style()
        style.text[gtk.STATE_NORMAL] = self.get_colormap().alloc_color(HobColors.GRAY, False, False)
        entry.set_style(style)
        entry.set_text(self.search_name)
        entry.set_editable(False)

    def set_search_entry_reset_cb(self, search, event):
        self.reset_entry(search)

    def set_search_entry_clear_cb(self, search, icon_pos, event):
        self.reset_entry(search)

