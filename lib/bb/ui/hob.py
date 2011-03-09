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
from bb.ui.crumbs.progress import ProgressBar
from bb.ui.crumbs.tasklistmodel import TaskListModel
from bb.ui.crumbs.hobeventhandler import HobHandler
from bb.ui.crumbs.runningbuild import RunningBuildTreeView, RunningBuild
import xmlrpclib
import logging
import Queue

extraCaches = ['bb.cache_extra:HobRecipeInfo']

class MainWindow (gtk.Window):
            
    def __init__(self, taskmodel, handler, curr_mach=None, curr_distro=None):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.model = taskmodel
	self.model.connect("tasklist-populated", self.update_model)
	self.curr_mach = curr_mach
	self.curr_distro = curr_distro
        self.handler = handler
        self.set_border_width(10)
        self.connect("delete-event", gtk.main_quit)
        self.set_title("BitBake Image Creator")
        self.set_default_size(700, 600)

        self.build = RunningBuild()
        self.build.connect("build-succeeded", self.running_build_succeeded_cb)
        self.build.connect("build-failed", self.running_build_failed_cb)

	createview = self.create_build_gui()
        buildview = self.view_build_gui()
	self.nb = gtk.Notebook()
	self.nb.append_page(createview)
	self.nb.append_page(buildview)
	self.nb.set_current_page(0)
	self.nb.set_show_tabs(False)
        self.add(self.nb)
        self.generating = False

    def scroll_tv_cb(self, model, path, it, view):
        view.scroll_to_cell(path)

    def running_build_failed_cb(self, running_build):
        # FIXME: handle this
        return

    def running_build_succeeded_cb(self, running_build):
        label = gtk.Label("Build completed, start another build?")
        dialog = gtk.Dialog("Build complete",
                            self,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_NO, gtk.RESPONSE_NO,
                             gtk.STOCK_YES, gtk.RESPONSE_YES))
        dialog.vbox.pack_start(label)
        label.show()
        response = dialog.run()
        dialog.destroy()
        if not response == gtk.RESPONSE_YES:
            self.model.reset() # NOTE: really?
            self.nb.set_current_page(0)
        return

    def machine_combo_changed_cb(self, combo, handler):
        mach = combo.get_active_text()
	if mach != self.curr_mach:
	    self.curr_mach = mach
            handler.set_machine(mach)

    def update_machines(self, handler, machines):
	active = 0
	for machine in machines:
	    self.machine_combo.append_text(machine)
	    if machine == self.curr_mach:
                self.machine_combo.set_active(active)
	    active = active + 1
	self.machine_combo.connect("changed", self.machine_combo_changed_cb, handler)

    def update_distros(self, handler, distros):
        # FIXME: when we add UI for changing distro this will be used
        return

    def data_generated(self, handler):
        self.generating = False

    def spin_idle_func(self, pbar):
        if self.generating:
            pbar.pulse()
            return True
        else:
            pbar.hide()
            return False

    def busy(self, handler):
        self.generating = True
        pbar = ProgressBar(self)
        pbar.connect("delete-event", gtk.main_quit) # NOTE: questionable...
        pbar.pulse()
        gobject.timeout_add (200,
                             self.spin_idle_func,
                             pbar)

    def update_model(self, model):
	pkgsaz_model = gtk.TreeModelSort(self.model.packages_model())
        pkgsaz_model.set_sort_column_id(self.model.COL_NAME, gtk.SORT_ASCENDING)
        self.pkgsaz_tree.set_model(pkgsaz_model)

        # FIXME: need to implement a custom sort function, as otherwise the column
        # is re-ordered when toggling the inclusion state (COL_INC)
	pkgsgrp_model = gtk.TreeModelSort(self.model.packages_model())
	pkgsgrp_model.set_sort_column_id(self.model.COL_GROUP, gtk.SORT_ASCENDING)
	self.pkgsgrp_tree.set_model(pkgsgrp_model)

        self.contents_tree.set_model(self.model.contents_model())
	self.images_tree.set_model(self.model.images_model())
	self.tasks_tree.set_model(self.model.tasks_model())

    def reset_clicked_cb(self, button):
        label = gtk.Label("Are you sure you want to reset the image contents?")
        dialog = gtk.Dialog("Confirm reset", self,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.vbox.pack_start(label)
        label.show()
        response = dialog.run()
        dialog.destroy()
        if (response == gtk.RESPONSE_ACCEPT):
            self.model.reset()
        return

    def bake_clicked_cb(self, button):
        if not self.model.targets_contains_image():
            label = gtk.Label("No image was selected. Just build the selected packages?")
            dialog = gtk.Dialog("Warning, no image selected",
                                self,
                                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                (gtk.STOCK_NO, gtk.RESPONSE_NO,
                                 gtk.STOCK_YES, gtk.RESPONSE_YES))
            dialog.vbox.pack_start(label)
            label.show()
            response = dialog.run()
            dialog.destroy()
            if not response == gtk.RESPONSE_YES:
                return

        # Note: We could "squash" the targets list to only include things not brought in by an image
	task_list = self.model.get_targets()
	if len(task_list):
	    tasks = " ".join(task_list)
            # TODO: show a confirmation dialog
            print("Including these extra tasks in IMAGE_INSTALL: %s" % tasks)
        else:
            return

        self.nb.set_current_page(1)
        self.handler.run_build(task_list)

        return

    def advanced_expander_cb(self, expander, param):
        return

    def images(self):
        self.images_tree = gtk.TreeView()
	self.images_tree.set_headers_visible(True)
        self.images_tree.set_headers_clickable(False)
        self.images_tree.set_enable_search(True)
        self.images_tree.set_search_column(0)
        self.images_tree.get_selection().set_mode(gtk.SELECTION_NONE)

        col = gtk.TreeViewColumn('Package')
        col1 = gtk.TreeViewColumn('Description')
        col2 = gtk.TreeViewColumn('License')
        col3 = gtk.TreeViewColumn('Include')
	col3.set_resizable(False)

        self.images_tree.append_column(col)
        self.images_tree.append_column(col1)
        self.images_tree.append_column(col2)
        self.images_tree.append_column(col3)

        cell = gtk.CellRendererText()
        cell1 = gtk.CellRendererText()
        cell2 = gtk.CellRendererText()
        cell3 = gtk.CellRendererToggle()
        cell3.set_property('activatable', True)
        cell3.connect("toggled", self.toggle_include_cb, self.images_tree)

        col.pack_start(cell, True)
        col1.pack_start(cell1, True)
        col2.pack_start(cell2, True)
        col3.pack_start(cell3, True)

        col.set_attributes(cell, text=self.model.COL_NAME)
        col1.set_attributes(cell1, text=self.model.COL_DESC)
        col2.set_attributes(cell2, text=self.model.COL_LIC)
        col3.set_attributes(cell3, active=self.model.COL_INC)

        self.images_tree.show()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(self.images_tree)

        return scroll

    def toggle_package(self, path, model):
        # Convert path to path in original model
        opath = model.convert_path_to_child_path(path)
        # current include status
	inc = self.model[opath][self.model.COL_INC]
	if inc:
	    self.model.mark(opath)
            self.model.sweep_up()
	    #self.model.remove_package_full(cpath)
	else:
	    self.model.include_item(opath)
        return

    def remove_package_cb(self, cell, path):
        model = self.model.contents_model()
        label = gtk.Label("Are you sure you want to remove this item?")
        dialog = gtk.Dialog("Confirm removal", self,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.vbox.pack_start(label)
        label.show()
        response = dialog.run()
        dialog.destroy()
        if (response == gtk.RESPONSE_ACCEPT):
            self.toggle_package(path, model)

    def toggle_include_cb(self, cell, path, tv):
        model = tv.get_model()
        self.toggle_package(path, model)

    def toggle_pkg_include_cb(self, cell, path, tv):
        # there's an extra layer of models in the packages case.
        sort_model = tv.get_model()
        cpath = sort_model.convert_path_to_child_path(path)
        self.toggle_package(cpath, sort_model.get_model())
	
    def pkgsaz(self):
        self.pkgsaz_tree = gtk.TreeView()
        self.pkgsaz_tree.set_headers_visible(True)
        self.pkgsaz_tree.set_headers_clickable(True)
        self.pkgsaz_tree.set_enable_search(True)
        self.pkgsaz_tree.set_search_column(0)
        self.pkgsaz_tree.get_selection().set_mode(gtk.SELECTION_NONE)

        col = gtk.TreeViewColumn('Package')
        col1 = gtk.TreeViewColumn('Description')
	col1.set_resizable(True)
        col2 = gtk.TreeViewColumn('License')
	col2.set_resizable(True)
        col3 = gtk.TreeViewColumn('Group')
        col4 = gtk.TreeViewColumn('Include')
	col4.set_resizable(False)

        self.pkgsaz_tree.append_column(col)
        self.pkgsaz_tree.append_column(col1)
        self.pkgsaz_tree.append_column(col2)
        self.pkgsaz_tree.append_column(col3)
        self.pkgsaz_tree.append_column(col4)

        cell = gtk.CellRendererText()
        cell1 = gtk.CellRendererText()
	cell1.set_property('width-chars', 20)
        cell2 = gtk.CellRendererText()
	cell2.set_property('width-chars', 20)
        cell3 = gtk.CellRendererText()
        cell4 = gtk.CellRendererToggle()
        cell4.set_property('activatable', True)
        cell4.connect("toggled", self.toggle_pkg_include_cb, self.pkgsaz_tree)

        col.pack_start(cell, True)
        col1.pack_start(cell1, True)
        col2.pack_start(cell2, True)
        col3.pack_start(cell3, True)
        col4.pack_start(cell4, True)

        col.set_attributes(cell, text=self.model.COL_NAME)
        col1.set_attributes(cell1, text=self.model.COL_DESC)
        col2.set_attributes(cell2, text=self.model.COL_LIC)
        col3.set_attributes(cell3, text=self.model.COL_GROUP)
        col4.set_attributes(cell4, active=self.model.COL_INC)

        self.pkgsaz_tree.show()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(self.pkgsaz_tree)

        return scroll

    def pkgsgrp(self):
        self.pkgsgrp_tree = gtk.TreeView()
        self.pkgsgrp_tree.set_headers_visible(True)
        self.pkgsgrp_tree.set_headers_clickable(False)
        self.pkgsgrp_tree.set_enable_search(True)
        self.pkgsgrp_tree.set_search_column(0)
        self.pkgsgrp_tree.get_selection().set_mode(gtk.SELECTION_NONE)

        col = gtk.TreeViewColumn('Package')
        col1 = gtk.TreeViewColumn('Description')
	col1.set_resizable(True)
        col2 = gtk.TreeViewColumn('License')
	col2.set_resizable(True)
        col3 = gtk.TreeViewColumn('Group')
        col4 = gtk.TreeViewColumn('Include')
	col4.set_resizable(False)

        self.pkgsgrp_tree.append_column(col)
        self.pkgsgrp_tree.append_column(col1)
        self.pkgsgrp_tree.append_column(col2)
        self.pkgsgrp_tree.append_column(col3)
        self.pkgsgrp_tree.append_column(col4)

        cell = gtk.CellRendererText()
        cell1 = gtk.CellRendererText()
	cell1.set_property('width-chars', 20)
        cell2 = gtk.CellRendererText()
	cell2.set_property('width-chars', 20)
        cell3 = gtk.CellRendererText()
        cell4 = gtk.CellRendererToggle()
        cell4.set_property("activatable", True)
        cell4.connect("toggled", self.toggle_pkg_include_cb, self.pkgsgrp_tree)

        col.pack_start(cell, True)
        col1.pack_start(cell1, True)
        col2.pack_start(cell2, True)
        col3.pack_start(cell3, True)
        col4.pack_start(cell4, True)

        col.set_attributes(cell, text=self.model.COL_NAME)
        col1.set_attributes(cell1, text=self.model.COL_DESC)
        col2.set_attributes(cell2, text=self.model.COL_LIC)
        col3.set_attributes(cell3, text=self.model.COL_GROUP)
        col4.set_attributes(cell4, active=self.model.COL_INC)

        self.pkgsgrp_tree.show()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(self.pkgsgrp_tree)

        return scroll

    def tasks(self):
        self.tasks_tree = gtk.TreeView()
        self.tasks_tree.set_headers_visible(True)
        self.tasks_tree.set_headers_clickable(False)
        self.tasks_tree.set_enable_search(True)
        self.tasks_tree.set_search_column(0)
        self.tasks_tree.get_selection().set_mode(gtk.SELECTION_NONE)

        col = gtk.TreeViewColumn('Package')
        col1 = gtk.TreeViewColumn('Description')
        col2 = gtk.TreeViewColumn('Include')
	col2.set_resizable(False)

        self.tasks_tree.append_column(col)
        self.tasks_tree.append_column(col1)
        self.tasks_tree.append_column(col2)

        cell = gtk.CellRendererText()
        cell1 = gtk.CellRendererText()
        cell2 = gtk.CellRendererToggle()
        cell2.set_property('activatable', True)
        cell2.connect("toggled", self.toggle_include_cb, self.tasks_tree)

        col.pack_start(cell, True)
        col1.pack_start(cell1, True)
        col2.pack_start(cell2, True)

        col.set_attributes(cell, text=self.model.COL_NAME)
        col1.set_attributes(cell1, text=self.model.COL_DESC)
        col2.set_attributes(cell2, active=self.model.COL_INC)

        self.tasks_tree.show()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(self.tasks_tree)

        return scroll

    def cancel_build(self, button):
        label = gtk.Label("Do you really want to stop this build?")
        dialog = gtk.Dialog("Cancel build",
                            self,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_NO, gtk.RESPONSE_NO,
                             gtk.STOCK_YES, gtk.RESPONSE_YES))
        dialog.vbox.pack_start(label)
        label.show()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.handler.cancel_build()
        return

    def view_build_gui(self):
        vbox = gtk.VBox(False, 6)
        vbox.show()
        build_tv = RunningBuildTreeView()
        build_tv.show()
        build_tv.set_model(self.build.model)
        self.build.model.connect("row-inserted", self.scroll_tv_cb, build_tv)
        scrolled_view = gtk.ScrolledWindow ()
        scrolled_view.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_view.add(build_tv)
        scrolled_view.show()
        vbox.pack_start(scrolled_view, expand=True, fill=True)
        hbox = gtk.HBox(False, 6)
        hbox.show()
        vbox.pack_start(hbox, expand=False, fill=False)
        cancel = gtk.Button(stock=gtk.STOCK_CANCEL)
        cancel.connect("clicked", self.cancel_build)
        cancel.show()
        hbox.pack_end(cancel, expand=False, fill=False)

        return vbox
    
    def create_build_gui(self):
        vbox = gtk.VBox(False, 6)
        vbox.show()
        hbox = gtk.HBox(False, 6)
        hbox.show()
        vbox.pack_start(hbox, expand=False, fill=False)

        label = gtk.Label("Machine:")
        label.show()
        hbox.pack_start(label, expand=False, fill=False, padding=6)
        self.machine_combo = gtk.combo_box_new_text()
	self.machine_combo.set_active(0)
        self.machine_combo.show()
        self.machine_combo.set_tooltip_text("Selects the architecture of the target board for which you would like to build an image.")
        hbox.pack_start(self.machine_combo, expand=False, fill=False, padding=6)

        ins = gtk.Notebook()
        vbox.pack_start(ins, expand=True, fill=True)
        ins.set_show_tabs(True)
        label = gtk.Label("Images")
        label.show()
        ins.append_page(self.images(), tab_label=label)
        label = gtk.Label("Tasks")
        label.show()
        ins.append_page(self.tasks(), tab_label=label)
        label = gtk.Label("Packages (by Group)")
        label.show()
        ins.append_page(self.pkgsgrp(), tab_label=label)
        label = gtk.Label("Packages (by Name)")
        label.show()
        ins.append_page(self.pkgsaz(), tab_label=label)
        ins.set_current_page(0)
        ins.show_all()

        hbox = gtk.HBox()
        hbox.show()
        vbox.pack_start(hbox, expand=False, fill=False)
        label = gtk.Label("Image contents:")
        label.show()
        hbox.pack_start(label, expand=False, fill=False, padding=6)
        con = self.contents()
        con.show()
        vbox.pack_start(con, expand=True, fill=True)

        #advanced = gtk.Expander(label="Advanced")
        #advanced.connect("notify::expanded", self.advanced_expander_cb)
        #advanced.show()
        #vbox.pack_start(advanced, expand=False, fill=False)

        hbox = gtk.HBox()
        hbox.show()
        vbox.pack_start(hbox, expand=False, fill=False)
        bake = gtk.Button("Bake")
        bake.connect("clicked", self.bake_clicked_cb)
        bake.show()
        hbox.pack_end(bake, expand=False, fill=False, padding=6)
        reset = gtk.Button("Reset")
        reset.connect("clicked", self.reset_clicked_cb)
        reset.show()
        hbox.pack_end(reset, expand=False, fill=False, padding=6)

        return vbox

    def contents(self):
        self.contents_tree = gtk.TreeView()
        self.contents_tree.set_headers_visible(True)
        self.contents_tree.get_selection().set_mode(gtk.SELECTION_NONE)

        # allow searching in the package column
        self.contents_tree.set_search_column(0)

        col = gtk.TreeViewColumn('Package')
	col.set_sort_column_id(0)
        col1 = gtk.TreeViewColumn('Brought in by')
	col1.set_resizable(True)
        col2 = gtk.TreeViewColumn('Remove')
	col2.set_expand(False)

        self.contents_tree.append_column(col)
        self.contents_tree.append_column(col1)
        self.contents_tree.append_column(col2)

        cell = gtk.CellRendererText()
        cell1 = gtk.CellRendererText()
	cell1.set_property('width-chars', 20)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self.remove_package_cb)

        col.pack_start(cell, True)
        col1.pack_start(cell1, True)
        col2.pack_start(cell2, True)

        col.set_attributes(cell, text=self.model.COL_NAME)
        col1.set_attributes(cell1, text=self.model.COL_BINB)
        col2.set_attributes(cell2, active=self.model.COL_INC)

        self.contents_tree.show()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(self.contents_tree)

        return scroll

