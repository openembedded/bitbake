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
    ICON_INDI_ERROR_FILE          = os.path.join(HOB_ICON_BASE_DIR, ('indicators/denied.png'))
    ICON_INDI_REMOVE_FILE         = os.path.join(HOB_ICON_BASE_DIR, ('indicators/remove.png'))
    ICON_INDI_REMOVE_HOVER_FILE   = os.path.join(HOB_ICON_BASE_DIR, ('indicators/remove-hover.png'))
    ICON_INDI_ADD_FILE            = os.path.join(HOB_ICON_BASE_DIR, ('indicators/add.png'))
    ICON_INDI_ADD_HOVER_FILE      = os.path.join(HOB_ICON_BASE_DIR, ('indicators/add-hover.png'))
    ICON_INDI_REFRESH_FILE        = os.path.join(HOB_ICON_BASE_DIR, ('indicators/refresh.png'))
    ICON_INDI_ALERT_FILE          = os.path.join(HOB_ICON_BASE_DIR, ('indicators/alert.png'))
    ICON_INDI_TICK_FILE           = os.path.join(HOB_ICON_BASE_DIR, ('indicators/tick.png'))
    ICON_INDI_INFO_FILE           = os.path.join(HOB_ICON_BASE_DIR, ('indicators/info.png'))

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
        "vmdk"          : ["vmdk"],
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
         "cell-fadeinout-stopped" : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                           (gobject.TYPE_PYOBJECT,
                            gobject.TYPE_PYOBJECT,
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
            if 'expand' in column.keys():
                col.set_expand(True)
            self.table_tree.append_column(col)

            if (not 'col_style' in column.keys()) or column['col_style'] == 'text':
                cell = gtk.CellRendererText()
                col.pack_start(cell, True)
                col.set_attributes(cell, text=column['col_id'])
            elif column['col_style'] == 'check toggle':
                cell = HobCellRendererToggle()
                cell.set_property('activatable', True)
                cell.connect("toggled", self.toggled_cb, i, self.table_tree)
                cell.connect_render_state_changed(self.stop_cell_fadeinout_cb, self.table_tree)
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
            elif column['col_style'] == 'binb':
                cell = gtk.CellRendererText()
                col.pack_start(cell, True)
                col.set_cell_data_func(cell, self.display_binb_cb, column['col_id'])

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scroll.add(self.table_tree)
        self.pack_start(scroll, True, True, 0)

    def display_binb_cb(self, col, cell, model, it, col_id):
        binb =  model.get_value(it, col_id)
        # Just display the first item
        if binb:
            bin = binb.split(', ')
            cell.set_property('text', bin[0])
        else:
            cell.set_property('text', "")
        return True

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

    def stop_cell_fadeinout_cb(self, ctrl, cell, tree):
        self.emit("cell-fadeinout-stopped", ctrl, cell, tree)

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

class HobButton(gtk.Button):
    """
    A gtk.Button subclass which follows the visual design of Hob for primary
    action buttons

    label: the text to display as the button's label
    """
    def __init__(self, label):
        gtk.Button.__init__(self, label)
        HobButton.style_button(self)

    @staticmethod
    def style_button(button):
        style = button.get_style()
        button_color = gtk.gdk.Color(HobColors.ORANGE)
        button.modify_bg(gtk.STATE_NORMAL, button_color)
        button.modify_bg(gtk.STATE_PRELIGHT, button_color)
        button.modify_bg(gtk.STATE_SELECTED, button_color)

        button.set_flags(gtk.CAN_DEFAULT)
        button.grab_default()

        label = "<span size='x-large'><b>%s</b></span>" % gobject.markup_escape_text(button.get_label())
        button.set_label(label)
        button.child.set_use_markup(True)

class HobAltButton(gtk.Button):
    """
    A gtk.Button subclass which has no relief, and so is more discrete
    """
    def __init__(self, label):
        gtk.Button.__init__(self, label)
        HobAltButton.style_button(self)

    """
    A callback for the state-changed event to ensure the text is displayed
    differently when the widget is not sensitive
    """
    @staticmethod
    def desensitise_on_state_change_cb(button, state):
        if not button.get_property("sensitive"):
            HobAltButton.set_text(button, False)
        else:
            HobAltButton.set_text(button, True)

    """
    Set the button label with an appropriate colour for the current widget state
    """
    @staticmethod
    def set_text(button, sensitive=True):
        if sensitive:
            colour = HobColors.PALE_BLUE
        else:
            colour = HobColors.LIGHT_GRAY
        button.set_label("<span size='large' color='%s'><b>%s</b></span>" % (colour, gobject.markup_escape_text(button.text)))
        button.child.set_use_markup(True)

    @staticmethod
    def style_button(button):
        button.text = button.get_label()
        button.connect("state-changed", HobAltButton.desensitise_on_state_change_cb)
        HobAltButton.set_text(button)
        button.child.set_use_markup(True)
        button.set_relief(gtk.RELIEF_NONE)

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

        hbox = gtk.HBox(False, 10)
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
        mark = "<span size='x-large'>%s</span>\n<span size='medium' fgcolor='%s' weight='ultralight'>%s</span>" % (primary_text, colour, secondary_text)
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
        self.connect("query-tooltip", self.query_tooltip_cb)
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

    def append_tab_child(self, title, page, tooltip=""):
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
            "tooltip_markup"   : tooltip,
        }
        self.children.append(new_one)
        if tooltip and (not self.props.has_tooltip):
            self.props.has_tooltip = True
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
                if not child == self.current_child:
                    self.window.draw_layout(self.style.fg_gc[gtk.STATE_NORMAL], int(x), int(y), pangolayout, gtk.gdk.Color(HobColors.WHITE))
                else:
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
        if not child == self.current_child:
            color = cr.set_source_color(gtk.gdk.color_parse(HobColors.DEEP_RED))
        else:
            color = cr.set_source_color(gtk.gdk.color_parse(HobColors.GRAY))
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
        self.window.draw_layout(self.style.fg_gc[gtk.STATE_NORMAL], int(x), int(y), layout, gtk.gdk.Color(HobColors.WHITE))

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

    def query_tooltip_cb(self, widget, x, y, keyboardtip, tooltip):
        if keyboardtip or (not tooltip):
            return False
        # check which tab be clicked
        for child in self.children:
           if      (child["x"] < x) and (x < child["x"] + self.tab_width) \
               and (child["y"] < y) and (y < child["y"] + self.tab_height):
               tooltip.set_markup(child["tooltip_markup"])
               return True

        return False

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
        label = notebook.get_tab_label(notebook_child)
        tooltip_markup = label.get_tooltip_markup()
        if not title:
            return
        for child in self.tabbar.children:
            if child["title"] == title:
                child["toggled_page"] = page
                return
        self.tabbar.append_tab_child(title, page, tooltip_markup)

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

