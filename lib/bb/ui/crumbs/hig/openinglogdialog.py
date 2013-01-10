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
import gobject
from bb.ui.crumbs.hobwidget import HobAltButton
from bb.ui.crumbs.progressbar import HobProgressBar
from bb.ui.crumbs.hig.crumbsdialog import CrumbsDialog

"""
The following are convenience classes for implementing GNOME HIG compliant
BitBake GUI's
In summary: spacing = 12px, border-width = 6px
"""

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