def main (server, eventHandler):
    gobject.threads_init()
    gtk.gdk.threads_init()

    taskmodel = TaskListModel()
    handler = HobHandler(taskmodel, server)
    mach = server.runCommand(["getVariable", "MACHINE"])
    distro = server.runCommand(["getVariable", "DISTRO"])

    window = MainWindow(taskmodel, handler, mach, distro)
    window.show_all ()
    handler.connect("machines-updated", window.update_machines)
    handler.connect("distros-updated", window.update_distros)
    handler.connect("generating-data", window.busy)
    handler.connect("data-generated", window.data_generated)
    pbar = ProgressBar(window)
    pbar.connect("delete-event", gtk.main_quit)

    try:
        # kick the while thing off
        handler.current_command = "findConfigFilesDistro"
        server.runCommand(["findConfigFiles", "DISTRO"])
    except xmlrpclib.Fault:
        print("XMLRPC Fault getting commandline:\n %s" % x)
        return 1

    # This timeout function regularly probes the event queue to find out if we
    # have any messages waiting for us.
    gobject.timeout_add (100,
                         handler.event_handle_idle_func,
                         eventHandler,
                         window.build,
                         pbar)

    try:
        gtk.main()
    except EnvironmentError as ioerror:
        # ignore interrupted io
        if ioerror.args[0] == 4:
            pass
    finally:
        server.runCommand(["stateStop"])

