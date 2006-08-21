#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'TaskData' implementation

Task data collection and handling

Copyright (C) 2006  Richard Purdie

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License version 2 as published by the Free 
Software Foundation

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
"""

from bb import data, fetch, event, mkdirhier, utils
import bb, os

class TaskData:
    """
    BitBake Task Data implementation
    """
    def __init__(self):
        self.build_names_index = []
        self.run_names_index = []
        self.fn_index = []

        self.build_targets = {}
        self.run_targets = {}

        self.tasks_fnid = []
        self.tasks_name = []
        self.tasks_tdepends = []

        self.depids = {}
        self.rdepids = {}

        self.consider_msgs_cache = []

        self.failed_deps = []
        self.failed_rdeps = []
        self.failed_fnids = []


    def matches_in_list(self, data, substring):
        """
        Return a list of the positions of substring in list data
        """
        matches = []
        start = 0
        while 1:
            try:
                start = data.index(substring, start)
            except ValueError:
                return matches
            matches.append(start)
            start = start + 1

    def both_contain(self, list1, list2):
        """
        Return the items present in both list1 and list2
        """
        matches = []
        for data in list1:
            if data in list2:
                return data
        return None


    def getbuild_id(self, name):
        """
        Return an ID number for the build target name.
        If it doesn't exist, create one.
        """
        if not name in self.build_names_index:
            self.build_names_index.append(name)

        return self.build_names_index.index(name)

    def getrun_id(self, name):
        """
        Return an ID number for the run target name. 
        If it doesn't exist, create one.
        """
        if not name in self.run_names_index:
            self.run_names_index.append(name)

        return self.run_names_index.index(name)

    def getfn_id(self, name):
        """
        Return an ID number for the filename. 
        If it doesn't exist, create one.
        """
        if not name in self.fn_index:
            self.fn_index.append(name)

        return self.fn_index.index(name)

    def gettask_id(self, fn, task):
        """
        Return an ID number for the task matching fn and task.
        If it doesn't exist, create one.
        """
        fnid = self.getfn_id(fn)

        fnids = self.matches_in_list(self.tasks_fnid, fnid)
        names = self.matches_in_list(self.tasks_name, task)

        listid = self.both_contain(fnids, names)

        if listid is not None:
            return listid

        self.tasks_name.append(task)
        self.tasks_fnid.append(fnid)
        self.tasks_tdepends.append([])

        return len(self.tasks_name)-1

    def add_tasks(self, fn, dataCache):
        """
        Add tasks for a given fn to the database
        """

        task_graph = dataCache.task_queues[fn]
        task_deps = dataCache.task_deps[fn]

        fnid = self.getfn_id(fn)

        if fnid in self.failed_fnids:
            bb.fatal("Trying to re-add a failed file? Something is broken...")

        # Check if we've already seen this fn
        if fnid in self.tasks_fnid:
            return

        # Work out task dependencies
        for task in task_graph.allnodes():
            parentids = []
            for dep in task_graph.getparents(task):
                parentid = self.gettask_id(fn, dep)
                parentids.append(parentid)
            taskid = self.gettask_id(fn, task)
            self.tasks_tdepends[taskid].extend(parentids)

        # Work out build dependencies
        if not fnid in self.depids:
            dependids = []
            for depend in dataCache.deps[fn]:
                bb.msg.debug(2, bb.msg.domain.TaskData, "Added dependency %s for %s" % (depend, fn))
                dependids.append(self.getbuild_id(depend))
            self.depids[fnid] = dependids

        # Work out runtime dependencies
        if not fnid in self.rdepids:
            rdependids = []
            rdepends = dataCache.rundeps[fn]
            rrecs = dataCache.runrecs[fn]
            for package in rdepends:
                for rdepend in rdepends[package]:
                    bb.msg.debug(2, bb.msg.domain.TaskData, "Added runtime dependency %s for %s" % (rdepend, fn))
                    rdependids.append(self.getrun_id(rdepend))
            for package in rrecs:
                for rdepend in rrecs[package]:
                    bb.msg.debug(2, bb.msg.domain.TaskData, "Added runtime recommendation %s for %s" % (rdepend, fn))
                    rdependids.append(self.getrun_id(rdepend))
            self.rdepids[fnid] = rdependids

    def have_build_target(self, target):
        """
        Have we a build target matching this name?
        """
        targetid = self.getbuild_id(target)

        if targetid in self.build_targets:
            return True
        return False

    def have_runtime_target(self, target):
        """
        Have we a runtime target matching this name?
        """
        targetid = self.getrun_id(target)

        if targetid in self.run_targets:
            return True
        return False

    def add_build_target(self, fn, item):
        """
        Add a build target.
        If already present, append the provider fn to the list
        """
        targetid = self.getbuild_id(item)
        fnid = self.getfn_id(fn)

        if targetid in self.build_targets:
            if fnid in self.build_targets[targetid]:
                return
            self.build_targets[targetid].append(fnid)
            return
        self.build_targets[targetid] = [fnid]

    def add_runtime_target(self, fn, item):
        """
        Add a runtime target.
        If already present, append the provider fn to the list
        """
        targetid = self.getrun_id(item)
        fnid = self.getfn_id(fn)

        if targetid in self.run_targets:
            if fnid in self.run_targets[targetid]:
                return
            self.run_targets[targetid].append(fnid)
            return
        self.run_targets[targetid] = [fnid]

    def get_unresolved_build_targets(self, dataCache):
        """
        Return a list of build targets who's providers 
        are unknown.
        """
        unresolved = []
        for target in self.build_names_index:
            if target in dataCache.ignored_dependencies:
                continue
            if self.build_names_index.index(target) in self.failed_deps:
                continue
            if not self.have_build_target(target):
                unresolved.append(target)
        return unresolved

    def get_unresolved_run_targets(self, dataCache):
        """
        Return a list of runtime targets who's providers 
        are unknown.
        """
        unresolved = []
        for target in self.run_names_index:
            if target in dataCache.ignored_dependencies:
                continue
            if self.run_names_index.index(target) in self.failed_rdeps:
                continue
            if not self.have_runtime_target(target):
                unresolved.append(target)
        return unresolved

    def get_provider(self, item):
        """
        Return a list of providers of item
        """
        targetid = self.getbuild_id(item)
   
        return self.build_targets[targetid]

    def get_dependees(self, itemid):
        """
        Return a list of targets which depend on item
        """
        dependees = []
        for fnid in self.depids:
            if itemid in self.depids[fnid]:
                dependees.append(fnid)
        return dependees

    def get_dependees_str(self, item):
        """
        Return a list of targets which depend on item as a user readable string
        """
        itemid = self.getbuild_id(item)
        dependees = []
        for fnid in self.depids:
            if itemid in self.depids[fnid]:
                dependees.append(self.fn_index[fnid])
        return dependees

    def get_rdependees(self, itemid):
        """
        Return a list of targets which depend on runtime item
        """
        dependees = []
        for fnid in self.rdepids:
            if itemid in self.rdepids[fnid]:
                dependees.append(fnid)
        return dependees

    def get_rdependees_str(self, item):
        """
        Return a list of targets which depend on runtime item as a user readable string
        """
        itemid = self.getrun_id(item)
        dependees = []
        for fnid in self.rdepids:
            if itemid in self.rdepids[fnid]:
                dependees.append(self.fn_index[fnid])
        return dependees

    def add_provider(self, cfgData, dataCache, item):
        """
        Add the providers of item to the task data
        """

        if item in dataCache.ignored_dependencies:
            return True

        if not item in dataCache.providers:
            bb.msg.error(bb.msg.domain.Provider, "No providers of build target %s (for %s)" % (item, self.get_dependees_str(item)))
            bb.event.fire(bb.event.NoProvider(item, cfgData))
            raise bb.providers.NoProvider(item)

        if self.have_build_target(item):
            return True

        all_p = dataCache.providers[item]

        eligible = bb.providers.filterProviders(all_p, item, cfgData, dataCache)

        for p in eligible:
            fnid = self.getfn_id(p)
            if fnid in self.failed_fnids:
                eligible.remove(p)

        if not eligible:
            bb.msg.error(bb.msg.domain.Provider, "No providers of build target %s after filtering (for %s)" % (item, self.get_dependees_str(item)))
            bb.event.fire(bb.event.NoProvider(item, cfgData))
            raise bb.providers.NoProvider(item)

        prefervar = bb.data.getVar('PREFERRED_PROVIDER_%s' % item, cfgData, 1)
        if prefervar:
            dataCache.preferred[item] = prefervar

        discriminated = False
        if item in dataCache.preferred:
            for p in eligible:
                pn = dataCache.pkg_fn[p]
                if dataCache.preferred[item] == pn:
                    bb.msg.note(2, bb.msg.domain.Provider, "selecting %s to satisfy %s due to PREFERRED_PROVIDERS" % (pn, item))
                    eligible.remove(p)
                    eligible = [p] + eligible
                    discriminated = True
                    break

        if len(eligible) > 1 and discriminated == False:
            if item not in self.consider_msgs_cache:
                providers_list = []
                for fn in eligible:
                    providers_list.append(dataCache.pkg_fn[fn])
                bb.msg.note(1, bb.msg.domain.Provider, "multiple providers are available (%s);" % ", ".join(providers_list))
                bb.msg.note(1, bb.msg.domain.Provider, "consider defining PREFERRED_PROVIDER_%s" % item)
                bb.event.fire(bb.event.MultipleProviders(item,providers_list,cfgData))
            self.consider_msgs_cache.append(item)

        for fn in eligible:
            fnid = self.getfn_id(fn)
            if fnid in self.failed_fnids:
                continue
            bb.msg.debug(2, bb.msg.domain.Provider, "adding %s to satisfy %s" % (fn, item))
            self.add_tasks(fn, dataCache)
            self.add_build_target(fn, item)

            item = dataCache.pkg_fn[fn]

        return True

    def add_rprovider(self, cfgData, dataCache, item):
        """
        Add the runtime providers of item to the task data
        (takes item names from RDEPENDS/PACKAGES namespace)
        """

        if item in dataCache.ignored_dependencies:
            return True

        if self.have_runtime_target(item):
            return True

        all_p = bb.providers.getRuntimeProviders(dataCache, item)

        if not all_p:
            bb.msg.error(bb.msg.domain.Provider, "No providers of runtime build target %s (for %s)" % (item, self.get_rdependees_str(item)))
            bb.event.fire(bb.event.NoProvider(item, cfgData, runtime=True))
            raise bb.providers.NoRProvider(item)

        eligible = bb.providers.filterProviders(all_p, item, cfgData, dataCache)

        for p in eligible:
            fnid = self.getfn_id(p)
            if fnid in self.failed_fnids:
                eligible.remove(p)

        if not eligible:
            bb.msg.error(bb.msg.domain.Provider, "No providers of runtime build target %s after filtering (for %s)" % (item, self.get_rdependees_str(item)))
            bb.event.fire(bb.event.NoProvider(item, cfgData, runtime=True))
            raise bb.providers.NoRProvider(item)

        # Should use dataCache.preferred here?
        preferred = []
        for p in eligible:
            pn = dataCache.pkg_fn[p]
            provides = dataCache.pn_provides[pn]
            for provide in provides:
                prefervar = bb.data.getVar('PREFERRED_PROVIDER_%s' % provide, cfgData, 1)
                if prefervar == pn:
                    bb.msg.note(2, bb.msg.domain.Provider, "selecting %s to satisfy runtime %s due to PREFERRED_PROVIDERS" % (pn, item))
                    eligible.remove(p)
                    eligible = [p] + eligible
                    preferred.append(p)

        if len(eligible) > 1 and len(preferred) == 0:
            if item not in self.consider_msgs_cache:
                providers_list = []
                for fn in eligible:
                    providers_list.append(dataCache.pkg_fn[fn])
                bb.msg.note(2, bb.msg.domain.Provider, "multiple providers are available (%s);" % ", ".join(providers_list))
                bb.msg.note(2, bb.msg.domain.Provider, "consider defining a PREFERRED_PROVIDER to match runtime %s" % item)
                bb.event.fire(bb.event.MultipleProviders(item,providers_list, cfgData, runtime=True))
            self.consider_msgs_cache.append(item)

        if len(preferred) > 1:
            if item not in self.consider_msgs_cache:
                providers_list = []
                for fn in preferred:
                    providers_list.append(dataCache.pkg_fn[fn])
                bb.msg.note(2, bb.msg.domain.Provider, "multiple preferred providers are available (%s);" % ", ".join(providers_list))
                bb.msg.note(2, bb.msg.domain.Provider, "consider defining only one PREFERRED_PROVIDER to match runtime %s" % item)
                bb.event.fire(bb.event.MultipleProviders(item,providers_list, cfgData, runtime=True))
            self.consider_msgs_cache.append(item)

        # run through the list until we find one that we can build
        for fn in eligible:
            fnid = self.getfn_id(fn)
            if fnid in self.failed_fnids:
                continue
            bb.msg.debug(2, bb.msg.domain.Provider, "adding %s to satisfy runtime %s" % (fn, item))
            self.add_tasks(fn, dataCache)
            self.add_runtime_target(fn, item)

        return True

    def fail_fnid(self, fnid):
        """
        Mark a file as failed (unbuildable)
        Remove any references from build and runtime provider lists
        """
        if fnid in self.failed_fnids:
            return
        bb.msg.note(1, bb.msg.domain.Provider, "Removing failed file %s" % self.fn_index[fnid])
        self.failed_fnids.append(fnid)
        for target in self.build_targets:
            if fnid in self.build_targets[target]:
                self.build_targets[target].remove(fnid)
                if len(self.build_targets[target]) == 0:
                    self.remove_buildtarget(target)
        for target in self.run_targets:
            if fnid in self.run_targets[target]:
                self.run_targets[target].remove(fnid)
                if len(self.run_targets[target]) == 0:
                    self.remove_runtarget(target)

    def remove_buildtarget(self, targetid):
        """
        Mark a build target as failed (unbuildable)
        Trigger removal of any files that have this as a dependency
        """
        bb.msg.note(1, bb.msg.domain.Provider, "Removing failed build target %s" % self.build_names_index[targetid])
        self.failed_deps.append(targetid)
        dependees = self.get_dependees(targetid)
        for fnid in dependees:
            self.fail_fnid(fnid)

    def remove_runtarget(self, targetid):
        """
        Mark a run target as failed (unbuildable)
        Trigger removal of any files that have this as a dependency
        """
        bb.msg.note(1, bb.msg.domain.Provider, "Removing failed runtime build target %s" % self.run_names_index[targetid])
        self.failed_rdeps.append(targetid)
        dependees = self.get_rdependees(targetid)
        for fnid in dependees:
            self.fail_fnid(fnid)

    def add_unresolved(self, cfgData, dataCache):
        """
        Resolve all unresolved build and runtime targets
        """
        bb.msg.note(1, bb.msg.domain.TaskData, "Resolving missing task queue dependencies")
        while 1:
            added = 0
            for target in self.get_unresolved_build_targets(dataCache):
                try:
                    self.add_provider(cfgData, dataCache, target)
                    added = added + 1
                except bb.providers.NoProvider:
                    # FIXME - should look at configuration.abort here and raise if set
                    self.remove_buildtarget(self.getbuild_id(target))
            for target in self.get_unresolved_run_targets(dataCache):
                try:
                    self.add_rprovider(cfgData, dataCache, target)
                    added = added + 1
                except bb.providers.NoRProvider:
                    # FIXME - should look at configuration.abort here and raise if set
                    self.remove_runtarget(self.getrun_id(target))
            bb.msg.debug(1, bb.msg.domain.TaskData, "Resolved " + str(added) + " extra dependecies")
            if added == 0:
                break
            


    def dump_data(self):
        """
        Dump some debug information on the internal data structures
        """
        bb.msg.debug(3, bb.msg.domain.TaskData, "build_names:")
        bb.msg.debug(3, bb.msg.domain.TaskData, self.build_names_index)
        bb.msg.debug(3, bb.msg.domain.TaskData, "run_names:")
        bb.msg.debug(3, bb.msg.domain.TaskData, self.run_names_index)
        bb.msg.debug(3, bb.msg.domain.TaskData, "build_targets:")
        for target in self.build_targets.keys():
            bb.msg.debug(3, bb.msg.domain.TaskData, " %s: %s" % (self.build_names_index[target], self.build_targets[target]))
        bb.msg.debug(3, bb.msg.domain.TaskData, "run_targets:")
        for target in self.run_targets.keys():
            bb.msg.debug(3, bb.msg.domain.TaskData, " %s: %s" % (self.run_names_index[target], self.run_targets[target]))
        bb.msg.debug(3, bb.msg.domain.TaskData, "tasks:")
        for task in range(len(self.tasks_name)):
            bb.msg.debug(3, bb.msg.domain.TaskData, " (%s)%s - %s: %s" % (
                task, 
                self.fn_index[self.tasks_fnid[task]], 
                self.tasks_name[task], 
                self.tasks_tdepends[task]))


