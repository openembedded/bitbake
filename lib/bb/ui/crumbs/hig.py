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

import gobject
import gtk
"""
The following are convenience classes for implementing GNOME HIG compliant
BitBake GUI's
In summary: spacing = 12px, border-width = 6px
"""

class CrumbsDialog(gtk.Dialog):
    """
    A GNOME HIG compliant dialog widget.
    Add buttons with gtk.Dialog.add_button or gtk.Dialog.add_buttons
    """
    def __init__(self, parent=None, label="", icon=gtk.STOCK_INFO):
        gtk.Dialog.__init__(self, "", parent, gtk.DIALOG_DESTROY_WITH_PARENT)
        
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
