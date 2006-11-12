#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'RunQueue' implementation

Handles preparation and execution of a queue of tasks

Copyright (C) 2006  Richard Purdie

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License version 2 as published by the Free 
Software Foundation

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
"""

from bb import msg, data, fetch, event, mkdirhier, utils
from sets import Set 
import bb, os, sys

class TaskFailure(Exception):
    """Exception raised when a task in a runqueue fails"""

    def __init__(self, fnid, fn, taskname):
        self.args = fnid, fn, taskname

class RunQueue:
    """
    BitBake Run Queue implementation
    """
    def __init__(self):
        self.reset_runqueue()

    def reset_runqueue(self):
        self.runq_fnid = []
        self.runq_task = []
        self.runq_depends = []
        self.runq_revdeps = []
        self.runq_weight = []
        self.prio_map = []

    def get_user_idstring(self, task, taskData):
        fn = taskData.fn_index[self.runq_fnid[task]]
        taskname = self.runq_task[task]
        return "%s, %s" % (fn, taskname)

    def prepare_runqueue(self, cfgData, dataCache, taskData, targets):
        """
        Turn a set of taskData into a RunQueue and compute data needed 
        to optimise the execution order.
        targets is list of paired values - a provider name and the task to run
        """

        depends = []
        runq_weight1 = []
        runq_build = []
        runq_done = []

        bb.msg.note(1, bb.msg.domain.RunQueue, "Preparing Runqueue")

        for task in range(len(taskData.tasks_name)):
            fnid = taskData.tasks_fnid[task]
            fn = taskData.fn_index[fnid]
            task_deps = dataCache.task_deps[fn]

            if fnid not in taskData.failed_fnids:

                depends = taskData.tasks_tdepends[task]

                # Resolve Depends
                if 'deptask' in task_deps and taskData.tasks_name[task] in task_deps['deptask']:
                    taskname = task_deps['deptask'][taskData.tasks_name[task]]
                    for depid in taskData.depids[fnid]:
                        if depid in taskData.build_targets:
                            depdata = taskData.build_targets[depid][0]
                            if depdata:
                                dep = taskData.fn_index[depdata]
                                depends.append(taskData.gettask_id(dep, taskname))

                # Resolve Runtime Depends
                if 'rdeptask' in task_deps and taskData.tasks_name[task] in task_deps['rdeptask']:
                    taskname = task_deps['rdeptask'][taskData.tasks_name[task]]
                    for depid in taskData.rdepids[fnid]:
                        if depid in taskData.run_targets:
                            depdata = taskData.run_targets[depid][0]
                            if depdata:
                                dep = taskData.fn_index[depdata]
                                depends.append(taskData.gettask_id(dep, taskname))

                def add_recursive_build(depid):
                    """
                    Add build depends of depid to depends
                    (if we've not see it before)
                    (calls itself recursively)
                    """
                    if str(depid) in dep_seen:
                        return
                    dep_seen.append(depid)
                    if depid in taskData.build_targets:
                        depdata = taskData.build_targets[depid][0]
                        if depdata:
                            dep = taskData.fn_index[depdata]
                            taskid = taskData.gettask_id(dep, taskname)
                            depends.append(taskid)
                            fnid = taskData.tasks_fnid[taskid]
                            for nextdepid in taskData.depids[fnid]:
                                if nextdepid not in dep_seen:
                                    add_recursive_build(nextdepid)
                            for nextdepid in taskData.rdepids[fnid]:
                                if nextdepid not in rdep_seen:
                                    add_recursive_run(nextdepid)

                def add_recursive_run(rdepid):
                    """
                    Add runtime depends of rdepid to depends
                    (if we've not see it before)
                    (calls itself recursively)
                    """
                    if str(rdepid) in rdep_seen:
                        return
                    rdep_seen.append(rdepid)
                    if rdepid in taskData.run_targets:
                        depdata = taskData.run_targets[rdepid][0]
                        if depdata:
                            dep = taskData.fn_index[depdata]
                            taskid = taskData.gettask_id(dep, taskname)
                            depends.append(taskid)
                            fnid = taskData.tasks_fnid[taskid]
                            for nextdepid in taskData.depids[fnid]:
                                if nextdepid not in dep_seen:
                                    add_recursive_build(nextdepid)
                            for nextdepid in taskData.rdepids[fnid]:
                                if nextdepid not in rdep_seen:
                                    add_recursive_run(nextdepid)


                # Resolve Recursive Runtime Depends
                # Also includes all Build Depends (and their runtime depends)
                if 'recrdeptask' in task_deps and taskData.tasks_name[task] in task_deps['recrdeptask']:
                    dep_seen = []
                    rdep_seen = []
                    taskname = task_deps['recrdeptask'][taskData.tasks_name[task]]
                    for depid in taskData.depids[fnid]:
                        add_recursive_build(depid)
                    for rdepid in taskData.rdepids[fnid]:
                        add_recursive_run(rdepid)

                #Prune self references
                if task in depends:
                    newdep = []
                    bb.msg.debug(2, bb.msg.domain.RunQueue, "Task %s (%s %s) contains self reference! %s" % (task, taskData.fn_index[taskData.tasks_fnid[task]], taskData.tasks_name[task], depends))
                    for dep in depends:
                       if task != dep:
                          newdep.append(dep)
                    depends = newdep


            self.runq_fnid.append(taskData.tasks_fnid[task])
            self.runq_task.append(taskData.tasks_name[task])
            self.runq_depends.append(Set(depends))
            self.runq_revdeps.append(Set())
            self.runq_weight.append(0)

            runq_weight1.append(0)
            runq_build.append(0)
            runq_done.append(0)

        bb.msg.note(2, bb.msg.domain.RunQueue, "Marking Active Tasks")

        def mark_active(listid, depth):
            """
            Mark an item as active along with its depends
            (calls itself recursively)
            """

            if runq_build[listid] == 1:
                return

            runq_build[listid] = 1

            depends = self.runq_depends[listid]
            for depend in depends:
                mark_active(depend, depth+1)

        for target in targets:
            targetid = taskData.getbuild_id(target[0])
            if targetid in taskData.failed_deps:
                continue

            fnid = taskData.build_targets[targetid][0]
            if fnid in taskData.failed_fnids:
                continue

            fnids = taskData.matches_in_list(self.runq_fnid, fnid)
            tasks = taskData.matches_in_list(self.runq_task, target[1])

            listid = taskData.both_contain(fnids, tasks)

            mark_active(listid, 1)

        # Prune inactive tasks
        maps = []
        delcount = 0
        for listid in range(len(self.runq_fnid)):
            if runq_build[listid-delcount] == 1:
                maps.append(listid-delcount)
            else:
                del self.runq_fnid[listid-delcount]
                del self.runq_task[listid-delcount]
                del self.runq_depends[listid-delcount]
                del self.runq_weight[listid-delcount]
                del runq_weight1[listid-delcount]
                del runq_build[listid-delcount]
                del runq_done[listid-delcount]
                del self.runq_revdeps[listid-delcount]
                delcount = delcount + 1
                maps.append(-1)

        if len(self.runq_fnid) == 0:
            bb.msg.fatal(bb.msg.domain.RunQueue, "No active tasks?! Please report this bug.")

        bb.msg.note(2, bb.msg.domain.RunQueue, "Pruned %s inactive tasks, %s left" % (delcount, len(self.runq_fnid)))

        for listid in range(len(self.runq_fnid)):
            newdeps = []
            origdeps = self.runq_depends[listid]
            for origdep in origdeps:
                if maps[origdep] == -1:
                    bb.msg.fatal(bb.msg.domain.RunQueue, "Invalid mapping - Should never happen!")
                newdeps.append(maps[origdep])
            self.runq_depends[listid] = Set(newdeps)

        bb.msg.note(2, bb.msg.domain.RunQueue, "Assign Weightings")

        for listid in range(len(self.runq_fnid)):
            for dep in self.runq_depends[listid]:
                self.runq_revdeps[dep].add(listid)

        endpoints = []
        for listid in range(len(self.runq_fnid)):
            revdeps = self.runq_revdeps[listid]
            if len(revdeps) == 0:
                runq_done[listid] = 1
                self.runq_weight[listid] = 1
                endpoints.append(listid)
            for dep in revdeps:
                if dep in self.runq_depends[listid]:
                    #self.dump_data(taskData)
                    bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s (%s) has circular dependency on %s (%s)" % (taskData.fn_index[self.runq_fnid[dep]], self.runq_task[dep] , taskData.fn_index[self.runq_fnid[listid]], self.runq_task[listid]))
            runq_weight1[listid] = len(revdeps)

        bb.msg.note(2, bb.msg.domain.RunQueue, "Compute totals (have %s endpoint(s))" % len(endpoints))

        while 1:
            next_points = []
            for listid in endpoints:
                for revdep in self.runq_depends[listid]:
                    self.runq_weight[revdep] = self.runq_weight[revdep] + self.runq_weight[listid]
                    runq_weight1[revdep] = runq_weight1[revdep] - 1
                    if runq_weight1[revdep] == 0:
                        next_points.append(revdep)
                        runq_done[revdep] = 1
            endpoints = next_points
            if len(next_points) == 0:
                break           

        # Sanity Checks
        for task in range(len(self.runq_fnid)):
            if runq_done[task] == 0:
                seen = []
                def print_chain(taskid):
                    seen.append(taskid)
                    for revdep in self.runq_revdeps[taskid]:
                        if runq_done[revdep] == 0:
                            bb.msg.error(bb.msg.domain.RunQueue, "Task %s (%s) (depends: %s)" % (revdep, self.get_user_idstring(revdep, taskData), self.runq_depends[revdep]))
                            if revdep not in seen:
                                print_chain(revdep)
                print_chain(task)
                bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s (%s) not processed!\nThis is probably a circular dependency (the chain might be printed above)." % (task, self.get_user_idstring(task, taskData)))
            if runq_weight1[task] != 0:
                bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s (%s) count not zero!" % (task, self.get_user_idstring(task, taskData)))

        # Make a weight sorted map
        from copy import deepcopy

        sortweight = deepcopy(self.runq_weight)
        sortweight.sort()
        copyweight = deepcopy(self.runq_weight)
        self.prio_map = []

        for weight in sortweight:
            idx = copyweight.index(weight)
            self.prio_map.append(idx)
            copyweight[idx] = -1
        self.prio_map.reverse()

    def execute_runqueue(self, cooker, cfgData, dataCache, taskData, runlist):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        Upon failure, optionally try to recover the build using any alternate providers
        (if the abort on failure configuration option isn't set)
        """

        failures = 0
        while 1:
            try:
                self.execute_runqueue_internal(cooker, cfgData, dataCache, taskData)
                return failures
            except bb.runqueue.TaskFailure, (fnid, taskData.fn_index[fnid], taskname):
                if taskData.abort:
                    raise
                taskData.fail_fnid(fnid)
                self.reset_runqueue()
                self.prepare_runqueue(cfgData, dataCache, taskData, runlist)
                failures = failures + 1

    def execute_runqueue_internal(self, cooker, cfgData, dataCache, taskData):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        """

        bb.msg.note(1, bb.msg.domain.RunQueue, "Executing runqueue")

        runq_buildable = []
        runq_running = []
        runq_complete = []
        active_builds = 0
        build_pids = {}

        def get_next_task(data):
            """
            Return the id of the highest priority task that is buildable
            """
            for task1 in range(len(data.runq_fnid)):
                task = data.prio_map[task1]
                if runq_running[task] == 1:
                    continue
                if runq_buildable[task] == 1:
                    return task
            return None

        def task_complete(data, task):
            """
            Mark a task as completed
            Look at the reverse dependencies and mark any task with 
            completed dependencies as buildable
            """
            runq_complete[task] = 1
            for revdep in data.runq_revdeps[task]:
                if runq_running[revdep] == 1:
                    continue
                if runq_buildable[revdep] == 1:
                    continue
                alldeps = 1
                for dep in data.runq_depends[revdep]:
                    if runq_complete[dep] != 1:
                        alldeps = 0
                if alldeps == 1:
                    runq_buildable[revdep] = 1
                    fn = taskData.fn_index[self.runq_fnid[revdep]]
                    taskname = self.runq_task[revdep]
                    bb.msg.debug(1, bb.msg.domain.RunQueue, "Marking task %s (%s, %s) as buildable" % (revdep, fn, taskname))

        # Mark initial buildable tasks
        for task in range(len(self.runq_fnid)):
            runq_running.append(0)
            runq_complete.append(0)
            if len(self.runq_depends[task]) == 0:
                runq_buildable.append(1)
            else:
                runq_buildable.append(0)


        number_tasks = int(bb.data.getVar("BB_NUMBER_THREADS", cfgData) or 1)

        try:
            while 1:
                task = get_next_task(self)
                if task is not None:
                    fn = taskData.fn_index[self.runq_fnid[task]]
                    taskname = self.runq_task[task]

                    if bb.build.stamp_is_current_cache(dataCache, fn, taskname):
                        targetid = taskData.gettask_id(fn, taskname)
                        if not (targetid in taskData.external_targets and cooker.configuration.force):
                            bb.msg.debug(2, bb.msg.domain.RunQueue, "Stamp current task %s (%s)" % (task, self.get_user_idstring(task, taskData)))
                            runq_running[task] = 1
                            task_complete(self, task)
                            continue

                    bb.msg.debug(1, bb.msg.domain.RunQueue, "Running task %s (%s)" % (task, self.get_user_idstring(task, taskData)))
                    try: 
                        pid = os.fork() 
                    except OSError, e: 
                        bb.msg.fatal(bb.msg.domain.RunQueue, "fork failed: %d (%s)" % (e.errno, e.strerror))
                    if pid == 0:
                        cooker.configuration.cmd = taskname[3:]
                        try: 
                            cooker.tryBuild(fn, False)
                        except:
                            bb.msg.error(bb.msg.domain.Build, "Build of " + fn + " " + taskname + " failed")
                            raise
                        sys.exit(0)
                    build_pids[pid] = task
                    runq_running[task] = 1
                    active_builds = active_builds + 1
                    if active_builds < number_tasks:
                        continue
                if active_builds > 0:
                    result = os.waitpid(-1, 0)
                    active_builds = active_builds - 1
                    if result[1] != 0:
                        bb.msg.error(bb.msg.domain.RunQueue, "Task %s (%s) failed" % (build_pids[result[0]], self.get_user_idstring(build_pids[result[0]], taskData)))
                        raise bb.runqueue.TaskFailure(self.runq_fnid[build_pids[result[0]]], taskData.fn_index[self.runq_fnid[build_pids[result[0]]]], self.runq_task[build_pids[result[0]]])
                    task_complete(self, build_pids[result[0]])
                    del build_pids[result[0]]
                    continue
                break
        except SystemExit:
            raise
        except:
            bb.msg.error(bb.msg.domain.RunQueue, "Exception received")
            if active_builds > 0:
                while active_builds > 0:
                    bb.msg.note(1, bb.msg.domain.RunQueue, "Waiting for %s active tasks to finish" % active_builds)
                    tasknum = 1
                    for k, v in build_pids.iteritems():
                        bb.msg.note(1, bb.msg.domain.RunQueue, "%s: %s (%s)" % (tasknum, self.get_user_idstring(v, taskData), k))
                        tasknum = tasknum + 1
                    result = os.waitpid(-1, 0)
                    del build_pids[result[0]]		    
                    active_builds = active_builds - 1
            raise

        # Sanity Checks
        for task in range(len(self.runq_fnid)):
            if runq_buildable[task] == 0:
                bb.msg.error(bb.msg.domain.RunQueue, "Task %s never buildable!" % task)
            if runq_running[task] == 0:
                bb.msg.error(bb.msg.domain.RunQueue, "Task %s never ran!" % task)
            if runq_complete[task] == 0:
                bb.msg.error(bb.msg.domain.RunQueue, "Task %s never completed!" % task)

        return 0

    def dump_data(self, taskQueue):
        """
        Dump some debug information on the internal data structures
        """
        bb.msg.debug(3, bb.msg.domain.RunQueue, "run_tasks:")
        for task in range(len(self.runq_fnid)):
                bb.msg.debug(3, bb.msg.domain.RunQueue, " (%s)%s - %s: %s   Deps %s RevDeps %s" % (task, 
                        taskQueue.fn_index[self.runq_fnid[task]], 
                        self.runq_task[task], 
                        self.runq_weight[task], 
                        self.runq_depends[task], 
                        self.runq_revdeps[task]))

        bb.msg.debug(3, bb.msg.domain.RunQueue, "sorted_tasks:")
        for task1 in range(len(self.runq_fnid)):
            if task1 in self.prio_map:
                task = self.prio_map[task1]
                bb.msg.debug(3, bb.msg.domain.RunQueue, " (%s)%s - %s: %s   Deps %s RevDeps %s" % (task, 
                        taskQueue.fn_index[self.runq_fnid[task]], 
                        self.runq_task[task], 
                        self.runq_weight[task], 
                        self.runq_depends[task], 
                        self.runq_revdeps[task]))