class HobWarpCellRendererText(gtk.CellRendererText):
    def __init__(self, col_number):
        gtk.CellRendererText.__init__(self)
        self.set_property("wrap-mode", pango.WRAP_WORD_CHAR)
        self.set_property("wrap-width", 300) # default value wrap width is 300
        self.col_n = col_number

    def do_render(self, window, widget, background_area, cell_area, expose_area, flags):
        if widget:
            self.props.wrap_width = self.get_resized_wrap_width(widget, widget.get_column(self.col_n))
        return gtk.CellRendererText.do_render(self, window, widget, background_area, cell_area, expose_area, flags)

    def get_resized_wrap_width(self, treeview, column):
        otherCols = []
        for col in treeview.get_columns():
            if col != column:
                otherCols.append(col)
        adjwidth = treeview.allocation.width - sum(c.get_width() for c in otherCols)
        adjwidth -= treeview.style_get_property("horizontal-separator") * 4
        if self.props.wrap_width == adjwidth or adjwidth <= 0:
                adjwidth = self.props.wrap_width
        return adjwidth

gobject.type_register(HobWarpCellRendererText)

class HobIconChecker(hic):
    def set_hob_icon_to_stock_icon(self, file_path, stock_id=""):
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(file_path)
        except Exception, e:
            return None

        if stock_id and (gtk.icon_factory_lookup_default(stock_id) == None):
            icon_factory = gtk.IconFactory()
            icon_factory.add_default()
            icon_factory.add(stock_id, gtk.IconSet(pixbuf))
            gtk.stock_add([(stock_id, '_label', 0, 0, '')])

            return icon_factory.lookup(stock_id)

        return None

    """
    For make hob icon consistently by request, and avoid icon view diff by system or gtk version, we use some 'hob icon' to replace the 'gtk icon'.
    this function check the stock_id and make hob_id to replaced the gtk_id then return it or ""
    """
    def check_stock_icon(self, stock_name=""):
        HOB_CHECK_STOCK_NAME = {
            ('hic-dialog-info', 'gtk-dialog-info', 'dialog-info')           : self.ICON_INDI_INFO_FILE,
            ('hic-ok',          'gtk-ok',           'ok')                   : self.ICON_INDI_TICK_FILE,
            ('hic-dialog-error', 'gtk-dialog-error', 'dialog-error')        : self.ICON_INDI_ERROR_FILE,
            ('hic-dialog-warning', 'gtk-dialog-warning', 'dialog-warning')  : self.ICON_INDI_ALERT_FILE,
            ('hic-task-refresh', 'gtk-execute', 'execute')                  : self.ICON_INDI_REFRESH_FILE,
        }
        valid_stock_id = stock_name
        if stock_name:
            for names, path in HOB_CHECK_STOCK_NAME.iteritems():
                if stock_name in names:
                    valid_stock_id = names[0]
                    if not gtk.icon_factory_lookup_default(valid_stock_id):
                        self.set_hob_icon_to_stock_icon(path, valid_stock_id)

        return valid_stock_id

