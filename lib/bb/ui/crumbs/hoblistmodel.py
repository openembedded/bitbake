#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2011        Intel Corporation
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
from bb.ui.crumbs.hobpages import HobPage

#
# PackageListModel
#
class PackageListModel(gtk.TreeStore):
    """
    This class defines an gtk.TreeStore subclass which will convert the output
    of the bb.event.TargetsTreeGenerated event into a gtk.TreeStore whilst also
    providing convenience functions to access gtk.TreeModel subclasses which
    provide filtered views of the data.
    """
    (COL_NAME, COL_VER, COL_REV, COL_RNM, COL_SEC, COL_SUM, COL_RDEP, COL_RPROV, COL_SIZE, COL_BINB, COL_INC, COL_FADE_INC) = range(12)

    __gsignals__ = {
        "package-selection-changed" : (gobject.SIGNAL_RUN_LAST,
                                gobject.TYPE_NONE,
                                ()),
    }

    __toolchain_required_packages__ = ["task-core-standalone-sdk-target", "task-core-standalone-sdk-target-dbg"]

    def __init__(self):

        self.contents = None
        self.images = None
        self.pkgs_size = 0
        self.pn_path = {}
        self.pkg_path = {}
        self.rprov_pkg = {}
        
        gtk.TreeStore.__init__ (self,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_BOOLEAN,
                                gobject.TYPE_BOOLEAN)


    """
    Find the model path for the item_name
    Returns the path in the model or None
    """
    def find_path_for_item(self, item_name):
        pkg = item_name
        if item_name not in self.pkg_path.keys():
            if item_name not in self.rprov_pkg.keys():
                return None
            pkg = self.rprov_pkg[item_name]
            if pkg not in self.pkg_path.keys():
                return None

        return self.pkg_path[pkg]

    def find_item_for_path(self, item_path):
        return self[item_path][self.COL_NAME]

    """
    Helper function to determine whether an item is an item specified by filter
    """
    def tree_model_filter(self, model, it, filter):
        for key in filter.keys():
            if model.get_value(it, key) not in filter[key]:
                return False

        return True

    """
    Create, if required, and return a filtered gtk.TreeModelSort
    containing only the items specified by filter
    """
    def tree_model(self, filter):
        model = self.filter_new()
        model.set_visible_func(self.tree_model_filter, filter)

        sort = gtk.TreeModelSort(model)
        sort.set_sort_column_id(PackageListModel.COL_NAME, gtk.SORT_ASCENDING)
        sort.set_default_sort_func(None)
        return sort

    def convert_vpath_to_path(self, view_model, view_path):
        # view_model is the model sorted
        # get the path of the model filtered
        filtered_model_path = view_model.convert_path_to_child_path(view_path)
        # get the model filtered
        filtered_model = view_model.get_model()
        # get the path of the original model
        path = filtered_model.convert_path_to_child_path(filtered_model_path)
        return path

    def convert_path_to_vpath(self, view_model, path):
        name = self.find_item_for_path(path)
        it = view_model.get_iter_first()
        while it:
            child_it = view_model.iter_children(it)
            while child_it:
                view_name = view_model.get_value(child_it, self.COL_NAME)
                if view_name == name:
                    view_path = view_model.get_path(child_it)
                    return view_path
                child_it = view_model.iter_next(child_it)
            it = view_model.iter_next(it)
        return None

    """
    The populate() function takes as input the data from a
    bb.event.PackageInfo event and populates the package list.
    """
    def populate(self, pkginfolist):
        self.clear()
        self.pkgs_size = 0
        self.pn_path = {}
        self.pkg_path = {}
        self.rprov_pkg = {}

        for pkginfo in pkginfolist:
            pn = pkginfo['PN']
            pv = pkginfo['PV']
            pr = pkginfo['PR']
            if pn in self.pn_path.keys():
                pniter = self.get_iter(self.pn_path[pn])
            else:
                pniter = self.append(None)
                self.set(pniter, self.COL_NAME, pn + '-' + pv + '-' + pr,
                                 self.COL_INC, False)
                self.pn_path[pn] = self.get_path(pniter)

            pkg = pkginfo['PKG']
            pkgv = pkginfo['PKGV']
            pkgr = pkginfo['PKGR']
            pkgsize = pkginfo['PKGSIZE_%s' % pkg] if 'PKGSIZE_%s' % pkg in pkginfo.keys() else "0"
            pkg_rename = pkginfo['PKG_%s' % pkg] if 'PKG_%s' % pkg in pkginfo.keys() else ""
            section = pkginfo['SECTION_%s' % pkg] if 'SECTION_%s' % pkg in pkginfo.keys() else ""
            summary = pkginfo['SUMMARY_%s' % pkg] if 'SUMMARY_%s' % pkg in pkginfo.keys() else ""
            rdep = pkginfo['RDEPENDS_%s' % pkg] if 'RDEPENDS_%s' % pkg in pkginfo.keys() else ""
            rrec = pkginfo['RRECOMMENDS_%s' % pkg] if 'RRECOMMENDS_%s' % pkg in pkginfo.keys() else ""
            rprov = pkginfo['RPROVIDES_%s' % pkg] if 'RPROVIDES_%s' % pkg in pkginfo.keys() else ""
            for i in rprov.split():
                self.rprov_pkg[i] = pkg

            if 'ALLOW_EMPTY_%s' % pkg in pkginfo.keys():
                allow_empty = pkginfo['ALLOW_EMPTY_%s' % pkg]
            elif 'ALLOW_EMPTY' in pkginfo.keys():
                allow_empty = pkginfo['ALLOW_EMPTY']
            else:
                allow_empty = ""

            if pkgsize == "0" and not allow_empty:
                continue

            # pkgsize is in KB
            size = HobPage._size_to_string(HobPage._string_to_size(pkgsize + ' KB'))

            it = self.append(pniter)
            self.pkg_path[pkg] = self.get_path(it)
            self.set(it, self.COL_NAME, pkg, self.COL_VER, pkgv,
                     self.COL_REV, pkgr, self.COL_RNM, pkg_rename,
                     self.COL_SEC, section, self.COL_SUM, summary,
                     self.COL_RDEP, rdep + ' ' + rrec,
                     self.COL_RPROV, rprov, self.COL_SIZE, size,
                     self.COL_BINB, "", self.COL_INC, False)

    """
    Check whether the item at item_path is included or not
    """
    def path_included(self, item_path):
        return self[item_path][self.COL_INC]

    """
    Update the model, send out the notification.
    """
    def selection_change_notification(self):
        self.emit("package-selection-changed")

    """
    Mark a certain package as selected.
    All its dependencies are marked as selected.
    The recipe provides the package is marked as selected.
    If user explicitly selects a recipe, all its providing packages are selected
    """
    def include_item(self, item_path, binb=""):
        if self.path_included(item_path):
            return

        item_name = self[item_path][self.COL_NAME]
        item_rdep = self[item_path][self.COL_RDEP]

        self[item_path][self.COL_INC] = True

        it = self.get_iter(item_path)

        # If user explicitly selects a recipe, all its providing packages are selected.
        if not self[item_path][self.COL_VER] and binb == "User Selected":
            child_it = self.iter_children(it)
            while child_it:
                child_path = self.get_path(child_it)
                child_included = self.path_included(child_path)
                if not child_included:
                    self.include_item(child_path, binb="User Selected")
                child_it = self.iter_next(child_it)
            return

        # The recipe provides the package is also marked as selected
        parent_it = self.iter_parent(it)
        if parent_it:
            parent_path = self.get_path(parent_it)
            self[parent_path][self.COL_INC] = True

        item_bin = self[item_path][self.COL_BINB].split(', ')
        if binb and not binb in item_bin:
            item_bin.append(binb)
            self[item_path][self.COL_BINB] = ', '.join(item_bin).lstrip(', ')

        if item_rdep:
            # Ensure all of the items deps are included and, where appropriate,
            # add this item to their COL_BINB
            for dep in item_rdep.split(" "):
                if dep.startswith('('):
                    continue
                # If the contents model doesn't already contain dep, add it
                dep_path = self.find_path_for_item(dep)
                if not dep_path:
                    continue
                dep_included = self.path_included(dep_path)

                if dep_included and not dep in item_bin:
                    # don't set the COL_BINB to this item if the target is an
                    # item in our own COL_BINB
                    dep_bin = self[dep_path][self.COL_BINB].split(', ')
                    if not item_name in dep_bin:
                        dep_bin.append(item_name)
                        self[dep_path][self.COL_BINB] = ', '.join(dep_bin).lstrip(', ')
                elif not dep_included:
                    self.include_item(dep_path, binb=item_name)

    """
    Mark a certain package as de-selected.
    All other packages that depends on this package are marked as de-selected.
    If none of the packages provided by the recipe, the recipe should be marked as de-selected.
    If user explicitly de-select a recipe, all its providing packages are de-selected.
    """
    def exclude_item(self, item_path):
        if not self.path_included(item_path):
            return

        self[item_path][self.COL_INC] = False

        item_name = self[item_path][self.COL_NAME]
        item_rdep = self[item_path][self.COL_RDEP]
        it = self.get_iter(item_path)

        # If user explicitly de-select a recipe, all its providing packages are de-selected.
        if not self[item_path][self.COL_VER]:
            child_it = self.iter_children(it)
            while child_it:
                child_path = self.get_path(child_it)
                child_included = self[child_path][self.COL_INC]
                if child_included:
                    self.exclude_item(child_path)
                child_it = self.iter_next(child_it)
            return

        # If none of the packages provided by the recipe, the recipe should be marked as de-selected.
        parent_it = self.iter_parent(it)
        peer_iter = self.iter_children(parent_it)
        enabled = 0
        while peer_iter:
            peer_path = self.get_path(peer_iter)
            if self[peer_path][self.COL_INC]:
                enabled = 1
                break
            peer_iter = self.iter_next(peer_iter)
        if not enabled:
            parent_path = self.get_path(parent_it)
            self[parent_path][self.COL_INC] = False

        # All packages that depends on this package are de-selected.
        if item_rdep:
            for dep in item_rdep.split(" "):
                if dep.startswith('('):
                    continue
                dep_path = self.find_path_for_item(dep)
                if not dep_path:
                    continue
                dep_bin = self[dep_path][self.COL_BINB].split(', ')
                if item_name in dep_bin:
                    dep_bin.remove(item_name)
                    self[dep_path][self.COL_BINB] = ', '.join(dep_bin).lstrip(', ')

        item_bin = self[item_path][self.COL_BINB].split(', ')
        if item_bin:
            for binb in item_bin:
                binb_path = self.find_path_for_item(binb)
                if not binb_path:
                    continue
                self.exclude_item(binb_path)

    """
    Package model may be incomplete, therefore when calling the
    set_selected_packages(), some packages will not be set included.
    Return the un-set packages list.
    """
    def set_selected_packages(self, packagelist):
        left = []
        for pn in packagelist:
            if pn in self.pkg_path.keys():
                path = self.pkg_path[pn]
                self.include_item(item_path=path,
                                  binb="User Selected")
            else:
                left.append(pn)

        self.selection_change_notification()
        return left

    def get_user_selected_packages(self):
        packagelist = []

        it = self.get_iter_first()
        while it:
            child_it = self.iter_children(it)
            while child_it:
                if self.get_value(child_it, self.COL_INC):
                    binb = self.get_value(child_it, self.COL_BINB)
                    if not binb or binb == "User Selected":
                        name = self.get_value(child_it, self.COL_NAME)
                        packagelist.append(name)
                child_it = self.iter_next(child_it)
            it = self.iter_next(it)

        return packagelist

    def get_selected_packages(self):
        packagelist = []

        it = self.get_iter_first()
        while it:
            child_it = self.iter_children(it)
            while child_it:
                if self.get_value(child_it, self.COL_INC):
                    name = self.get_value(child_it, self.COL_NAME)
                    packagelist.append(name)
                child_it = self.iter_next(child_it)
            it = self.iter_next(it)

        return packagelist

    def get_selected_packages_toolchain(self):
        packagelist = []

        it = self.get_iter_first()
        while it:
            if self.get_value(it, self.COL_INC):
                child_it = self.iter_children(it)
                while child_it:
                    name = self.get_value(child_it, self.COL_NAME)
                    inc = self.get_value(child_it, self.COL_INC)
                    if inc or name.endswith("-dev") or name.endswith("-dbg"):
                        packagelist.append(name)
                    child_it = self.iter_next(child_it)
            it = self.iter_next(it)

        return list(set(packagelist + self.__toolchain_required_packages__));
    """
    Return the selected package size, unit is B.
    """
    def get_packages_size(self):
        packages_size = 0
        it = self.get_iter_first()
        while it:
            child_it = self.iter_children(it)
            while child_it:
                if self.get_value(child_it, self.COL_INC):
                    str_size = self.get_value(child_it, self.COL_SIZE)
                    if not str_size:
                        continue

                    packages_size += HobPage._string_to_size(str_size)

                child_it = self.iter_next(child_it)
            it = self.iter_next(it)
        return packages_size

    """
    Empty self.contents by setting the include of each entry to None
    """
    def reset(self):
        self.pkgs_size = 0
        it = self.get_iter_first()
        while it:
            self.set(it, self.COL_INC, False)
            child_it = self.iter_children(it)
            while child_it:
                self.set(child_it,
                         self.COL_INC, False,
                         self.COL_BINB, "")
                child_it = self.iter_next(child_it)
            it = self.iter_next(it)

        self.selection_change_notification()

    """
    Resync the state of included items to a backup column before performing the fadeout visible effect
    """
    def resync_fadeout_column(self, model_first_iter=None):
        it = model_first_iter
        while it:
            active = self.get_value(it, self.COL_INC)
            self.set(it, self.COL_FADE_INC, active)
            if self.iter_has_child(it):
                self.resync_fadeout_column(self.iter_children(it))

            it = self.iter_next(it)

