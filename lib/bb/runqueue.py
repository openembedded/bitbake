#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'RunQueue' implementation

Handles preparation and execution of a queue of tasks
"""

# Copyright (C) 2006-2007  Richard Purdie
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

from bb import msg, data, event, mkdirhier, utils
from sets import Set 
import bb, os, sys
import signal

class TaskFailure(Exception):
    """Exception raised when a task in a runqueue fails"""
    def __init__(self, x): 
        self.args = x


class RunQueueStats:
    """
    Holds statistics on the tasks handled by the associated runQueue
    """
    def __init__(self, total):
        self.completed = 0
        self.skipped = 0
        self.failed = 0
        self.active = 0
        self.total = total

    def taskFailed(self):
        self.active = self.active - 1
        self.failed = self.failed + 1

    def taskCompleted(self):
        self.active = self.active - 1
        self.completed = self.completed + 1

    def taskSkipped(self):
        self.active = self.active + 1
        self.skipped = self.skipped + 1

    def taskActive(self):
        self.active = self.active + 1

# These values indicate the next step due to be run in the 
# runQueue state machine
runQueuePrepare = 2
runQueueRunInit = 3
runQueueRunning = 4
runQueueFailedCleanUp = 5
runQueueFailed = 6
runQueueCleanUp = 7
runQueueComplete = 8
runQueueChildProcess = 9

class RunQueueScheduler:
    """
    Control the order tasks are scheduled in.
    """
    def __init__(self, runqueue):
        """
        The default scheduler just returns the first buildable task (the 
        priority map is sorted by task numer)
        """
        self.rq = runqueue
        numTasks = len(self.rq.runq_fnid)

        self.prio_map = []
        self.prio_map.extend(range(numTasks))

    def next(self):
        """
        Return the id of the first task we find that is buildable
        """
        for task1 in range(len(self.rq.runq_fnid)):
            task = self.prio_map[task1]
            if self.rq.runq_running[task] == 1:
                continue
            if self.rq.runq_buildable[task] == 1:
                return task

class RunQueueSchedulerSpeed(RunQueueScheduler):
    """
    A scheduler optimised for speed. The priority map is sorted by task weight,
    heavier weighted tasks (tasks needed by the most other tasks) are run first.
    """
    def __init__(self, runqueue):
        """
        The priority map is sorted by task weight.
        """
        from copy import deepcopy

        self.rq = runqueue

        sortweight = deepcopy(self.rq.runq_weight)
        sortweight.sort()
        copyweight = deepcopy(self.rq.runq_weight)
        self.prio_map = []

        for weight in sortweight:
            idx = copyweight.index(weight)
            self.prio_map.append(idx)
            copyweight[idx] = -1

        self.prio_map.reverse()

class RunQueueSchedulerCompletion(RunQueueSchedulerSpeed):
    """
    A scheduler optimised to complete .bb files are quickly as possible. The 
    priority map is sorted by task weight, but then reordered so once a given 
    .bb file starts to build, its completed as quickly as possible. This works
    well where disk space is at a premium and classes like OE's rm_work are in 
    force.
    """
    def __init__(self, runqueue):
        RunQueueSchedulerSpeed.__init__(self, runqueue)
        from copy import deepcopy

        #FIXME - whilst this groups all fnids together it does not reorder the
        #fnid groups optimally.
 
        basemap = deepcopy(self.prio_map)
        self.prio_map = []
        while (len(basemap) > 0):
            entry = basemap.pop(0)
            self.prio_map.append(entry)
            fnid = self.rq.runq_fnid[entry]
            todel = []
            for entry in basemap:
                entry_fnid = self.rq.runq_fnid[entry]
                if entry_fnid == fnid:
                    todel.append(basemap.index(entry))
                    self.prio_map.append(entry)
            todel.reverse()
            for idx in todel:
                del basemap[idx]

class RunQueue:
    """
    BitBake Run Queue implementation
    """
    def __init__(self, cooker, cfgData, dataCache, taskData, targets):
        self.reset_runqueue()
        self.cooker = cooker
        self.dataCache = dataCache
        self.taskData = taskData
        self.cfgData = cfgData
        self.targets = targets

        self.number_tasks = int(bb.data.getVar("BB_NUMBER_THREADS", cfgData) or 1)
        self.multi_provider_whitelist = (bb.data.getVar("MULTI_PROVIDER_WHITELIST", cfgData) or "").split()

    def reset_runqueue(self):
        self.runq_fnid = []
        self.runq_task = []
        self.runq_depends = []
        self.runq_revdeps = []

        self.state = runQueuePrepare

    def get_user_idstring(self, task):
        fn = self.taskData.fn_index[self.runq_fnid[task]]
        taskname = self.runq_task[task]
        return "%s, %s" % (fn, taskname)

    def circular_depchains_handler(self, tasks):
        """
        Some tasks aren't buildable, likely due to circular dependency issues.
        Identify the circular dependencies and print them in a user readable format.
        """
        from copy import deepcopy

        valid_chains = []
        explored_deps = {}
        msgs = []

        def chain_reorder(chain):
            """
            Reorder a dependency chain so the lowest task id is first
            """
            lowest = 0
            new_chain = []
            for entry in range(len(chain)):
                if chain[entry] < chain[lowest]:
                    lowest = entry
            new_chain.extend(chain[lowest:])
            new_chain.extend(chain[:lowest])
            return new_chain

        def chain_compare_equal(chain1, chain2):
            """
            Compare two dependency chains and see if they're the same
            """
            if len(chain1) != len(chain2):
                return False
            for index in range(len(chain1)):
                if chain1[index] != chain2[index]:
                    return False
            return True
            
        def chain_array_contains(chain, chain_array):
            """
            Return True if chain_array contains chain
            """
            for ch in chain_array:
                if chain_compare_equal(ch, chain):
                    return True
            return False

        def find_chains(taskid, prev_chain):
            prev_chain.append(taskid)
            total_deps = []
            total_deps.extend(self.runq_revdeps[taskid])
            for revdep in self.runq_revdeps[taskid]:
                if revdep in prev_chain:
                    idx = prev_chain.index(revdep)
                    # To prevent duplicates, reorder the chain to start with the lowest taskid
                    # and search through an array of those we've already printed
                    chain = prev_chain[idx:]
                    new_chain = chain_reorder(chain)
                    if not chain_array_contains(new_chain, valid_chains):
                        valid_chains.append(new_chain)
                        msgs.append("Dependency loop #%d found:\n" % len(valid_chains))
                        for dep in new_chain:
                            msgs.append("  Task %s (%s) (depends: %s)\n" % (dep, self.get_user_idstring(dep), self.runq_depends[dep]))
                        msgs.append("\n")
                    if len(valid_chains) > 10:
                        msgs.append("Aborted dependency loops search after 10 matches.\n")
                        return msgs
                    continue
                scan = False
                if revdep not in explored_deps:
                    scan = True
                elif revdep in explored_deps[revdep]:
                    scan = True
                else:
                    for dep in prev_chain:
                        if dep in explored_deps[revdep]:
                            scan = True
                if scan:
                    find_chains(revdep, deepcopy(prev_chain))
                for dep in explored_deps[revdep]:
                    if dep not in total_deps:
                        total_deps.append(dep)

            explored_deps[taskid] = total_deps

        for task in tasks:
            find_chains(task, [])

        return msgs

    def calculate_task_weights(self, endpoints):
        """
        Calculate a number representing the "weight" of each task. Heavier weighted tasks 
        have more dependencies and hence should be executed sooner for maximum speed.

        This function also sanity checks the task list finding tasks that its not
        possible to execute due to circular dependencies.
        """

        numTasks = len(self.runq_fnid)
        weight = []
        deps_left = []
        task_done = []

        for listid in range(numTasks):
            task_done.append(False)
            weight.append(0)
            deps_left.append(len(self.runq_revdeps[listid]))

        for listid in endpoints:
            weight[listid] = 1
            task_done[listid] = True

        while 1:
            next_points = []
            for listid in endpoints:
                for revdep in self.runq_depends[listid]:
                    weight[revdep] = weight[revdep] + weight[listid]
                    deps_left[revdep] = deps_left[revdep] - 1
                    if deps_left[revdep] == 0:
                        next_points.append(revdep)
                        task_done[revdep] = True
            endpoints = next_points
            if len(next_points) == 0:
                break      

        # Circular dependency sanity check
        problem_tasks = []
        for task in range(numTasks):
            if task_done[task] is False or deps_left[task] != 0:
                problem_tasks.append(task)
                bb.msg.debug(2, bb.msg.domain.RunQueue, "Task %s (%s) is not buildable\n" % (task, self.get_user_idstring(task)))
                bb.msg.debug(2, bb.msg.domain.RunQueue, "(Complete marker was %s and the remaining dependency count was %s)\n\n" % (task_done[task], deps_left[task]))

        if problem_tasks:
            message = "Unbuildable tasks were found.\n"
            message = message + "These are usually caused by circular dependencies and any circular dependency chains found will be printed below. Increase the debug level to see a list of unbuildable tasks.\n\n"
            message = message + "Identifying dependency loops (this may take a short while)...\n"
            bb.msg.error(bb.msg.domain.RunQueue, message)

            msgs = self.circular_depchains_handler(problem_tasks)

            message = "\n"
            for msg in msgs:
                message = message + msg
            bb.msg.fatal(bb.msg.domain.RunQueue, message)

        return weight

    def prepare_runqueue(self):
        """
        Turn a set of taskData into a RunQueue and compute data needed 
        to optimise the execution order.
        """

        depends = []
        runq_build = []

        taskData = self.taskData

        if len(taskData.tasks_name) == 0:
            # Nothing to do
            return

        bb.msg.note(1, bb.msg.domain.RunQueue, "Preparing runqueue")

        # Step A - Work out a list of tasks to run
        #
        # Taskdata gives us a list of possible providers for a every target 
        # ordered by priority (build_targets, run_targets). It also gives
        # information on each of those providers.
        #
        # To create the actual list of tasks to execute we fix the list of 
        # providers and then resolve the dependencies into task IDs. This 
        # process is repeated for each type of dependency (tdepends, deptask, 
        # rdeptast, recrdeptask, idepends).

        for task in range(len(taskData.tasks_name)):
            fnid = taskData.tasks_fnid[task]
            fn = taskData.fn_index[fnid]
            task_deps = self.dataCache.task_deps[fn]

            if fnid not in taskData.failed_fnids:

                # Resolve task internal dependencies 
                #
                # e.g. addtask before X after Y
                depends = taskData.tasks_tdepends[task]

                # Resolve 'deptask' dependencies 
                #
                # e.g. do_sometask[deptask] = "do_someothertask"
                # (makes sure sometask runs after someothertask of all DEPENDS)
                if 'deptask' in task_deps and taskData.tasks_name[task] in task_deps['deptask']:
                    tasknames = task_deps['deptask'][taskData.tasks_name[task]].split()
                    for depid in taskData.depids[fnid]:
                        # Won't be in build_targets if ASSUME_PROVIDED
                        if depid in taskData.build_targets:
                            depdata = taskData.build_targets[depid][0]
                            if depdata is not None:
                                dep = taskData.fn_index[depdata]
                                for taskname in tasknames:
                                    depends.append(taskData.gettask_id(dep, taskname))

                # Resolve 'rdeptask' dependencies 
                #
                # e.g. do_sometask[rdeptask] = "do_someothertask"
                # (makes sure sometask runs after someothertask of all RDEPENDS)
                if 'rdeptask' in task_deps and taskData.tasks_name[task] in task_deps['rdeptask']:
                    taskname = task_deps['rdeptask'][taskData.tasks_name[task]]
                    for depid in taskData.rdepids[fnid]:
                        if depid in taskData.run_targets:
                            depdata = taskData.run_targets[depid][0]
                            if depdata is not None:
                                dep = taskData.fn_index[depdata]
                                depends.append(taskData.gettask_id(dep, taskname))

                # Resolve inter-task dependencies 
                #
                # e.g. do_sometask[depends] = "targetname:do_someothertask"
                # (makes sure sometask runs after targetname's someothertask)
                idepends = taskData.tasks_idepends[task]
                for idepend in idepends:
                    depid = int(idepend.split(":")[0])
                    if depid in taskData.build_targets:
                        # Won't be in build_targets if ASSUME_PROVIDED
                        depdata = taskData.build_targets[depid][0]
                        if depdata is not None:
                            dep = taskData.fn_index[depdata]
                            depends.append(taskData.gettask_id(dep, idepend.split(":")[1]))

                def add_recursive_build(depid, depfnid):
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
                        if depdata is not None:
                            dep = taskData.fn_index[depdata]
                            idepends = []
                            # Need to avoid creating new tasks here
                            taskid = taskData.gettask_id(dep, taskname, False)
                            if taskid is not None:
                                depends.append(taskid)
                                fnid = taskData.tasks_fnid[taskid]
                                idepends = taskData.tasks_idepends[taskid]
                                #print "Added %s (%s) due to %s" % (taskid, taskData.fn_index[fnid], taskData.fn_index[depfnid])
                            else:
                                fnid = taskData.getfn_id(dep)
                            for nextdepid in taskData.depids[fnid]:
                                if nextdepid not in dep_seen:
                                    add_recursive_build(nextdepid, fnid)
                            for nextdepid in taskData.rdepids[fnid]:
                                if nextdepid not in rdep_seen:
                                    add_recursive_run(nextdepid, fnid)
                            for idepend in idepends:
                                nextdepid = int(idepend.split(":")[0])
                                if nextdepid not in dep_seen:
                                    add_recursive_build(nextdepid, fnid)

                def add_recursive_run(rdepid, depfnid):
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
                        if depdata is not None:
                            dep = taskData.fn_index[depdata]
                            idepends = []
                            # Need to avoid creating new tasks here
                            taskid = taskData.gettask_id(dep, taskname, False)
                            if taskid is not None:
                                depends.append(taskid)
                                fnid = taskData.tasks_fnid[taskid]
                                idepends = taskData.tasks_idepends[taskid]
                                #print "Added %s (%s) due to %s" % (taskid, taskData.fn_index[fnid], taskData.fn_index[depfnid])
                            else:
                                fnid = taskData.getfn_id(dep)
                            for nextdepid in taskData.depids[fnid]:
                                if nextdepid not in dep_seen:
                                    add_recursive_build(nextdepid, fnid)
                            for nextdepid in taskData.rdepids[fnid]:
                                if nextdepid not in rdep_seen:
                                    add_recursive_run(nextdepid, fnid)
                            for idepend in idepends:
                                nextdepid = int(idepend.split(":")[0])
                                if nextdepid not in dep_seen:
                                    add_recursive_build(nextdepid, fnid)

                # Resolve recursive 'recrdeptask' dependencies 
                #
                # e.g. do_sometask[recrdeptask] = "do_someothertask"
                # (makes sure sometask runs after someothertask of all DEPENDS, RDEPENDS and intertask dependencies, recursively)
                if 'recrdeptask' in task_deps and taskData.tasks_name[task] in task_deps['recrdeptask']:
                    for taskname in task_deps['recrdeptask'][taskData.tasks_name[task]].split():
                        dep_seen = []
                        rdep_seen = []
                        idep_seen = []
                        for depid in taskData.depids[fnid]:
                            add_recursive_build(depid, fnid)
                        for rdepid in taskData.rdepids[fnid]:
                            add_recursive_run(rdepid, fnid)
                        for idepend in idepends:
                            depid = int(idepend.split(":")[0])
                            add_recursive_build(depid, fnid)

                # Rmove all self references
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

            runq_build.append(0)

        # Step B - Mark all active tasks
        #
        # Start with the tasks we were asked to run and mark all dependencies
        # as active too. If the task is to be 'forced', clear its stamp. Once
        # all active tasks are marked, prune the ones we don't need.

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

        for target in self.targets:
            targetid = taskData.getbuild_id(target[0])

            if targetid not in taskData.build_targets:
                continue

            if targetid in taskData.failed_deps:
                continue

            fnid = taskData.build_targets[targetid][0]

            # Remove stamps for targets if force mode active
            if self.cooker.configuration.force:
                fn = taskData.fn_index[fnid]
                bb.msg.note(2, bb.msg.domain.RunQueue, "Remove stamp %s, %s" % (target[1], fn))
                bb.build.del_stamp(target[1], self.dataCache, fn)

            if fnid in taskData.failed_fnids:
                continue

            if target[1] not in taskData.tasks_lookup[fnid]:
                bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s does not exist for target %s" % (target[1], target[0]))

            listid = taskData.tasks_lookup[fnid][target[1]]

            mark_active(listid, 1)

        # Step C - Prune all inactive tasks
        #
        # Once all active tasks are marked, prune the ones we don't need.

        maps = []
        delcount = 0
        for listid in range(len(self.runq_fnid)):
            if runq_build[listid-delcount] == 1:
                maps.append(listid-delcount)
            else:
                del self.runq_fnid[listid-delcount]
                del self.runq_task[listid-delcount]
                del self.runq_depends[listid-delcount]
                del runq_build[listid-delcount]
                del self.runq_revdeps[listid-delcount]
                delcount = delcount + 1
                maps.append(-1)

        #
        # Step D - Sanity checks and computation
        #

        # Check to make sure we still have tasks to run
        if len(self.runq_fnid) == 0:
            if not taskData.abort:
                bb.msg.note(1, bb.msg.domain.RunQueue, "All possible tasks have been run but build incomplete (--continue mode). See errors above for incomplete tasks.")
                return
            bb.msg.fatal(bb.msg.domain.RunQueue, "No active tasks and not in --continue mode?! Please report this bug.")

        bb.msg.note(2, bb.msg.domain.RunQueue, "Pruned %s inactive tasks, %s left" % (delcount, len(self.runq_fnid)))

        # Remap the dependencies to account for the deleted tasks
        # Check we didn't delete a task we depend on
        for listid in range(len(self.runq_fnid)):
            newdeps = []
            origdeps = self.runq_depends[listid]
            for origdep in origdeps:
                if maps[origdep] == -1:
                    bb.msg.fatal(bb.msg.domain.RunQueue, "Invalid mapping - Should never happen!")
                newdeps.append(maps[origdep])
            self.runq_depends[listid] = Set(newdeps)

        bb.msg.note(2, bb.msg.domain.RunQueue, "Assign Weightings")

        # Generate a list of reverse dependencies to ease future calculations
        for listid in range(len(self.runq_fnid)):
            for dep in self.runq_depends[listid]:
                self.runq_revdeps[dep].add(listid)

        # Identify tasks at the end of dependency chains
        # Error on circular dependency loops (length two)
        endpoints = []
        for listid in range(len(self.runq_fnid)):
            revdeps = self.runq_revdeps[listid]
            if len(revdeps) == 0:
                endpoints.append(listid)
            for dep in revdeps:
                if dep in self.runq_depends[listid]:
                    #self.dump_data(taskData)
                    bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s (%s) has circular dependency on %s (%s)" % (taskData.fn_index[self.runq_fnid[dep]], self.runq_task[dep] , taskData.fn_index[self.runq_fnid[listid]], self.runq_task[listid]))

        bb.msg.note(2, bb.msg.domain.RunQueue, "Compute totals (have %s endpoint(s))" % len(endpoints))

        # Calculate task weights 
        # Check of higher length circular dependencies
        self.runq_weight = self.calculate_task_weights(endpoints)

        # Decide what order to execute the tasks in, pick a scheduler
        # FIXME - Allow user selection
        #self.sched = RunQueueScheduler(self)
        self.sched = RunQueueSchedulerSpeed(self)
        #self.sched = RunQueueSchedulerCompletion(self)

        # Sanity Check - Check for multiple tasks building the same provider
        prov_list = {}
        seen_fn = []
        for task in range(len(self.runq_fnid)):
            fn = taskData.fn_index[self.runq_fnid[task]]
            if fn in seen_fn:
                continue
            seen_fn.append(fn)
            for prov in self.dataCache.fn_provides[fn]:
                if prov not in prov_list:
                    prov_list[prov] = [fn]
                elif fn not in prov_list[prov]: 
                    prov_list[prov].append(fn)
        error = False
        for prov in prov_list:
            if len(prov_list[prov]) > 1 and prov not in self.multi_provider_whitelist:
                error = True
                bb.msg.error(bb.msg.domain.RunQueue, "Multiple files due to be built which all provide %s (%s)" % (prov, " ".join(prov_list[prov])))
        #if error:
        #    bb.msg.fatal(bb.msg.domain.RunQueue, "Corrupted metadata configuration detected, aborting...")

        #self.dump_data(taskData)

        self.state = runQueueRunInit

    def execute_runqueue(self):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        Upon failure, optionally try to recover the build using any alternate providers
        (if the abort on failure configuration option isn't set)
        """

        if self.state is runQueuePrepare:
            self.prepare_runqueue()

        if self.state is runQueueRunInit:
            bb.msg.note(1, bb.msg.domain.RunQueue, "Executing runqueue")
            self.execute_runqueue_initVars()

        if self.state is runQueueRunning:
            self.execute_runqueue_internal()

        if self.state is runQueueFailedCleanUp:
            self.finish_runqueue()

        if self.state is runQueueCleanUp:
            self.finish_runqueue()

        if self.state is runQueueFailed:
            if self.taskData.abort:
                raise bb.runqueue.TaskFailure(self.failed_fnids)
            self.reset_runqueue()

        if self.state is runQueueComplete:
            # All done
            bb.msg.note(1, bb.msg.domain.RunQueue, "Tasks Summary: Attempted %d tasks of which %d didn't need to be rerun and %d failed." % (self.stats.completed, self.stats.skipped, self.stats.failed))
            return False

        if self.state is runQueueChildProcess:
            print "Child process"
            return False

        # Loop
        return True

    def execute_runqueue_initVars(self):

        self.stats = RunQueueStats(len(self.runq_fnid))

        self.runq_buildable = []
        self.runq_running = []
        self.runq_complete = []
        self.build_pids = {}
        self.failed_fnids = []

        # Mark initial buildable tasks
        for task in range(self.stats.total):
            self.runq_running.append(0)
            self.runq_complete.append(0)
            if len(self.runq_depends[task]) == 0:
                self.runq_buildable.append(1)
            else:
                self.runq_buildable.append(0)

        self.state = runQueueRunning

     # RP - this code allows tasks to run out of the correct order - disabled, FIXME
        # Find any tasks with current stamps and remove them from the queue
     #   for task1 in range(self.stats.total):
     #       task = self.prio_map[task1]
     #       fn = self.taskData.fn_index[self.runq_fnid[task]]
     #       taskname = self.runq_task[task]
     #       if bb.build.stamp_is_current(taskname, self.dataCache, fn):
     #           bb.msg.debug(2, bb.msg.domain.RunQueue, "Stamp current task %s (%s)" % (task, self.get_user_idstring(task)))
     #           self.runq_running[task] = 1
     #           self.runq_buildable[task] = 1
     #           self.task_complete(task)
     #           self.stats.taskCompleted()
     #           self.stats.taskSkipped()

    def task_complete(self, task):
        """
        Mark a task as completed
        Look at the reverse dependencies and mark any task with 
        completed dependencies as buildable
        """
        self.runq_complete[task] = 1
        for revdep in self.runq_revdeps[task]:
            if self.runq_running[revdep] == 1:
                continue
            if self.runq_buildable[revdep] == 1:
                continue
            alldeps = 1
            for dep in self.runq_depends[revdep]:
                if self.runq_complete[dep] != 1:
                    alldeps = 0
            if alldeps == 1:
                self.runq_buildable[revdep] = 1
                fn = self.taskData.fn_index[self.runq_fnid[revdep]]
                taskname = self.runq_task[revdep]
                bb.msg.debug(1, bb.msg.domain.RunQueue, "Marking task %s (%s, %s) as buildable" % (revdep, fn, taskname))

    def task_fail(self, task, exitcode):
        """
        Called when a task has failed
        Updates the state engine with the failure
        """
        bb.msg.error(bb.msg.domain.RunQueue, "Task %s (%s) failed with %s" % (task, self.get_user_idstring(task), exitcode))
        self.stats.taskFailed()
        fnid = self.runq_fnid[task]
        self.failed_fnids.append(fnid)
        if not self.taskData.abort:
            self.taskData.fail_fnid(fnid)
        self.state = runQueueFailedCleanUp
        bb.event.fire(runQueueTaskFailed(task, self.stats, self, self.cfgData))

    def execute_runqueue_internal(self):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        """

        if self.stats.total == 0:
            # nothing to do
            self.state = runQueueCleanup

        while True:
            task = None
            if self.stats.active < self.number_tasks:
                task = self.sched.next()
            if task is not None:
                fn = self.taskData.fn_index[self.runq_fnid[task]]

                taskname = self.runq_task[task]
                if bb.build.stamp_is_current(taskname, self.dataCache, fn):
                    bb.msg.debug(2, bb.msg.domain.RunQueue, "Stamp current task %s (%s)" % (task, self.get_user_idstring(task)))
                    self.runq_running[task] = 1
                    self.runq_buildable[task] = 1
                    self.task_complete(task)
                    self.stats.taskCompleted()
                    self.stats.taskSkipped()
                    continue

                bb.event.fire(runQueueTaskStarted(task, self.stats, self, self.cfgData))
                bb.msg.note(1, bb.msg.domain.RunQueue, "Running task %d of %d (ID: %s, %s)" % (self.stats.completed + self.stats.active + 1, self.stats.total, task, self.get_user_idstring(task)))
                try: 
                    pid = os.fork() 
                except OSError, e: 
                    bb.msg.fatal(bb.msg.domain.RunQueue, "fork failed: %d (%s)" % (e.errno, e.strerror))
                if pid == 0:
                    self.state = runQueueChildProcess
                    # Make the child the process group leader
                    os.setpgid(0, 0)
                    newsi = os.open('/dev/null', os.O_RDWR)
                    os.dup2(newsi, sys.stdin.fileno())
                    self.cooker.configuration.cmd = taskname[3:]
                    try: 
                        self.cooker.tryBuild(fn, False)
                    except bb.build.EventException:
                        bb.msg.error(bb.msg.domain.Build, "Build of " + fn + " " + taskname + " failed")
                        sys.exit(1)
                    except:
                        bb.msg.error(bb.msg.domain.Build, "Build of " + fn + " " + taskname + " failed")
                        raise
                    sys.exit(0)
                self.build_pids[pid] = task
                self.runq_running[task] = 1
                self.stats.taskActive()
                if self.stats.active < self.number_tasks:
                    continue
            if self.stats.active > 0:
                result = os.waitpid(-1, os.WNOHANG)
                if result[0] is 0 and result[1] is 0:
                    return
                task = self.build_pids[result[0]]
                del self.build_pids[result[0]]
                if result[1] != 0:
                    self.task_fail(task, result[1])
                    return
                self.task_complete(task)
                self.stats.taskCompleted()
                bb.event.fire(runQueueTaskCompleted(task, self.stats, self, self.cfgData))
                continue

            # Sanity Checks
            for task in range(self.stats.total):
                if self.runq_buildable[task] == 0:
                    bb.msg.error(bb.msg.domain.RunQueue, "Task %s never buildable!" % task)
                if self.runq_running[task] == 0:
                    bb.msg.error(bb.msg.domain.RunQueue, "Task %s never ran!" % task)
                if self.runq_complete[task] == 0:
                    bb.msg.error(bb.msg.domain.RunQueue, "Task %s never completed!" % task)
            self.state = runQueueComplete
            return

    def finish_runqueue_now(self):
        bb.msg.note(1, bb.msg.domain.RunQueue, "Sending SIGINT to remaining %s tasks" % self.stats.active)
        for k, v in self.build_pids.iteritems():
             try:
                 os.kill(-k, signal.SIGINT)
             except:
                 pass

    def finish_runqueue(self, now = False):
        self.state = runQueueCleanUp
        if now:
            self.finish_runqueue_now()
        try:
            while self.stats.active > 0:
                bb.event.fire(runQueueExitWait(self.stats.active, self.cfgData))
                bb.msg.note(1, bb.msg.domain.RunQueue, "Waiting for %s active tasks to finish" % self.stats.active)
                tasknum = 1
                for k, v in self.build_pids.iteritems():
                    bb.msg.note(1, bb.msg.domain.RunQueue, "%s: %s (%s)" % (tasknum, self.get_user_idstring(v), k))
                    tasknum = tasknum + 1
                result = os.waitpid(-1, os.WNOHANG)
                if result[0] is 0 and result[1] is 0:
                    return
                task = self.build_pids[result[0]]
                del self.build_pids[result[0]]
                if result[1] != 0:
                    self.task_fail(task, result[1])
                else:
                    self.stats.taskCompleted()
                    bb.event.fire(runQueueTaskCompleted(task, self.stats, self, self.cfgData))
            if self.state is runQueueFailedCleanUp:
                self.state = runQueueFailed
                return
        except:
            self.finish_runqueue_now()
            raise

        self.state = runQueueComplete
        return

    def dump_data(self, taskQueue):
        """
        Dump some debug information on the internal data structures
        """
        bb.msg.debug(3, bb.msg.domain.RunQueue, "run_tasks:")
        for task in range(len(self.runq_task)):
                bb.msg.debug(3, bb.msg.domain.RunQueue, " (%s)%s - %s: %s   Deps %s RevDeps %s" % (task, 
                        taskQueue.fn_index[self.runq_fnid[task]], 
                        self.runq_task[task], 
                        self.runq_weight[task], 
                        self.runq_depends[task], 
                        self.runq_revdeps[task]))

        bb.msg.debug(3, bb.msg.domain.RunQueue, "sorted_tasks:")
        for task1 in range(len(self.runq_task)):
            if task1 in self.prio_map:
                task = self.prio_map[task1]
                bb.msg.debug(3, bb.msg.domain.RunQueue, " (%s)%s - %s: %s   Deps %s RevDeps %s" % (task, 
                        taskQueue.fn_index[self.runq_fnid[task]], 
                        self.runq_task[task], 
                        self.runq_weight[task], 
                        self.runq_depends[task], 
                        self.runq_revdeps[task]))


class TaskFailure(Exception):
    """
    Exception raised when a task in a runqueue fails
    """
    def __init__(self, x): 
        self.args = x


class runQueueExitWait(bb.event.Event):
    """
    Event when waiting for task processes to exit
    """

    def __init__(self, remain, d):
        self.remain = remain
        self.message = "Waiting for %s active tasks to finish" % remain
        bb.event.Event.__init__(self, d)

class runQueueEvent(bb.event.Event):
    """
    Base runQueue event class
    """
    def __init__(self, task, stats, rq, d):
        self.taskid = task
        self.taskstring = rq.get_user_idstring(task)
        self.stats = stats
        bb.event.Event.__init__(self, d)

class runQueueTaskStarted(runQueueEvent):
    """
    Event notifing a task was started
    """
    def __init__(self, task, stats, rq, d):
        runQueueEvent.__init__(self, task, stats, rq, d)
        self.message = "Running task %s (%d of %d) (%s)" % (task, stats.completed + stats.active + 1, self.stats.total, self.taskstring)

class runQueueTaskFailed(runQueueEvent):
    """
    Event notifing a task failed
    """
    def __init__(self, task, stats, rq, d):
        runQueueEvent.__init__(self, task, stats, rq, d)
        self.message = "Task %s failed (%s)" % (task, self.taskstring)

class runQueueTaskCompleted(runQueueEvent):
    """
    Event notifing a task completed
    """
    def __init__(self, task, stats, rq, d):
        runQueueEvent.__init__(self, task, stats, rq, d)
        self.message = "Task %s completed (%s)" % (task, self.taskstring)

