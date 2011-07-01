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
from bb.ui.crumbs.configurator import Configurator

class LayerEditor(gtk.Dialog):
    """
    Gtk+ Widget for enabling and disabling layers.
    Layers are added through using an open dialog to find the layer.conf
    Disabled layers are deleted from conf/bblayers.conf
    """
    def __init__(self, configurator, parent=None):
        gtk.Dialog.__init__(self, "Layers", None,
                            gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CLOSE, gtk.RESPONSE_OK))

        # We want to show a little more of the treeview in the default,
        # emptier, case
        self.set_size_request(-1, 300)
        self.set_border_width(6)
        self.vbox.set_property("spacing", 0)
        self.action_area.set_property("border-width", 6)

        self.configurator = configurator
        self.newly_added = {}

        # Label to inform users that meta is enabled but that you can't
        # disable it as it'd be a *bad* idea
        msg = "As the core of the build system the <i>meta</i> layer must always be included and therefore can't be viewed or edited here."
        lbl = gtk.Label()
        lbl.show()
        lbl.set_use_markup(True)
        lbl.set_markup(msg)
        lbl.set_line_wrap(True)
        lbl.set_justify(gtk.JUSTIFY_FILL)
        self.vbox.pack_start(lbl, expand=False, fill=False, padding=6)

        # Create a treeview in which to list layers
        # ListStore of Name, Path, Enabled
        self.layer_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        self.tv = gtk.TreeView(self.layer_store)
        self.tv.set_headers_visible(True)

        col0 = gtk.TreeViewColumn('Name')
        self.tv.append_column(col0)
        col1 = gtk.TreeViewColumn('Path')
        self.tv.append_column(col1)
        col2 = gtk.TreeViewColumn('Enabled')
        self.tv.append_column(col2)

        cell0 = gtk.CellRendererText()
        col0.pack_start(cell0, True)
        col0.set_attributes(cell0, text=0)
        cell1 = gtk.CellRendererText()
        col1.pack_start(cell1, True)
        col1.set_attributes(cell1, text=1)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self._toggle_layer_cb)
        col2.pack_start(cell2, True)
        col2.set_attributes(cell2, active=2)

        self.tv.show()
        self.vbox.pack_start(self.tv, expand=True, fill=True, padding=0)

        tb = gtk.Toolbar()
        tb.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        tb.set_style(gtk.TOOLBAR_BOTH)
        tb.set_tooltips(True)
        tb.show()
        icon = gtk.Image()
        icon.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_SMALL_TOOLBAR)
        icon.show()
        tb.insert_item("Add Layer", "Add new layer", None, icon,
                       self._find_layer_cb, None, -1)
        self.vbox.pack_start(tb, expand=False, fill=False, padding=0)

    def set_parent_window(self, parent):
        self.set_transient_for(parent)

    def load_current_layers(self, data):
        for layer, path in self.configurator.enabled_layers.items():
            if layer != 'meta':
                self.layer_store.append([layer, path, True])

    def save_current_layers(self):
        self.configurator.writeLayerConf()

    def _toggle_layer_cb(self, cell, path):
        name = self.layer_store[path][0]
        toggle = not self.layer_store[path][2]
        if toggle:
            self.configurator.addLayer(name, path)
        else:
            self.configurator.disableLayer(name)
        self.layer_store[path][2] = toggle

    def _find_layer_cb(self, button):
        self.find_layer(self)

    def find_layer(self, parent):
        dialog = gtk.FileChooserDialog("Add new layer", parent,
                                       gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_NO,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_YES))
        label = gtk.Label("Select the layer.conf of the layer you wish to add")
        label.show()
        dialog.set_extra_widget(label)
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()

        if response == gtk.RESPONSE_YES:
            # FIXME: verify we've actually got a layer conf?
            if path.endswith(".conf"):
                name, layerpath = self.configurator.addLayerConf(path)
                self.newly_added[name] = layerpath
                self.layer_store.append([name, layerpath, True])