class HobCellRendererController(gobject.GObject):
    (MODE_CYCLE_RUNNING, MODE_ONE_SHORT) = range(2)
    __gsignals__ = {
        "run-timer-stopped" : (gobject.SIGNAL_RUN_LAST,
                                gobject.TYPE_NONE,
                                ()),
    }
    def __init__(self, runningmode=MODE_CYCLE_RUNNING, is_draw_row=False):
        gobject.GObject.__init__(self)
        self.timeout_id = None
        self.current_angle_pos = 0.0
        self.step_angle = 0.0
        self.tree_headers_height = 0
        self.running_cell_areas = []
        self.running_mode = runningmode
        self.is_queue_draw_row_area = is_draw_row
        self.force_stop_enable = False

    def is_active(self):
        if self.timeout_id:
            return True
        else:
            return False

    def reset_run(self):
        self.force_stop()
        self.running_cell_areas = []
        self.current_angle_pos = 0.0
        self.step_angle = 0.0

    ''' time_iterval: (1~1000)ms, which will be as the basic interval count for timer
        init_usrdata: the current data which related the progress-bar will be at
        min_usrdata: the range of min of user data
        max_usrdata: the range of max of user data
        step: each step which you want to progress
        Note: the init_usrdata should in the range of from min to max, and max should > min
             step should < (max - min)
    '''
    def start_run(self, time_iterval, init_usrdata, min_usrdata, max_usrdata, step, tree):
        if (not time_iterval) or (not max_usrdata):
            return
        usr_range = (max_usrdata - min_usrdata) * 1.0
        self.current_angle_pos = (init_usrdata * 1.0) / usr_range
        self.step_angle = (step * 1) / usr_range
        self.timeout_id = gobject.timeout_add(int(time_iterval),
        self.make_image_on_progressing_cb, tree)
        self.tree_headers_height = self.get_treeview_headers_height(tree)
        self.force_stop_enable = False

    def force_stop(self):
        self.emit("run-timer-stopped")
        self.force_stop_enable = True
        if self.timeout_id:
            if gobject.source_remove(self.timeout_id):
                self.timeout_id = None

    def on_draw_pixbuf_cb(self, pixbuf, cr, x, y, img_width, img_height, do_refresh=True):
        if pixbuf:
            r = max(img_width/2, img_height/2)
            cr.translate(x + r, y + r)
            if do_refresh:
                cr.rotate(2 * math.pi * self.current_angle_pos)

            cr.set_source_pixbuf(pixbuf, -img_width/2, -img_height/2)
            cr.paint()

    def on_draw_fadeinout_cb(self, cr, color, x, y, width, height, do_fadeout=True):
        if do_fadeout:
            alpha = self.current_angle_pos * 0.8
        else:
            alpha = (1.0 - self.current_angle_pos) * 0.8

        cr.set_source_rgba(color.red, color.green, color.blue, alpha)
        cr.rectangle(x, y, width, height)
        cr.fill()

    def get_treeview_headers_height(self, tree):
        if tree and (tree.get_property("headers-visible") == True):
            height = tree.get_allocation().height - tree.get_bin_window().get_size()[1]
            return height

        return 0

    def make_image_on_progressing_cb(self, tree):
        self.current_angle_pos += self.step_angle
        if self.running_mode == self.MODE_CYCLE_RUNNING:
            if (self.current_angle_pos >= 1):
                self.current_angle_pos = self.step_angle
        else:
            if self.current_angle_pos > 1:
                self.force_stop()
                return False

        if self.is_queue_draw_row_area:
            for path in self.running_cell_areas:
                rect = tree.get_cell_area(path, tree.get_column(0))
                row_x, _, row_width, _ = tree.get_visible_rect()
                tree.queue_draw_area(row_x, rect.y + self.tree_headers_height, row_width, rect.height)
        else:
            for rect in self.running_cell_areas:
                tree.queue_draw_area(rect.x, rect.y + self.tree_headers_height, rect.width, rect.height)

        return (not self.force_stop_enable)

    def append_running_cell_area(self, cell_area):
        if cell_area and (cell_area not in self.running_cell_areas):
            self.running_cell_areas.append(cell_area)

    def remove_running_cell_area(self, cell_area):
        if cell_area in self.running_cell_areas:
            self.running_cell_areas.remove(cell_area)
        if not self.running_cell_areas:
            self.reset_run()