#
# RecipeListModel
#
class RecipeListModel(gtk.ListStore):
    """
    This class defines an gtk.ListStore subclass which will convert the output
    of the bb.event.TargetsTreeGenerated event into a gtk.ListStore whilst also
    providing convenience functions to access gtk.TreeModel subclasses which
    provide filtered views of the data.
    """
    (COL_NAME, COL_DESC, COL_LIC, COL_GROUP, COL_DEPS, COL_BINB, COL_TYPE, COL_INC, COL_IMG, COL_INSTALL, COL_PN, COL_FADE_INC) = range(12)

    __dummy_image__ = "Create your own image"

    __gsignals__ = {
        "recipe-selection-changed" : (gobject.SIGNAL_RUN_LAST,
                                  gobject.TYPE_NONE,
                                 ()),
        }

    """
    """
    def __init__(self):
        gtk.ListStore.__init__ (self,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_BOOLEAN,
                                gobject.TYPE_BOOLEAN,
                                gobject.TYPE_STRING,
                                gobject.TYPE_STRING,
                                gobject.TYPE_BOOLEAN)

    """
    Find the model path for the item_name
    Returns the path in the model or None
    """
    def find_path_for_item(self, item_name):
        if self.non_target_name(item_name) or item_name not in self.pn_path.keys():
            return None
        else:
            return self.pn_path[item_name]

    def find_item_for_path(self, item_path):
        return self[item_path][self.COL_NAME]

    """
    Helper method to determine whether name is a target pn
    """
    def non_target_name(self, name):
        if name and ('-native' in name):
            return True
        return False

    """
    Helper function to determine whether an item is an item specified by filter
    """
    def tree_model_filter(self, model, it, filter):
        name = model.get_value(it, self.COL_NAME)
        if self.non_target_name(name):
            return False

        for key in filter.keys():
            if model.get_value(it, key) not in filter[key]:
                return False

        return True

    def exclude_item_sort_func(self, model, iter1, iter2):
        val1 = model.get_value(iter1, RecipeListModel.COL_FADE_INC)
        val2 = model.get_value(iter2, RecipeListModel.COL_INC)
        return ((val1 == True) and (val2 == False))

    """
    Create, if required, and return a filtered gtk.TreeModelSort
    containing only the items which are items specified by filter
    """
    def tree_model(self, filter, excluded_items_ahead=False):
        model = self.filter_new()
        model.set_visible_func(self.tree_model_filter, filter)

        sort = gtk.TreeModelSort(model)
        if excluded_items_ahead:
            sort.set_default_sort_func(self.exclude_item_sort_func)
        else:
            sort.set_sort_column_id(RecipeListModel.COL_NAME, gtk.SORT_ASCENDING)
            sort.set_default_sort_func(None)
        return sort

    def convert_vpath_to_path(self, view_model, view_path):
        filtered_model_path = view_model.convert_path_to_child_path(view_path)
        filtered_model = view_model.get_model()

        # get the path of the original model
        path = filtered_model.convert_path_to_child_path(filtered_model_path)
        return path

    def convert_path_to_vpath(self, view_model, path):
        it = view_model.get_iter_first()
        while it:
            name = self.find_item_for_path(path)
            view_name = view_model.get_value(it, RecipeListModel.COL_NAME)
            if view_name == name:
                view_path = view_model.get_path(it)
                return view_path
            it = view_model.iter_next(it)
        return None

    """
    The populate() function takes as input the data from a
    bb.event.TargetsTreeGenerated event and populates the RecipeList.
    """
    def populate(self, event_model):
        # First clear the model, in case repopulating
        self.clear()

        # dummy image for prompt
        self.set(self.append(), self.COL_NAME, self.__dummy_image__,
                 self.COL_DESC, "Use the 'View recipes' and 'View packages' " \
                                "options to select what you want to include " \
                                "in your image.",
                 self.COL_LIC, "", self.COL_GROUP, "",
                 self.COL_DEPS, "", self.COL_BINB, "",
                 self.COL_TYPE, "image", self.COL_INC, False,
                 self.COL_IMG, False, self.COL_INSTALL, "", self.COL_PN, self.__dummy_image__)

        for item in event_model["pn"]:
            name = item
            desc = event_model["pn"][item]["description"]
            lic = event_model["pn"][item]["license"]
            group = event_model["pn"][item]["section"]
            inherits = event_model["pn"][item]["inherits"]
            install = []

            depends = event_model["depends"].get(item, []) + event_model["rdepends-pn"].get(item, [])

            if ('task-' in name):
                atype = 'task'
            elif ('image.bbclass' in " ".join(inherits)):
                if name != "hob-image":
                    atype = 'image'
                    install = event_model["rdepends-pkg"].get(item, []) + event_model["rrecs-pkg"].get(item, [])
            elif ('meta-' in name):
                atype = 'toolchain'
            elif (name == 'dummy-image' or name == 'dummy-toolchain'):
                atype = 'dummy'
            else:
                atype = 'recipe'

            self.set(self.append(), self.COL_NAME, item, self.COL_DESC, desc,
                     self.COL_LIC, lic, self.COL_GROUP, group,
                     self.COL_DEPS, " ".join(depends), self.COL_BINB, "",
                     self.COL_TYPE, atype, self.COL_INC, False,
                     self.COL_IMG, False, self.COL_INSTALL, " ".join(install), self.COL_PN, item)

        self.pn_path = {}
        it = self.get_iter_first()
        while it:
            pn = self.get_value(it, self.COL_NAME)
            path = self.get_path(it)
            self.pn_path[pn] = path
            it = self.iter_next(it)

    """
    Update the model, send out the notification.
    """
    def selection_change_notification(self):
        self.emit("recipe-selection-changed")

    def path_included(self, item_path):
        return self[item_path][self.COL_INC]

    """
    Add this item, and any of its dependencies, to the image contents
    """
    def include_item(self, item_path, binb="", image_contents=False):
        if self.path_included(item_path):
            return

        item_name = self[item_path][self.COL_NAME]
        item_deps = self[item_path][self.COL_DEPS]

        self[item_path][self.COL_INC] = True

        item_bin = self[item_path][self.COL_BINB].split(', ')
        if binb and not binb in item_bin:
            item_bin.append(binb)
            self[item_path][self.COL_BINB] = ', '.join(item_bin).lstrip(', ')

        # We want to do some magic with things which are brought in by the
        # base image so tag them as so
        if image_contents:
            self[item_path][self.COL_IMG] = True

        if item_deps:
            # Ensure all of the items deps are included and, where appropriate,
            # add this item to their COL_BINB
            for dep in item_deps.split(" "):
                # If the contents model doesn't already contain dep, add it
                dep_path = self.find_path_for_item(dep)
                if not dep_path:
                    continue
                dep_included = self.path_included(dep_path)

                if dep_included and not dep in item_bin:
                    # don't set the COL_BINB to this item if the target is an
                    # item in our own COL_BINB
                    dep_bin = self[dep_path][self.COL_BINB].split(', ')
                    if not item_name in dep_bin:
                        dep_bin.append(item_name)
                        self[dep_path][self.COL_BINB] = ', '.join(dep_bin).lstrip(', ')
                elif not dep_included:
                    self.include_item(dep_path, binb=item_name, image_contents=image_contents)

    def exclude_item(self, item_path):
        if not self.path_included(item_path):
            return

        self[item_path][self.COL_INC] = False

        item_name = self[item_path][self.COL_NAME]
        item_deps = self[item_path][self.COL_DEPS]
        if item_deps:
            for dep in item_deps.split(" "):
                dep_path = self.find_path_for_item(dep)
                if not dep_path:
                    continue
                dep_bin = self[dep_path][self.COL_BINB].split(', ')
                if item_name in dep_bin:
                    dep_bin.remove(item_name)
                    self[dep_path][self.COL_BINB] = ', '.join(dep_bin).lstrip(', ')

        item_bin = self[item_path][self.COL_BINB].split(', ')
        if item_bin:
            for binb in item_bin:
                binb_path = self.find_path_for_item(binb)
                if not binb_path:
                    continue
                self.exclude_item(binb_path)

    def reset(self):
        it = self.get_iter_first()
        while it:
            self.set(it,
                     self.COL_INC, False,
                     self.COL_BINB, "",
                     self.COL_IMG, False)
            it = self.iter_next(it)

        self.selection_change_notification()

    """
    Returns two lists. One of user selected recipes and the other containing
    all selected recipes
    """
    def get_selected_recipes(self):
        allrecipes = []
        userrecipes = []

        it = self.get_iter_first()
        while it:
            if self.get_value(it, self.COL_INC):
                name = self.get_value(it, self.COL_PN)
                type = self.get_value(it, self.COL_TYPE)
                if type != "image":
                    allrecipes.append(name)
                    sel = "User Selected" in self.get_value(it, self.COL_BINB)
                    if sel:
                        userrecipes.append(name)
            it = self.iter_next(it)

        return list(set(userrecipes)), list(set(allrecipes))

    def set_selected_recipes(self, recipelist):
        for pn in recipelist:
            if pn in self.pn_path.keys():
                path = self.pn_path[pn]
                self.include_item(item_path=path,
                                  binb="User Selected")
        self.selection_change_notification()

    def get_selected_image(self):
        it = self.get_iter_first()
        while it:
            if self.get_value(it, self.COL_INC):
                name = self.get_value(it, self.COL_PN)
                type = self.get_value(it, self.COL_TYPE)
                if type == "image":
                    sel = "User Selected" in self.get_value(it, self.COL_BINB)
                    if sel:
                        return name
            it = self.iter_next(it)
        return None

    def set_selected_image(self, img):
        if not img:
            return
        self.reset()
        path = self.find_path_for_item(img)
        self.include_item(item_path=path,
                          binb="User Selected",
                          image_contents=True)
        self.selection_change_notification()
