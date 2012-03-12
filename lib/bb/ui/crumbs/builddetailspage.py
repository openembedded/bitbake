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
from bb.ui.crumbs.progressbar import HobProgressBar
from bb.ui.crumbs.hobwidget import hic, HobNotebook
from bb.ui.crumbs.runningbuild import RunningBuildTreeView
from bb.ui.crumbs.runningbuild import BuildConfigurationTreeView
from bb.ui.crumbs.runningbuild import BuildFailureTreeView
from bb.ui.crumbs.hobpages import HobPage

#
# BuildDetailsPage
#

class BuildDetailsPage (HobPage):

    def __init__(self, builder):
        super(BuildDetailsPage, self).__init__(builder, "Building ...")

        self.num_of_issues = 0

        # create visual elements
        self.create_visual_elements()

    def create_visual_elements(self):
        # create visual elements
        self.vbox = gtk.VBox(False, 12)

        self.progress_box = gtk.HBox(False, 6)
        self.progress_bar = HobProgressBar()
        self.progress_box.pack_start(self.progress_bar, expand=True, fill=True)
        self.stop_button = gtk.LinkButton("Stop the build process", "Stop")
        self.stop_button.connect("clicked", self.stop_button_clicked_cb)
        self.progress_box.pack_end(self.stop_button, expand=False, fill=False)

        self.notebook = HobNotebook()
        self.config_tv = BuildConfigurationTreeView()
        self.config_model = self.builder.handler.build.model.config_model()
        self.config_tv.set_model(self.config_model)
        self.scrolled_view_config = gtk.ScrolledWindow ()
        self.scrolled_view_config.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled_view_config.add(self.config_tv)
        self.notebook.append_page(self.scrolled_view_config, gtk.Label("Build Configuration"))

        self.failure_tv = BuildFailureTreeView()
        self.failure_model = self.builder.handler.build.model.failure_model()
        self.failure_tv.set_model(self.failure_model)
        self.scrolled_view_failure = gtk.ScrolledWindow ()
        self.scrolled_view_failure.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled_view_failure.add(self.failure_tv)
        self.notebook.append_page(self.scrolled_view_failure, gtk.Label("Issues"))

        self.build_tv = RunningBuildTreeView(readonly=True)
        self.build_tv.set_model(self.builder.handler.build.model)
        self.scrolled_view_build = gtk.ScrolledWindow ()
        self.scrolled_view_build.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled_view_build.add(self.build_tv)
        self.notebook.append_page(self.scrolled_view_build, gtk.Label("Log"))

        self.button_box = gtk.HBox(False, 6)
        self.back_button = gtk.LinkButton("Go back to Image Configuration screen", "<< Back to image configuration")
        self.back_button.connect("clicked", self.back_button_clicked_cb)
        self.button_box.pack_start(self.back_button, expand=False, fill=False)

    def show_issues(self):
        self.num_of_issues += 1
        self.notebook.show_indicator_icon("Issues", self.num_of_issues)

    def reset_issues(self):
        self.num_of_issues = 0
        self.notebook.hide_indicator_icon("Issues")

    def _remove_all_widget(self):
        children = self.vbox.get_children() or []
        for child in children:
            self.vbox.remove(child)
        children = self.box_group_area.get_children() or []
        for child in children:
            self.box_group_area.remove(child)
        children = self.get_children() or []
        for child in children:
            self.remove(child)

    def show_page(self, step):
        self._remove_all_widget()
        if step == self.builder.PACKAGE_GENERATING or step == self.builder.FAST_IMAGE_GENERATING:
            self.title = "Building packages ..."
        else:
            self.title = "Building image ..."
        self.build_details_top = self.add_onto_top_bar(None)
        self.pack_start(self.build_details_top, expand=False, fill=False)
        self.pack_start(self.group_align, expand=True, fill=True)

        self.box_group_area.pack_start(self.vbox, expand=True, fill=True)

        self.progress_bar.reset()
        self.vbox.pack_start(self.progress_box, expand=False, fill=False)

        self.vbox.pack_start(self.notebook, expand=True, fill=True)

        self.box_group_area.pack_end(self.button_box, expand=False, fill=False)
        self.show_all()
        self.back_button.hide()

    def update_progress_bar(self, title, fraction, status=True):
        self.progress_bar.update(fraction)
        self.progress_bar.set_title(title)
        self.progress_bar.set_rcstyle(status)

    def back_button_clicked_cb(self, button):
        self.builder.show_configuration()

    def show_back_button(self):
        self.back_button.show()

    def stop_button_clicked_cb(self, button):
        self.builder.stop_build()

    def hide_stop_button(self):
        self.stop_button.hide()
