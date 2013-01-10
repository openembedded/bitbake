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

import glib
import gtk
from bb.ui.crumbs.hobwidget import HobIconChecker
from bb.ui.crumbs.hig.crumbsdialog import CrumbsDialog

"""
The following are convenience classes for implementing GNOME HIG compliant
BitBake GUI's
In summary: spacing = 12px, border-width = 6px
"""

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
