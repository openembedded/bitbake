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
from bb.ui.crumbs.progressbar import HobProgressBar
from bb.ui.crumbs.hobcolor import HobColors
from bb.ui.crumbs.hobwidget import hic, HobImageButton, HobInfoButton, HobAltButton, HobButton
from bb.ui.crumbs.hoblistmodel import RecipeListModel
from bb.ui.crumbs.hobpages import HobPage

#
# ImageConfigurationPage
#
class ImageConfigurationPage (HobPage):

    def __init__(self, builder):
        super(ImageConfigurationPage, self).__init__(builder, "Image configuration")

        self.image_combo_id = None
        # we use machine_combo_changed_by_manual to identify the machine is changed by code
        # or by manual. If by manual, all user's recipe selection and package selection are
        # cleared.
        self.machine_combo_changed_by_manual = True
        self.create_visual_elements()

    def create_visual_elements(self):
        # create visual elements
        self.toolbar = gtk.Toolbar()
        self.toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.toolbar.set_style(gtk.TOOLBAR_BOTH)

        template_button = self.append_toolbar_button(self.toolbar,
            "Templates",
            hic.ICON_TEMPLATES_DISPLAY_FILE,
            hic.ICON_TEMPLATES_HOVER_FILE,
            "Load a previously saved template",
            self.template_button_clicked_cb)
        my_images_button = self.append_toolbar_button(self.toolbar,
            "Images",
            hic.ICON_IMAGES_DISPLAY_FILE,
            hic.ICON_IMAGES_HOVER_FILE,
            "Open previously built images",
            self.my_images_button_clicked_cb)
        settings_button = self.append_toolbar_button(self.toolbar,
            "Settings",
            hic.ICON_SETTINGS_DISPLAY_FILE,
            hic.ICON_SETTINGS_HOVER_FILE,
            "View additional build settings",
            self.settings_button_clicked_cb)

        self.config_top_button = self.add_onto_top_bar(self.toolbar)

        self.gtable = gtk.Table(40, 40, True)
        self.create_config_machine()
        self.create_config_baseimg()
        self.config_build_button = self.create_config_build_button()

    def _remove_all_widget(self):
        children = self.gtable.get_children() or []
        for child in children:
            self.gtable.remove(child)
        children = self.box_group_area.get_children() or []
        for child in children:
            self.box_group_area.remove(child)
        children = self.get_children() or []
        for child in children:
            self.remove(child)

    def _pack_components(self, pack_config_build_button = False):
        self._remove_all_widget()
        self.pack_start(self.config_top_button, expand=False, fill=False)
        self.pack_start(self.group_align, expand=True, fill=True)

        self.box_group_area.pack_start(self.gtable, expand=True, fill=True)
        if pack_config_build_button:
            self.box_group_area.pack_end(self.config_build_button, expand=False, fill=False)
        else:
            box = gtk.HBox(False, 6)
            box.show()
            subbox = gtk.HBox(False, 0)
            subbox.set_size_request(205, 49)
            subbox.show()
            box.add(subbox)
            self.box_group_area.pack_end(box, False, False)

    def show_machine(self):
        self.progress_bar.reset()
        self._pack_components(pack_config_build_button = False)
        self.set_config_machine_layout(show_progress_bar = False)
        self.show_all()

    def update_progress_bar(self, title, fraction, status=None):
        self.progress_bar.update(fraction)
        self.progress_bar.set_title(title)
        self.progress_bar.set_rcstyle(status)

    def show_info_populating(self):
        self._pack_components(pack_config_build_button = False)
        self.set_config_machine_layout(show_progress_bar = True)
        self.show_all()

    def show_info_populated(self):
        self.progress_bar.reset()
        self._pack_components(pack_config_build_button = False)
        self.set_config_machine_layout(show_progress_bar = False)
        self.set_config_baseimg_layout()
        self.show_all()

    def show_baseimg_selected(self):
        self.progress_bar.reset()
        self._pack_components(pack_config_build_button = True)
        self.set_config_machine_layout(show_progress_bar = False)
        self.set_config_baseimg_layout()
        self.set_rcppkg_layout()
        self.show_all()

    def create_config_machine(self):
        self.machine_title = gtk.Label()
        self.machine_title.set_alignment(0.0, 0.5)
        mark = "<span %s>Select a machine</span>" % self.span_tag('x-large', 'bold')
        self.machine_title.set_markup(mark)

        self.machine_title_desc = gtk.Label()
        self.machine_title_desc.set_alignment(0.0, 0.5)
        mark = ("<span %s>Your selection is the profile of the target machine for which you"
        " are building the image.\n</span>") % (self.span_tag('medium'))
        self.machine_title_desc.set_markup(mark)

        self.machine_combo = gtk.combo_box_new_text()
        self.machine_combo.set_wrap_width(1)
        self.machine_combo.connect("changed", self.machine_combo_changed_cb)

        icon_file = hic.ICON_LAYERS_DISPLAY_FILE
        hover_file = hic.ICON_LAYERS_HOVER_FILE
        self.layer_button = HobImageButton("Layers", "Add support for machines, software, etc.",
                                icon_file, hover_file)
        self.layer_button.connect("clicked", self.layer_button_clicked_cb)

        markup = "Layers are a powerful mechanism to extend the Yocto Project "
        markup += "with your own functionality.\n"
        markup += "For more on layers, check the <a href=\""
        markup += "http://www.yoctoproject.org/docs/current/dev-manual/"
        markup += "dev-manual.html#understanding-and-using-layers\">reference manual</a>."
        self.layer_info_icon = HobInfoButton(markup, self.get_parent())

        self.progress_box = gtk.HBox(False, 6)
        self.progress_bar = HobProgressBar()
        self.progress_box.pack_start(self.progress_bar, expand=True, fill=True)
        self.stop_button = HobAltButton("Stop")
        self.stop_button.connect("clicked", self.stop_button_clicked_cb)
        self.progress_box.pack_end(self.stop_button, expand=False, fill=False)

        self.machine_separator = gtk.HSeparator()

    def set_config_machine_layout(self, show_progress_bar = False):
        self.gtable.attach(self.machine_title, 0, 40, 0, 4)
        self.gtable.attach(self.machine_title_desc, 0, 40, 4, 6)
        self.gtable.attach(self.machine_combo, 0, 12, 7, 10)
        self.gtable.attach(self.layer_button, 14, 36, 7, 12)
        self.gtable.attach(self.layer_info_icon, 36, 40, 7, 11)
        if show_progress_bar:
            self.gtable.attach(self.progress_box, 0, 40, 15, 19)
        self.gtable.attach(self.machine_separator, 0, 40, 13, 14)

    def create_config_baseimg(self):
        self.image_title = gtk.Label()
        self.image_title.set_alignment(0, 1.0)
        mark = "<span %s>Select a base image</span>" % self.span_tag('x-large', 'bold')
        self.image_title.set_markup(mark)

        self.image_title_desc = gtk.Label()
        self.image_title_desc.set_alignment(0, 0.5)
        mark = ("<span %s>Base images are a starting point for the type of image you want. "
                "You can build them as \n"
                "they are or customize them to your specific needs.\n</span>") % self.span_tag('medium')
        self.image_title_desc.set_markup(mark)

        self.image_combo = gtk.combo_box_new_text()
        self.image_combo.set_wrap_width(1)
        self.image_combo_id = self.image_combo.connect("changed", self.image_combo_changed_cb)

        self.image_desc = gtk.Label()
        self.image_desc.set_alignment(0.0, 0.5)
        self.image_desc.set_line_wrap(True)

        # button to view recipes
        icon_file = hic.ICON_RCIPE_DISPLAY_FILE
        hover_file = hic.ICON_RCIPE_HOVER_FILE
        self.view_recipes_button = HobImageButton("View recipes",
                                        "Add/remove recipes and tasks",
                                        icon_file, hover_file)
        self.view_recipes_button.connect("clicked", self.view_recipes_button_clicked_cb)

        # button to view packages
        icon_file = hic.ICON_PACKAGES_DISPLAY_FILE
        hover_file = hic.ICON_PACKAGES_HOVER_FILE
        self.view_packages_button = HobImageButton("View packages",
                                        "Add/remove previously built packages",
                                        icon_file, hover_file)
        self.view_packages_button.connect("clicked", self.view_packages_button_clicked_cb)

        self.image_separator = gtk.HSeparator()

    def set_config_baseimg_layout(self):
        self.gtable.attach(self.image_title, 0, 40, 15, 17)
        self.gtable.attach(self.image_title_desc, 0, 40, 18, 22)
        self.gtable.attach(self.image_combo, 0, 12, 23, 26)
        self.gtable.attach(self.image_desc, 13, 38, 23, 28)
        self.gtable.attach(self.image_separator, 0, 40, 35, 36)

    def set_rcppkg_layout(self):
        self.gtable.attach(self.view_recipes_button, 0, 20, 28, 33)
        self.gtable.attach(self.view_packages_button, 20, 40, 28, 33)

    def create_config_build_button(self):
        # Create the "Build packages" and "Build image" buttons at the bottom
        button_box = gtk.HBox(False, 6)

        # create button "Build image"
        just_bake_button = HobButton("Build image")
        just_bake_button.set_size_request(205, 49)
        just_bake_button.set_tooltip_text("Build target image")
        just_bake_button.connect("clicked", self.just_bake_button_clicked_cb)
        button_box.pack_end(just_bake_button, expand=False, fill=False)

        label = gtk.Label(" or ")
        button_box.pack_end(label, expand=False, fill=False)

        # create button "Build Packages"
        build_packages_button = HobAltButton("Build packages")
        build_packages_button.connect("clicked", self.build_packages_button_clicked_cb)
        build_packages_button.set_tooltip_text("Build recipes into packages")
        button_box.pack_end(build_packages_button, expand=False, fill=False)

        return button_box

    def stop_button_clicked_cb(self, button):
        self.builder.cancel_parse_sync()

    def machine_combo_changed_cb(self, machine_combo):
        combo_item = machine_combo.get_active_text()
        if not combo_item:
            return

        self.builder.configuration.curr_mach = combo_item
        if self.machine_combo_changed_by_manual:
            self.builder.configuration.clear_selection()
        # reset machine_combo_changed_by_manual
        self.machine_combo_changed_by_manual = True

        # Do reparse recipes
        self.builder.populate_recipe_package_info_async()

    def update_machine_combo(self):
        all_machines = self.builder.parameters.all_machines

        model = self.machine_combo.get_model()
        model.clear()
        for machine in all_machines:
            self.machine_combo.append_text(machine)
        self.machine_combo.set_active(-1)

    def switch_machine_combo(self):
        self.machine_combo_changed_by_manual = False
        model = self.machine_combo.get_model()
        active = 0
        while active < len(model):
            if model[active][0] == self.builder.configuration.curr_mach:
                self.machine_combo.set_active(active)
                return
            active += 1
        self.machine_combo.set_active(-1)

    def update_image_desc(self, selected_image):
        desc = ""
        if selected_image and selected_image in self.builder.recipe_model.pn_path.keys():
            image_path = self.builder.recipe_model.pn_path[selected_image]
            image_iter = self.builder.recipe_model.get_iter(image_path)
            desc = self.builder.recipe_model.get_value(image_iter, self.builder.recipe_model.COL_DESC)

        mark = ("<span %s>%s</span>\n") % (self.span_tag('small'), desc)
        self.image_desc.set_markup(mark)

    def image_combo_changed_idle_cb(self, selected_image, selected_recipes, selected_packages):
        self.builder.update_recipe_model(selected_image, selected_recipes)
        self.builder.update_package_model(selected_packages)
        self.builder.window_sensitive(True)

    def image_combo_changed_cb(self, combo):
        self.builder.window_sensitive(False)
        selected_image = self.image_combo.get_active_text()
        if not selected_image:
            return

        self.builder.customized = False

        selected_recipes = []

        image_path = self.builder.recipe_model.pn_path[selected_image]
        image_iter = self.builder.recipe_model.get_iter(image_path)
        selected_packages = self.builder.recipe_model.get_value(image_iter, self.builder.recipe_model.COL_INSTALL).split()
        self.update_image_desc(selected_image)

        self.builder.recipe_model.reset()
        self.builder.package_model.reset()

        self.show_baseimg_selected()

        glib.idle_add(self.image_combo_changed_idle_cb, selected_image, selected_recipes, selected_packages)

    def _image_combo_connect_signal(self):
        if not self.image_combo_id:
            self.image_combo_id = self.image_combo.connect("changed", self.image_combo_changed_cb)

    def _image_combo_disconnect_signal(self):
        if self.image_combo_id:
            self.image_combo.disconnect(self.image_combo_id)
            self.image_combo_id = None

    def update_image_combo(self, recipe_model, selected_image):
        # Update the image combo according to the images in the recipe_model
        # populate image combo
        filter = {RecipeListModel.COL_TYPE : ['image']}
        image_model = recipe_model.tree_model(filter)
        active = -1
        cnt = 0

        it = image_model.get_iter_first()
        self._image_combo_disconnect_signal()
        model = self.image_combo.get_model()
        model.clear()
        # append and set active
        while it:
            path = image_model.get_path(it)
            it = image_model.iter_next(it)
            image_name = image_model[path][recipe_model.COL_NAME]
            if image_name == self.builder.recipe_model.__dummy_image__:
                continue
            self.image_combo.append_text(image_name)
            if image_name == selected_image:
                active = cnt
            cnt = cnt + 1
        self.image_combo.append_text(self.builder.recipe_model.__dummy_image__)
        if selected_image == self.builder.recipe_model.__dummy_image__:
            active = cnt

        self.image_combo.set_active(-1)
        self.image_combo.set_active(active)

        if active != -1:
            self.show_baseimg_selected()

        self._image_combo_connect_signal()

    def layer_button_clicked_cb(self, button):
        # Create a layer selection dialog
        self.builder.show_layer_selection_dialog()

    def view_recipes_button_clicked_cb(self, button):
        self.builder.show_recipes()

    def view_packages_button_clicked_cb(self, button):
        self.builder.show_packages()

    def just_bake_button_clicked_cb(self, button):
        self.builder.just_bake()

    def build_packages_button_clicked_cb(self, button):
        self.builder.build_packages()

    def template_button_clicked_cb(self, button):
        response, path = self.builder.show_load_template_dialog()
        if not response:
            return
        if path:
            self.builder.load_template(path)

    def my_images_button_clicked_cb(self, button):
        self.builder.show_load_my_images_dialog()

    def settings_button_clicked_cb(self, button):
        # Create an advanced settings dialog
        response, settings_changed = self.builder.show_adv_settings_dialog()
        if not response:
            return
        if settings_changed:
            self.builder.reparse_post_adv_settings()