gobject.type_register(HobCellRendererController)

class HobCellRendererPixbuf(gtk.CellRendererPixbuf):
    def __init__(self):
        gtk.CellRendererPixbuf.__init__(self)
        self.control = HobCellRendererController()
        # add icon checker for make the gtk-icon transfer to hob-icon
        self.checker = HobIconChecker()
        self.set_property("stock-size", gtk.ICON_SIZE_DND)

    def get_pixbuf_from_stock_icon(self, widget, stock_id="", size=gtk.ICON_SIZE_DIALOG):
        if widget and stock_id and gtk.icon_factory_lookup_default(stock_id):
            return widget.render_icon(stock_id, size)

        return None

    def set_icon_name_to_id(self, new_name):
        if new_name and type(new_name) == str:
            # check the name is need to transfer to hob icon or not
            name = self.checker.check_stock_icon(new_name)
            if name.startswith("hic") or name.startswith("gtk"):
                stock_id = name
            else:
                stock_id = 'gtk-' + name

        return stock_id

    ''' render cell exactly, "icon-name" is priority
        if use the 'hic-task-refresh' will make the pix animation
        if 'pix' will change the pixbuf for it from the pixbuf or image.
    '''
    def do_render(self, window, tree, background_area,cell_area, expose_area, flags):
        if (not self.control) or (not tree):
            return

        x, y, w, h = self.on_get_size(tree, cell_area)
        x += cell_area.x
        y += cell_area.y
        w -= 2 * self.get_property("xpad")
        h -= 2 * self.get_property("ypad")

        stock_id = ""
        if self.props.icon_name:
            stock_id = self.set_icon_name_to_id(self.props.icon_name)
        elif self.props.stock_id:
            stock_id = self.props.stock_id
        elif self.props.pixbuf:
            pix = self.props.pixbuf
        else:
            return

        if stock_id:
            pix = self.get_pixbuf_from_stock_icon(tree, stock_id, self.props.stock_size)
        if stock_id == 'hic-task-refresh':
            self.control.append_running_cell_area(cell_area)
            if self.control.is_active():
                self.control.on_draw_pixbuf_cb(pix, window.cairo_create(), x, y, w, h, True)
            else:
                self.control.start_run(200, 0, 0, 1000, 200, tree)
        else:
            self.control.remove_running_cell_area(cell_area)
            self.control.on_draw_pixbuf_cb(pix, window.cairo_create(), x, y, w, h, False)

    def on_get_size(self, widget, cell_area):
        if self.props.icon_name or self.props.pixbuf or self.props.stock_id:
            w, h = gtk.icon_size_lookup(self.props.stock_size)
            calc_width = self.get_property("xpad") * 2 + w
            calc_height = self.get_property("ypad") * 2 + h
            x_offset = 0
            y_offset = 0
            if cell_area and w > 0 and h > 0:
                x_offset = self.get_property("xalign") * (cell_area.width - calc_width - self.get_property("xpad"))
                y_offset = self.get_property("yalign") * (cell_area.height - calc_height - self.get_property("ypad"))

            return x_offset, y_offset, w, h

        return 0, 0, 0, 0

