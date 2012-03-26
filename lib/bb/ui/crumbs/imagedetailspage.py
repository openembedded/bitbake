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

import gobject
import gtk
from bb.ui.crumbs.hobcolor import HobColors
from bb.ui.crumbs.hobwidget import hic, HobViewTable, HobAltButton, HobButton
from bb.ui.crumbs.hobpages import HobPage

#
# ImageDetailsPage
#
class ImageDetailsPage (HobPage):

    __columns__ = [{
            'col_name' : 'Image name',
            'col_id'   : 0,
            'col_style': 'text',
            'col_min'  : 500,
            'col_max'  : 500
        }, {
            'col_name' : 'Image size',
            'col_id'   : 1,
            'col_style': 'text',
            'col_min'  : 100,
            'col_max'  : 100
        }, {
            'col_name' : 'Select',
            'col_id'   : 2,
            'col_style': 'radio toggle',
            'col_min'  : 100,
            'col_max'  : 100
    }]

    class DetailBox (gtk.EventBox):
        def __init__(self, widget = None, varlist = None, vallist = None, icon = None, button = None, color = HobColors.LIGHT_GRAY):
            gtk.EventBox.__init__(self)

            # set color
            style = self.get_style().copy()
            style.bg[gtk.STATE_NORMAL] = self.get_colormap().alloc_color(color, False, False)
            self.set_style(style)

            self.hbox = gtk.HBox()
            self.hbox.set_border_width(15)
            self.add(self.hbox)

            if widget:
                row = 1
            elif varlist and vallist:
                # pack the icon and the text on the left
                row = len(varlist)
            self.table = gtk.Table(row, 20, True)
            self.table.set_size_request(100, -1)
            self.hbox.pack_start(self.table, expand=True, fill=True, padding=15)

            colid = 0
            self.line_widgets = {}
            if icon:
                self.table.attach(icon, colid, colid + 2, 0, 1)
                colid = colid + 2
            if widget:
                self.table.attach(widget, colid, 20, 0, 1)
            elif varlist and vallist:
                for line in range(0, row):
                    self.line_widgets[varlist[line]] = self.text2label(varlist[line], vallist[line])
                    self.table.attach(self.line_widgets[varlist[line]], colid, 20, line, line + 1)

            # pack the button on the right
            if button:
                self.hbox.pack_end(button, expand=False, fill=False)

        def update_line_widgets(self, variable, value):
            if len(self.line_widgets) == 0:
                return
            if not isinstance(self.line_widgets[variable], gtk.Label):
                return
            self.line_widgets[variable].set_markup(self.format_line(variable, value))

        def format_line(self, variable, value):
            markup = "<span weight=\'bold\'>%s</span>" % variable
            markup += "<span weight=\'normal\' foreground=\'#1c1c1c\' font_desc=\'14px\'>%s</span>" % value
            return markup

        def text2label(self, variable, value):
            # append the name:value to the left box
            # such as "Name: hob-core-minimal-variant-2011-12-15-beagleboard"
            label = gtk.Label()
            label.set_alignment(0.0, 0.5)
            label.set_markup(self.format_line(variable, value))
            return label

    def __init__(self, builder):
        super(ImageDetailsPage, self).__init__(builder, "Image details")

        self.image_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        self.create_visual_elements()

    def create_visual_elements(self):
        # create visual elements
        # create the toolbar
        self.toolbar = gtk.Toolbar()
        self.toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.toolbar.set_style(gtk.TOOLBAR_BOTH)

        my_images_button = self.append_toolbar_button(self.toolbar,
            "My images",
            hic.ICON_IMAGES_DISPLAY_FILE,
            hic.ICON_IMAGES_HOVER_FILE,
            "Open images built out previously for running or deployment",
            self.my_images_button_clicked_cb)

        self.details_top_buttons = self.add_onto_top_bar(self.toolbar)

    def _remove_all_widget(self):
        children = self.get_children() or []
        for child in children:
            self.remove(child)
        children = self.box_group_area.get_children() or []
        for child in children:
            self.box_group_area.remove(child)

    def _size_to_string(self, size):
        if len(str(int(size))) > 6:
            size_str = '%.1f' % (size*1.0/(1024*1024)) + ' MB'
        elif len(str(int(size))) > 3:
            size_str = '%.1f' % (size*1.0/1024) + ' KB'
        else:
            size_str = str(size) + ' B'
        return size_str

    def show_page(self, step):
        build_succeeded = (step == self.builder.IMAGE_GENERATED)
        image_addr = self.builder.parameters.image_addr
        image_names = self.builder.parameters.image_names
        if build_succeeded:
            machine = self.builder.configuration.curr_mach
            base_image = self.builder.recipe_model.get_selected_image()
            layers = self.builder.configuration.layers
            pkg_num = "%s" % len(self.builder.package_model.get_selected_packages())
        else:
            pkg_num = "N/A"

        self._remove_all_widget()
        self.pack_start(self.details_top_buttons, expand=False, fill=False)
        self.pack_start(self.group_align, expand=True, fill=True)

        if build_succeeded:
            # building is the previous step
            icon = gtk.Image()
            pixmap_path = hic.ICON_INDI_CONFIRM_FILE
            color = HobColors.RUNNING
            pix_buffer = gtk.gdk.pixbuf_new_from_file(pixmap_path)
            icon.set_from_pixbuf(pix_buffer)
            varlist = [""]
            vallist = ["Your image is ready"]
            build_result = self.DetailBox(varlist=varlist, vallist=vallist, icon=icon, color=color)
            self.box_group_area.pack_start(build_result, expand=False, fill=False)

        # create the buttons at the bottom first because the buttons are used in apply_button_per_image()
        if build_succeeded:
            buttonlist = ["Build new image", "Save as template", "Run image", "Deploy image"]
        else: # get to this page from "My images"
            buttonlist = ["Build new image", "Run image", "Deploy image"]
        details_bottom_buttons = self.create_bottom_buttons(buttonlist)

        # Name
        self.image_store.clear()
        default_toggled = False
        default_image_size = 0
        for image_name in image_names:
            image_size = self._size_to_string(os.stat(os.path.join(image_addr, image_name)).st_size)
            if not default_toggled:
                default_toggled = (self.test_type_runnable(image_name) and self.test_mach_runnable(image_name)) \
                    or self.test_deployable(image_name)
                self.image_store.set(self.image_store.append(), 0, image_name, 1, image_size, 2, default_toggled)
                if default_toggled:
                    default_image_size = image_size
                self.apply_buttons_per_image(image_name)
            else:
                self.image_store.set(self.image_store.append(), 0, image_name, 1, image_size, 2, False)
        image_table = HobViewTable(self.__columns__)
        image_table.set_model(self.image_store)
        image_table.connect("toggled", self.toggled_cb)
        view_files_button = HobAltButton("View files")
        view_files_button.connect("clicked", self.view_files_clicked_cb, image_addr)
        self.box_group_area.pack_start(self.DetailBox(widget=image_table, button=view_files_button), expand=True, fill=True)

        # Machine, Base image and Layers
        layer_num_limit = 15
        varlist = ["Machine: ", "Base image: ", "Layers: "]
        vallist = []
        if build_succeeded:
            vallist.append(machine)
            vallist.append(base_image)
            i = 0
            for layer in layers:
                varlist.append(" - ")
                if i > layer_num_limit:
                    break
                i += 1
            vallist.append("")
            i = 0
            for layer in layers:
                if i > layer_num_limit:
                    break
                elif i == layer_num_limit:
                    vallist.append("and more...")
                else:
                    vallist.append(layer)
                i += 1

            edit_config_button = HobAltButton("Edit configuration")
            edit_config_button.connect("clicked", self.edit_config_button_clicked_cb)
            setting_detail = self.DetailBox(varlist=varlist, vallist=vallist, button=edit_config_button)
            self.box_group_area.pack_start(setting_detail, expand=False, fill=False)

        # Packages included, and Total image size
        varlist = ["Packages included: ", "Total image size: "]
        vallist = []
        vallist.append(pkg_num)
        vallist.append(default_image_size)
        if build_succeeded:
            edit_packages_button = HobAltButton("Edit packages")
            edit_packages_button.connect("clicked", self.edit_packages_button_clicked_cb)
        else: # get to this page from "My images"
            edit_packages_button = None
        self.package_detail = self.DetailBox(varlist=varlist, vallist=vallist, button=edit_packages_button)
        self.box_group_area.pack_start(self.package_detail, expand=False, fill=False)

        # pack the buttons at the bottom, at this time they are already created.
        self.box_group_area.pack_end(details_bottom_buttons, expand=False, fill=False)

        self.show_all()

    def view_files_clicked_cb(self, button, image_addr):
        os.system("xdg-open /%s" % image_addr)

    def refresh_package_detail_box(self, image_size):
        self.package_detail.update_line_widgets("Total image size: ", image_size)

    def test_type_runnable(self, image_name):
        type_runnable = False
        for t in self.builder.parameters.runnable_image_types:
            if image_name.endswith(t):
                type_runnable = True
                break
        return type_runnable

    def test_mach_runnable(self, image_name):
        mach_runnable = False
        for t in self.builder.parameters.runnable_machine_patterns:
            if t in image_name:
                mach_runnable = True
                break
        return mach_runnable

    def test_deployable(self, image_name):
        deployable = False
        for t in self.builder.parameters.deployable_image_types:
            if image_name.endswith(t):
                deployable = True
                break
        return deployable

    def apply_buttons_per_image(self, image_name):
        self.run_button.set_sensitive(self.test_type_runnable(image_name) and self.test_mach_runnable(image_name))
        self.deploy_button.set_sensitive(self.test_deployable(image_name))

    def toggled_cb(self, table, cell, path, columnid, tree):
        model = tree.get_model()
        if not model:
            return
        iter = model.get_iter_first()
        while iter:
            rowpath = model.get_path(iter)
            model[rowpath][columnid] = False
            iter = model.iter_next(iter)

        model[path][columnid] = True
        self.refresh_package_detail_box(model[path][1])

        image_name = model[path][0]
        self.apply_buttons_per_image(image_name)

    def create_bottom_buttons(self, buttonlist):
        # Create the buttons at the bottom
        bottom_buttons = gtk.HBox(False, 6)
        created = False

        # create button "Deploy image"
        name = "Deploy image"
        if name in buttonlist:
            self.deploy_button = HobButton('Deploy image')
            self.deploy_button.set_size_request(205, 49)
            self.deploy_button.set_tooltip_text("Deploy image to get your target board")
            self.deploy_button.set_flags(gtk.CAN_DEFAULT)
            self.deploy_button.grab_default()
            self.deploy_button.connect("clicked", self.deploy_button_clicked_cb)
            bottom_buttons.pack_end(self.deploy_button, expand=False, fill=False)
            created = True

        name = "Run image"
        if name in buttonlist:
            if created == True:
                # separator
                label = gtk.Label(" or ")
                bottom_buttons.pack_end(label, expand=False, fill=False)

            # create button "Run image"
            self.run_button = HobAltButton("Run image")
            self.run_button.connect("clicked", self.run_button_clicked_cb)
            bottom_buttons.pack_end(self.run_button, expand=False, fill=False)
            created = True

        name = "Save as template"
        if name in buttonlist:
            if created == True:
                # separator
                label = gtk.Label(" or ")
                bottom_buttons.pack_end(label, expand=False, fill=False)

            # create button "Save as template"
            save_button = HobAltButton("Save as template")
            save_button.connect("clicked", self.save_button_clicked_cb)
            bottom_buttons.pack_end(save_button, expand=False, fill=False)
            create = True

        name = "Build new image"
        if name in buttonlist:
            # create button "Build new image"
            build_new_button = HobAltButton("Build new image")
            build_new_button.connect("clicked", self.build_new_button_clicked_cb)
            bottom_buttons.pack_start(build_new_button, expand=False, fill=False)

        return bottom_buttons

    def _get_selected_image(self):
        image_name = ""
        iter = self.image_store.get_iter_first()
        while iter:
            path = self.image_store.get_path(iter)
            if self.image_store[path][2]:
                image_name = self.image_store[path][0]
                break
            iter = self.image_store.iter_next(iter)

        return image_name

    def save_button_clicked_cb(self, button):
        self.builder.show_save_template_dialog()

    def deploy_button_clicked_cb(self, button):
        image_name = self._get_selected_image()
        self.builder.deploy_image(image_name)

    def run_button_clicked_cb(self, button):
        image_name = self._get_selected_image()
        self.builder.runqemu_image(image_name)

    def build_new_button_clicked_cb(self, button):
        self.builder.initiate_new_build()

    def edit_config_button_clicked_cb(self, button):
        self.builder.show_configuration()

    def edit_packages_button_clicked_cb(self, button):
        self.builder.show_packages(ask=False)

    def my_images_button_clicked_cb(self, button):
        self.builder.show_load_my_images_dialog()
