#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2012   Intel Corporation
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
try:
    import gconf
except:
    pass

class PersistentTooltip(gtk.Window):
	"""
	A tooltip which persists once shown until the user dismisses it with the Esc
	key or by clicking the close button.

	# FIXME: the PersistentTooltip should be disabled when the user clicks anywhere off
	# it. We can't do this with focus-out-event becuase modal ensures we have focus?

	markup: some Pango text markup to display in the tooltip
	"""
	def __init__(self, markup):
		gtk.Window.__init__(self, gtk.WINDOW_POPUP)

		# The placement of the close button on the tip should reflect how the
		# window manager of the users system places close buttons. Try to read
		# the metacity gconf key to determine whether the close button is on the
		# left or the right.
		# In the case that we can't determine the users configuration we default
		# to close buttons being on the right.
		__button_right = True
		try:
		    client = gconf.client_get_default()
		    order = client.get_string("/apps/metacity/general/button_layout")
		    if order and order.endswith(":"):
		        __button_right = False
		except NameError:
			pass

		# We need to ensure we're only shown once
		self.shown = False

		# We don't want any WM decorations
		self.set_decorated(False)
		# We don't want to show in the taskbar or window switcher
		self.set_skip_pager_hint(True)
		self.set_skip_taskbar_hint(True)
		# We must be modal to ensure we grab focus when presented from a gtk.Dialog
		self.set_modal(True)

		self.set_border_width(6)
		self.set_position(gtk.WIN_POS_MOUSE)
		self.set_opacity(0.95)

		# Draw our label and close buttons
		hbox = gtk.HBox(False, 0)
		hbox.show()
		vbox = gtk.VBox(False, 0)
		vbox.show()
		vbox.pack_start(hbox, True, True, 0)

		img = gtk.Image()
		img.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_BUTTON)

		self.button = gtk.Button()
		self.button.set_image(img)
		self.button.connect("clicked", self._dismiss_cb)
		self.button.set_can_default(True)
		self.button.grab_focus()
		self.button.show()
		if __button_right:
		    hbox.pack_end(self.button, False, False, 0)
		else:
		    hbox.pack_start(self.button, False, False, 0)

		self.set_default(self.button)

		self.label = gtk.Label()
		self.label.set_markup(markup)
		self.label.show()
		vbox.pack_end(self.label, True, True, 6)

		self.connect("key-press-event", self._catch_esc_cb)

		# Inherit the system theme for a tooltip
		style = gtk.rc_get_style_by_paths(gtk.settings_get_default(),
			'gtk-tooltip', 'gtk-tooltip', gobject.TYPE_NONE)
		self.set_style(style)

		self.add(vbox)

	"""
	Callback when the PersistentTooltip's close button is clicked.
	Hides the PersistentTooltip.
	"""
	def _dismiss_cb(self, button):
		self.hide()
		return True

	"""
	Callback when the Esc key is detected. Hides the PersistentTooltip.
	"""
	def _catch_esc_cb(self, widget, event):
		keyname = gtk.gdk.keyval_name(event.keyval)
		if keyname == "Escape":
			self.hide()
		return True

	"""
	Called to present the PersistentTooltip.
	Overrides the superclasses show() method to include state tracking.
	"""
	def show(self):
		if not self.shown:
			self.shown = True
			gtk.Window.show(self)

	"""
	Called to hide the PersistentTooltip.
	Overrides the superclasses hide() method to include state tracking.
	"""
	def hide(self):
		self.shown = False
		gtk.Window.hide(self)