gobject.type_register(HobCellRendererPixbuf)

class HobCellRendererToggle(gtk.CellRendererToggle):
    def __init__(self):
        gtk.CellRendererToggle.__init__(self)
        self.ctrl = HobCellRendererController(is_draw_row=True)
        self.ctrl.running_mode = self.ctrl.MODE_ONE_SHORT
        self.cell_attr = {"fadeout": False}

    def do_render(self, window, widget, background_area, cell_area, expose_area, flags):
        if (not self.ctrl) or (not widget):
            return
        if self.ctrl.is_active():
            path = widget.get_path_at_pos(cell_area.x + cell_area.width/2, cell_area.y + cell_area.height/2)
            # sometimes the parameters of cell_area will be a negative number,such as pull up down the scroll bar
            # it's over the tree container range, so the path will be bad
            if not path: return
            path = path[0]
            if path in self.ctrl.running_cell_areas:
                cr = window.cairo_create()
                color = gtk.gdk.Color(HobColors.WHITE)

                row_x, _, row_width, _ = widget.get_visible_rect()
                border_y = self.get_property("ypad")
                self.ctrl.on_draw_fadeinout_cb(cr, color, row_x, cell_area.y - border_y, row_width, \
                                               cell_area.height + border_y * 2, self.cell_attr["fadeout"])

        return gtk.CellRendererToggle.do_render(self, window, widget, background_area, cell_area, expose_area, flags)

    '''delay: normally delay time is 1000ms
       cell_list: whilch cells need to be render
    '''
    def fadeout(self, tree, delay, cell_list=None):
        if (delay < 200) or (not tree):
            return
        self.cell_attr["fadeout"] = True
        self.ctrl.running_cell_areas = cell_list
        self.ctrl.start_run(200, 0, 0, delay, (delay * 200 / 1000), tree)

    def connect_render_state_changed(self, func, usrdata=None):
        if not func:
            return
        if usrdata:
            self.ctrl.connect("run-timer-stopped", func, self, usrdata)
        else:
            self.ctrl.connect("run-timer-stopped", func, self)

gobject.type_register(HobCellRendererToggle)
