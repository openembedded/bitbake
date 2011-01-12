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

import gtk
import gobject

class TaskListModel(gtk.ListStore):
    """
    This class defines an gtk.ListStore subclass which will convert the output
    of the bb.event.TargetsTreeGenerated event into a gtk.ListStore whilst also
    providing convenience functions to access gtk.TreeModel subclasses which
    provide filtered views of the data.
    """
    (COL_NAME, COL_DESC, COL_LIC, COL_GROUP, COL_DEPS, COL_BINB, COL_TYPE, COL_INC) = range(8)

    __gsignals__ = {
        "tasklist-populated" : (gobject.SIGNAL_RUN_LAST,
                                gobject.TYPE_NONE,
                                ())
        }

    """
    """
    def __init__(self):
        self.contents = None
        self.tasks = None
        self.packages = None
        self.images = None
        
        gtk.ListStore.__init__ (self,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_BOOLEAN)

    """
    Create, if required, and return a filtered gtk.TreeModel
    containing only the items which are to be included in the
    image
    """
    def contents_model(self):
        if not self.contents:
            self.contents = self.filter_new()
            self.contents.set_visible_column(self.COL_INC)
        return self.contents
    
    """
    Helper function to determine whether an item is a task
    """
    def task_model_filter(self, model, it):
        if model.get_value(it, self.COL_TYPE) == 'task':
            return True
        else:
            return False

    """
    Create, if required, and return a filtered gtk.TreeModel
    containing only the items which are tasks
    """
    def tasks_model(self):
        if not self.tasks:
            self.tasks = self.filter_new()
            self.tasks.set_visible_func(self.task_model_filter)
        return self.tasks

    """
    Helper function to determine whether an item is an image
    """
    def image_model_filter(self, model, it):
        if model.get_value(it, self.COL_TYPE) == 'image':
            return True
        else:
            return False

    """
    Create, if required, and return a filtered gtk.TreeModel
    containing only the items which are images
    """
    def images_model(self):
        if not self.images:
            self.images = self.filter_new()
            self.images.set_visible_func(self.image_model_filter)
        return self.images

    """
    Helper function to determine whether an item is a package
    """
    def package_model_filter(self, model, it):
        if model.get_value(it, self.COL_TYPE) == 'package':
            return True
        else:
            return False

    """
    Create, if required, and return a filtered gtk.TreeModel
    containing only the items which are packages
    """
    def packages_model(self):
        if not self.packages:
            self.packages = self.filter_new()
            self.packages.set_visible_func(self.package_model_filter)
        return self.packages

    """
    The populate() function takes as input the data from a
    bb.event.TargetsTreeGenerated event and populates the TaskList.
    Once the population is done it emits gsignal tasklist-populated
    to notify any listeners that the model is ready
    """
    def populate(self, event_model):
        for item in event_model["pn"]:
            atype = 'package'
            name = item
            summary = event_model["pn"][item]["summary"]
            license = event_model["pn"][item]["license"]
            group = event_model["pn"][item]["section"]
            
	    depends = event_model["depends"].get(item, "")
            rdepends = event_model["rdepends-pn"].get(item, "")
            depends = depends + rdepends
            self.squish(depends)
            deps = " ".join(depends)
            
            if name.count('task-') > 0:
                atype = 'task'
            elif name.count('-image-') > 0:
                atype = 'image'

            self.set(self.append(), self.COL_NAME, name, self.COL_DESC, summary,
	             self.COL_LIC, license, self.COL_GROUP, group,
		     self.COL_DEPS, deps, self.COL_BINB, "",
		     self.COL_TYPE, atype, self.COL_INC, False)
	
	self.emit("tasklist-populated")

    """
    squish lst so that it doesn't contain any duplicates
    """
    def squish(self, lst):
        seen = {}
        for l in lst:
            seen[l] = 1
        return seen.keys()

    """
    Mark the item at path as not included
    NOTE:
    path should be a gtk.TreeModelPath into self (not a filtered model)
    """
    def remove_item_path(self, path):
        self[path][self.COL_BINB] = ""
        self[path][self.COL_INC] = False

    """
    """
    def mark(self, path):
        name = self[path][self.COL_NAME]
        it = self.get_iter_first()
        removals = []
        #print("Removing %s" % name)

        self.remove_item_path(path)

        # Remove all dependent packages, update binb
        while it:
            path = self.get_path(it)
            # FIXME: need to ensure partial name matching doesn't happen, regexp?
            if self[path][self.COL_INC] and self[path][self.COL_DEPS].count(name):
                #print("%s depended on %s, marking for removal" % (self[path][self.COL_NAME], name))
                # found a dependency, remove it
                self.mark(path)
            if self[path][self.COL_INC] and self[path][self.COL_BINB].count(name):
                binb = self.find_alt_dependency(self[path][self.COL_NAME])
                #print("%s was brought in by %s, binb set to %s" % (self[path][self.COL_NAME], name, binb))
                self[path][self.COL_BINB] = binb
            it = self.iter_next(it)

    """
    """
    def sweep_up(self):
        removals = []
        it = self.get_iter_first()

	while it:
	    path = self.get_path(it)
	    binb = self[path][self.COL_BINB]
	    if binb == "" or binb is None:
                #print("Sweeping up %s" % self[path][self.COL_NAME])
                if not path in removals:
                    removals.extend(path)
            it = self.iter_next(it)

	while removals:
	    path = removals.pop()
	    self.mark(path)

    """
    Remove an item from the contents
    """
    def remove_item(self, path):
        self.mark(path)
        self.sweep_up()

    """
    Find the name of an item in the image contents which depends on the item
    at contents_path returns either an item name (str) or None
    NOTE:
    contents_path must be a path in the self.contents gtk.TreeModel
    """
    def find_alt_dependency(self, name):
        it = self.get_iter_first()
        while it:
            # iterate all items in the model
            path = self.get_path(it)
            deps = self[path][self.COL_DEPS]
            itname = self[path][self.COL_NAME]
            inc = self[path][self.COL_INC]
            if itname != name and inc and deps.count(name) > 0:
		# if this item depends on the item, return this items name
		#print("%s depends on %s" % (itname, name))
	        return itname
	    it = self.iter_next(it)
	return ""

    """
    Convert a path in self to a path in the filtered contents model
    """
    def contents_path_for_path(self, path):
        return self.contents.convert_child_path_to_path(path)

    """
    Check the self.contents gtk.TreeModel for an item
    where COL_NAME matches item_name
    Returns True if a match is found, False otherwise
    """
    def contents_includes_name(self, item_name):
        it = self.contents.get_iter_first()
        while it:
            path = self.contents.get_path(it)
            if self.contents[path][self.COL_NAME] == item_name:
                return True
            it = self.contents.iter_next(it)
        return False

    """
    Add this item, and any of its dependencies, to the image contents
    """
    def include_item(self, item_path, binb=""):
        name = self[item_path][self.COL_NAME]
        deps = self[item_path][self.COL_DEPS]
        cur_inc = self[item_path][self.COL_INC]
        #print("Adding %s for %s dependency" % (name, binb))
        if not cur_inc:
            self[item_path][self.COL_INC] = True
            self[item_path][self.COL_BINB] = binb
        if deps:
            #print("Dependencies of %s are %s" % (name, deps))
            # add all of the deps and set their binb to this item
            for dep in deps.split(" "):
                # FIXME: this skipping virtuals can't be right? Unless we choose only to show target
                # packages? In which case we should handle this server side...
                # If the contents model doesn't already contain dep, add it
                if not dep.startswith("virtual") and not self.contents_includes_name(dep):
                    path = self.find_path_for_item(dep)
                    if path:
                        self.include_item(path, name)
                    else:
                        pass

    """
    Find the model path for the item_name
    Returns the path in the model or None
    """
    def find_path_for_item(self, item_name):
        it = self.get_iter_first()
        path = None
        while it:
            path = self.get_path(it)
            if (self[path][self.COL_NAME] == item_name):
                return path
            else:
                it = self.iter_next(it)
        return None

    """
    Empty self.contents by setting the include of each entry to None
    """
    def reset(self):
        it = self.contents.get_iter_first()
        while it:
            path = self.contents.get_path(it)
            opath = self.contents.convert_path_to_child_path(path)
            self[opath][self.COL_INC] = False
            self[opath][self.COL_BINB] = ""
            # As we've just removed the first item...
            it = self.contents.get_iter_first()

    """
    Returns True if one of the selected tasks is an image, False otherwise
    """
    def targets_contains_image(self):
        it = self.images.get_iter_first()
        while it:
            path = self.images.get_path(it)
            inc = self.images[path][self.COL_INC]
            if inc:
                return True
            it = self.images.iter_next(it)
        return False

    """
    Return a list of all selected items which are not -native or -cross
    """
    def get_targets(self):
        tasks = []

        it = self.contents.get_iter_first()
        while it:
            path = self.contents.get_path(it)
            name = self.contents[path][self.COL_NAME]
            stype = self.contents[path][self.COL_TYPE]
            if not name.count('-native') and not name.count('-cross'):
                tasks.append(name)
            it = self.contents.iter_next(it)
        return tasks
