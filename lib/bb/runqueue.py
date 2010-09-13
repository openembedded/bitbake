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

import os
import sys
import signal
import stat
import fcntl
import logging
import bb
from bb import msg, data, event

bblogger = logging.getLogger("BitBake")
logger = logging.getLogger("BitBake.RunQueue")

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

    def taskCompleted(self, number = 1):
        self.active = self.active - number
        self.completed = self.completed + number

    def taskSkipped(self, number = 1):
        self.active = self.active + number
        self.skipped = self.skipped + number

    def taskActive(self):
        self.active = self.active + 1

# These values indicate the next step due to be run in the
# runQueue state machine
runQueuePrepare = 2
runQueueRunInit = 3
runQueueRunning = 4
runQueueFailed = 6
runQueueCleanUp = 7
runQueueComplete = 8
runQueueChildProcess = 9

class RunQueueScheduler(object):
    """
    Control the order tasks are scheduled in.
    """
    name = "basic"

    def __init__(self, runqueue):
        """
        The default scheduler just returns the first buildable task (the
        priority map is sorted by task numer)
        """
        self.rq = runqueue
        numTasks = len(self.rq.runq_fnid)

        self.prio_map = []
        self.prio_map.extend(range(numTasks))

    def next_buildable_tasks(self):
        """
        Return the id of the first task we find that is buildable
        """
        for tasknum in xrange(len(self.rq.runq_fnid)):
            taskid = self.prio_map[tasknum]
            if self.rq.runq_running[taskid] == 1:
                continue
            if self.rq.runq_buildable[taskid] == 1:
                yield taskid

    def next(self):
        """
        Return the id of the task we should build next
        """
        if self.rq.stats.active < self.rq.number_tasks:
            return next(self.next_buildable_tasks(), None)

class RunQueueSchedulerSpeed(RunQueueScheduler):
    """
    A scheduler optimised for speed. The priority map is sorted by task weight,
    heavier weighted tasks (tasks needed by the most other tasks) are run first.
    """
    name = "speed"

    def __init__(self, runqueue):
        """
        The priority map is sorted by task weight.
        """
        from copy import deepcopy

        self.rq = runqueue

        sortweight = sorted(deepcopy(self.rq.runq_weight))
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
    name = "completion"

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

        self.number_tasks = int(bb.data.getVar("BB_NUMBER_THREADS", cfgData, 1) or 1)
        self.multi_provider_whitelist = (bb.data.getVar("MULTI_PROVIDER_WHITELIST", cfgData, 1) or "").split()
        self.scheduler = bb.data.getVar("BB_SCHEDULER", cfgData, 1) or "speed"
        self.stamppolicy = bb.data.getVar("BB_STAMP_POLICY", cfgData, 1) or "perfile"
        self.stampwhitelist = bb.data.getVar("BB_STAMP_WHITELIST", cfgData, 1) or ""

        self.schedulers = set(obj for obj in globals().itervalues()
                              if type(obj) is type and issubclass(obj, RunQueueScheduler))

        user_schedulers = bb.data.getVar("BB_SCHEDULERS", cfgData, True)
        if user_schedulers:
            for sched in user_schedulers.split():
                if not "." in sched:
                    bb.note("Ignoring scheduler '%s' from BB_SCHEDULERS: not an import" % sched)
                    continue

                modname, name = sched.rsplit(".", 1)
                try:
                    module = __import__(modname, fromlist=(name,))
                except ImportError, exc:
                    logger.critical("Unable to import scheduler '%s' from '%s': %s" % (name, modname, exc))
                    raise SystemExit(1)
                else:
                    self.schedulers.add(getattr(module, name))

    def reset_runqueue(self):
        self.runq_fnid = []
        self.runq_task = []
        self.runq_depends = []
        self.runq_revdeps = []
        self.state = runQueuePrepare

    def runq_depends_names(self, ids):
        import re
        ret = []
        for id in self.runq_depends[ids]:
            nam = os.path.basename(self.get_user_idstring(id))
            nam = re.sub("_[^,]*,", ",", nam)
            ret.extend([nam])
        return ret

    def get_user_idstring(self, task):
        fn = self.taskData.fn_index[self.runq_fnid[task]]
        taskname = self.runq_task[task]
        return "%s, %s" % (fn, taskname)

    def get_task_id(self, fnid, taskname):
        for listid in xrange(len(self.runq_fnid)):
            if self.runq_fnid[listid] == fnid and self.runq_task[listid] == taskname:
                return listid
        return None

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
            for entry in xrange(len(chain)):
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
            for index in xrange(len(chain1)):
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
                            msgs.append("  Task %s (%s) (dependent Tasks %s)\n" % (dep, self.get_user_idstring(dep), self.runq_depends_names(dep)))
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

        for listid in xrange(numTasks):
            task_done.append(False)
            weight.append(0)
            deps_left.append(len(self.runq_revdeps[listid]))

        for listid in endpoints:
            weight[listid] = 1
            task_done[listid] = True

        while True:
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
        for task in xrange(numTasks):
            if task_done[task] is False or deps_left[task] != 0:
                problem_tasks.append(task)
                logger.debug(2, "Task %s (%s) is not buildable\n", task, self.get_user_idstring(task))
                logger.debug(2, "(Complete marker was %s and the remaining dependency count was %s)\n\n", task_done[task], deps_left[task])

        if problem_tasks:
            message = "Unbuildable tasks were found.\n"
            message = message + "These are usually caused by circular dependencies and any circular dependency chains found will be printed below. Increase the debug level to see a list of unbuildable tasks.\n\n"
            message = message + "Identifying dependency loops (this may take a short while)...\n"
            logger.error(message)

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

        runq_build = []
        recursive_tdepends = {}
        runq_recrdepends = []
        tdepends_fnid = {}

        taskData = self.taskData

        if len(taskData.tasks_name) == 0:
            # Nothing to do
            return

        logger.info("Preparing runqueue")

        # Step A - Work out a list of tasks to run
        #
        # Taskdata gives us a list of possible providers for every build and run
        # target ordered by priority. It also gives information on each of those
        # providers.
        #
        # To create the actual list of tasks to execute we fix the list of
        # providers and then resolve the dependencies into task IDs. This
        # process is repeated for each type of dependency (tdepends, deptask,
        # rdeptast, recrdeptask, idepends).

        def add_build_dependencies(depids, tasknames, depends):
            for depid in depids:
                # Won't be in build_targets if ASSUME_PROVIDED
                if depid not in taskData.build_targets:
                    continue
                depdata = taskData.build_targets[depid][0]
                if depdata is None:
                    continue
                dep = taskData.fn_index[depdata]
                for taskname in tasknames:
                    taskid = taskData.gettask_id(dep, taskname, False)
                    if taskid is not None:
                        depends.append(taskid)

        def add_runtime_dependencies(depids, tasknames, depends):
            for depid in depids:
                if depid not in taskData.run_targets:
                    continue
                depdata = taskData.run_targets[depid][0]
                if depdata is None:
                    continue
                dep = taskData.fn_index[depdata]
                for taskname in tasknames:
                    taskid = taskData.gettask_id(dep, taskname, False)
                    if taskid is not None:
                        depends.append(taskid)

        for task in xrange(len(taskData.tasks_name)):
            depends = []
            recrdepends = []
            fnid = taskData.tasks_fnid[task]
            fn = taskData.fn_index[fnid]
            task_deps = self.dataCache.task_deps[fn]

            logger.debug(2, "Processing %s:%s", fn, taskData.tasks_name[task])

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
                    add_build_dependencies(taskData.depids[fnid], tasknames, depends)

                # Resolve 'rdeptask' dependencies
                #
                # e.g. do_sometask[rdeptask] = "do_someothertask"
                # (makes sure sometask runs after someothertask of all RDEPENDS)
                if 'rdeptask' in task_deps and taskData.tasks_name[task] in task_deps['rdeptask']:
                    taskname = task_deps['rdeptask'][taskData.tasks_name[task]]
                    add_runtime_dependencies(taskData.rdepids[fnid], [taskname], depends)

                # Resolve inter-task dependencies
                #
                # e.g. do_sometask[depends] = "targetname:do_someothertask"
                # (makes sure sometask runs after targetname's someothertask)
                if fnid not in tdepends_fnid:
                    tdepends_fnid[fnid] = set()
                idepends = taskData.tasks_idepends[task]
                for (depid, idependtask) in idepends:
                    if depid in taskData.build_targets:
                        # Won't be in build_targets if ASSUME_PROVIDED
                        depdata = taskData.build_targets[depid][0]
                        if depdata is not None:
                            dep = taskData.fn_index[depdata]
                            taskid = taskData.gettask_id(dep, idependtask, False)
                            if taskid is None:
                                bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s in %s depends upon nonexistant task %s in %s" % (taskData.tasks_name[task], fn, idependtask, dep))
                            depends.append(taskid)
                            if depdata != fnid:
                                tdepends_fnid[fnid].add(taskid)


                # Resolve recursive 'recrdeptask' dependencies (A)
                #
                # e.g. do_sometask[recrdeptask] = "do_someothertask"
                # (makes sure sometask runs after someothertask of all DEPENDS, RDEPENDS and intertask dependencies, recursively)
                # We cover the recursive part of the dependencies below
                if 'recrdeptask' in task_deps and taskData.tasks_name[task] in task_deps['recrdeptask']:
                    for taskname in task_deps['recrdeptask'][taskData.tasks_name[task]].split():
                        recrdepends.append(taskname)
                        add_build_dependencies(taskData.depids[fnid], [taskname], depends)
                        add_runtime_dependencies(taskData.rdepids[fnid], [taskname], depends)

                # Rmove all self references
                if task in depends:
                    newdep = []
                    logger.debug(2, "Task %s (%s %s) contains self reference! %s", task, taskData.fn_index[taskData.tasks_fnid[task]], taskData.tasks_name[task], depends)
                    for dep in depends:
                        if task != dep:
                            newdep.append(dep)
                    depends = newdep

            self.runq_fnid.append(taskData.tasks_fnid[task])
            self.runq_task.append(taskData.tasks_name[task])
            self.runq_depends.append(set(depends))
            self.runq_revdeps.append(set())

            runq_build.append(0)
            runq_recrdepends.append(recrdepends)

        #
        # Build a list of recursive cumulative dependencies for each fnid
        # We do this by fnid, since if A depends on some task in B
        # we're interested in later tasks B's fnid might have but B itself
        # doesn't depend on
        #
        # Algorithm is O(tasks) + O(tasks)*O(fnids)
        #
        reccumdepends = {}
        for task in xrange(len(self.runq_fnid)):
            fnid = self.runq_fnid[task]
            if fnid not in reccumdepends:
                if fnid in tdepends_fnid:
                    reccumdepends[fnid] = tdepends_fnid[fnid]
                else:
                    reccumdepends[fnid] = set()
            reccumdepends[fnid].update(self.runq_depends[task])
        for task in xrange(len(self.runq_fnid)):
            taskfnid = self.runq_fnid[task]
            for fnid in reccumdepends:
                if task in reccumdepends[fnid]:
                    reccumdepends[fnid].add(task)
                    if taskfnid in reccumdepends:
                        reccumdepends[fnid].update(reccumdepends[taskfnid])


        # Resolve recursive 'recrdeptask' dependencies (B)
        #
        # e.g. do_sometask[recrdeptask] = "do_someothertask"
        # (makes sure sometask runs after someothertask of all DEPENDS, RDEPENDS and intertask dependencies, recursively)
        for task in xrange(len(self.runq_fnid)):
            if len(runq_recrdepends[task]) > 0:
                taskfnid = self.runq_fnid[task]
                for dep in reccumdepends[taskfnid]:
                    # Ignore self references
                    if dep == task:
                        continue
                    for taskname in runq_recrdepends[task]:
                        if taskData.tasks_name[dep] == taskname:
                            self.runq_depends[task].add(dep)

        # Step B - Mark all active tasks
        #
        # Start with the tasks we were asked to run and mark all dependencies
        # as active too. If the task is to be 'forced', clear its stamp. Once
        # all active tasks are marked, prune the ones we don't need.

        logger.verbose("Marking Active Tasks")

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

        self.target_pairs = []
        for target in self.targets:
            targetid = taskData.getbuild_id(target[0])

            if targetid not in taskData.build_targets:
                continue

            if targetid in taskData.failed_deps:
                continue

            fnid = taskData.build_targets[targetid][0]
            fn = taskData.fn_index[fnid]
            self.target_pairs.append((fn, target[1]))

            # Remove stamps for targets if force mode active
            if self.cooker.configuration.force:
                logger.verbose("Remove stamp %s, %s", target[1], fn)
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
        for listid in xrange(len(self.runq_fnid)):
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
                bb.msg.fatal(bb.msg.domain.RunQueue, "All buildable tasks have been run but the build is incomplete (--continue mode). Errors for the tasks that failed will have been printed above.")
            else:
                bb.msg.fatal(bb.msg.domain.RunQueue, "No active tasks and not in --continue mode?! Please report this bug.")

        logger.verbose("Pruned %s inactive tasks, %s left", delcount, len(self.runq_fnid))

        # Remap the dependencies to account for the deleted tasks
        # Check we didn't delete a task we depend on
        for listid in xrange(len(self.runq_fnid)):
            newdeps = []
            origdeps = self.runq_depends[listid]
            for origdep in origdeps:
                if maps[origdep] == -1:
                    bb.msg.fatal(bb.msg.domain.RunQueue, "Invalid mapping - Should never happen!")
                newdeps.append(maps[origdep])
            self.runq_depends[listid] = set(newdeps)

        logger.verbose("Assign Weightings")

        # Generate a list of reverse dependencies to ease future calculations
        for listid in xrange(len(self.runq_fnid)):
            for dep in self.runq_depends[listid]:
                self.runq_revdeps[dep].add(listid)

        # Identify tasks at the end of dependency chains
        # Error on circular dependency loops (length two)
        endpoints = []
        for listid in xrange(len(self.runq_fnid)):
            revdeps = self.runq_revdeps[listid]
            if len(revdeps) == 0:
                endpoints.append(listid)
            for dep in revdeps:
                if dep in self.runq_depends[listid]:
                    #self.dump_data(taskData)
                    bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s (%s) has circular dependency on %s (%s)" % (taskData.fn_index[self.runq_fnid[dep]], self.runq_task[dep], taskData.fn_index[self.runq_fnid[listid]], self.runq_task[listid]))

        logger.verbose("Compute totals (have %s endpoint(s))", len(endpoints))

        # Calculate task weights
        # Check of higher length circular dependencies
        self.runq_weight = self.calculate_task_weights(endpoints)

        for scheduler in self.schedulers:
            if self.scheduler == scheduler.name:
                self.sched = scheduler(self)
                logger.debug(1, "Using runqueue scheduler '%s'", scheduler.name)
                break
        else:
            bb.fatal("Invalid scheduler '%s'.  Available schedulers: %s" %
                     (self.scheduler, ", ".join(obj.name for obj in self.schedulers)))

        # Sanity Check - Check for multiple tasks building the same provider
        prov_list = {}
        seen_fn = []
        for task in xrange(len(self.runq_fnid)):
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
                logger.error("Multiple .bb files are due to be built which each provide %s (%s).\n This usually means one provides something the other doesn't and should.", prov, " ".join(prov_list[prov]))


        # Create a whitelist usable by the stamp checks
        stampfnwhitelist = []
        for entry in self.stampwhitelist.split():
            entryid = self.taskData.getbuild_id(entry)
            if entryid not in self.taskData.build_targets:
                continue
            fnid = self.taskData.build_targets[entryid][0]
            fn = self.taskData.fn_index[fnid]
            stampfnwhitelist.append(fn)
        self.stampfnwhitelist = stampfnwhitelist

        #self.dump_data(taskData)

        self.state = runQueueRunInit

    def check_stamps(self):
        unchecked = {}
        current = []
        notcurrent = []
        buildable = []

        if self.stamppolicy == "perfile":
            fulldeptree = False
        else:
            fulldeptree = True
            stampwhitelist = []
            if self.stamppolicy == "whitelist":
                stampwhitelist = self.self.stampfnwhitelist

        for task in xrange(len(self.runq_fnid)):
            unchecked[task] = ""
            if len(self.runq_depends[task]) == 0:
                buildable.append(task)

        def check_buildable(self, task, buildable):
            for revdep in self.runq_revdeps[task]:
                alldeps = 1
                for dep in self.runq_depends[revdep]:
                    if dep in unchecked:
                        alldeps = 0
                if alldeps == 1:
                    if revdep in unchecked:
                        buildable.append(revdep)

        for task in xrange(len(self.runq_fnid)):
            if task not in unchecked:
                continue
            fn = self.taskData.fn_index[self.runq_fnid[task]]
            taskname = self.runq_task[task]
            stampfile = "%s.%s" % (self.dataCache.stamp[fn], taskname)
            # If the stamp is missing its not current
            if not os.access(stampfile, os.F_OK):
                del unchecked[task]
                notcurrent.append(task)
                check_buildable(self, task, buildable)
                continue
            # If its a 'nostamp' task, it's not current
            taskdep = self.dataCache.task_deps[fn]
            if 'nostamp' in taskdep and task in taskdep['nostamp']:
                del unchecked[task]
                notcurrent.append(task)
                check_buildable(self, task, buildable)
                continue

        while (len(buildable) > 0):
            nextbuildable = []
            for task in buildable:
                if task in unchecked:
                    fn = self.taskData.fn_index[self.runq_fnid[task]]
                    taskname = self.runq_task[task]
                    stampfile = "%s.%s" % (self.dataCache.stamp[fn], taskname)
                    iscurrent = True

                    t1 = os.stat(stampfile)[stat.ST_MTIME]
                    for dep in self.runq_depends[task]:
                        if iscurrent:
                            fn2 = self.taskData.fn_index[self.runq_fnid[dep]]
                            taskname2 = self.runq_task[dep]
                            stampfile2 = "%s.%s" % (self.dataCache.stamp[fn2], taskname2)
                            if fn == fn2 or (fulldeptree and fn2 not in stampwhitelist):
                                if dep in notcurrent:
                                    iscurrent = False
                                else:
                                    t2 = os.stat(stampfile2)[stat.ST_MTIME]
                                    if t1 < t2:
                                        iscurrent = False
                    del unchecked[task]
                    if iscurrent:
                        current.append(task)
                    else:
                        notcurrent.append(task)

                check_buildable(self, task, nextbuildable)

            buildable = nextbuildable

        #for task in range(len(self.runq_fnid)):
        #    fn = self.taskData.fn_index[self.runq_fnid[task]]
        #    taskname = self.runq_task[task]
        #    print "%s %s.%s" % (task, taskname, fn)

        #print "Unchecked: %s" % unchecked
        #print "Current: %s" % current
        #print "Not current: %s" % notcurrent

        if len(unchecked) > 0:
            bb.msg.fatal(bb.msg.domain.RunQueue, "check_stamps fatal internal error")
        return current

    def check_stamp_task(self, task, taskname = None):

        if self.stamppolicy == "perfile":
            fulldeptree = False
        else:
            fulldeptree = True
            stampwhitelist = []
            if self.stamppolicy == "whitelist":
                stampwhitelist = self.stampfnwhitelist

        fn = self.taskData.fn_index[self.runq_fnid[task]]
        if taskname is None:
            taskname = self.runq_task[task]
        stampfile = "%s.%s" % (self.dataCache.stamp[fn], taskname)
        # If the stamp is missing its not current
        if not os.access(stampfile, os.F_OK):
            logger.debug(2, "Stampfile %s not available\n", stampfile)
            return False
        # If its a 'nostamp' task, it's not current
        taskdep = self.dataCache.task_deps[fn]
        if 'nostamp' in taskdep and taskname in taskdep['nostamp']:
            logger.debug(2, "%s.%s is nostamp\n", fn, taskname)
            return False

        iscurrent = True
        t1 = os.stat(stampfile)[stat.ST_MTIME]
        for dep in self.runq_depends[task]:
            if iscurrent:
                fn2 = self.taskData.fn_index[self.runq_fnid[dep]]
                taskname2 = self.runq_task[dep]
                stampfile2 = "%s.%s" % (self.dataCache.stamp[fn2], taskname2)
                if fn == fn2 or (fulldeptree and fn2 not in stampwhitelist):
                    try:
                        t2 = os.stat(stampfile2)[stat.ST_MTIME]
                        if t1 < t2:
                            logger.debug(2, "Stampfile %s < %s", stampfile, stampfile2)
                            iscurrent = False
                    except:
                        logger.debug(2, "Exception reading %s for %s", stampfile2, stampfile)
                        iscurrent = False

        return iscurrent

    def execute_runqueue(self):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        Upon failure, optionally try to recover the build using any alternate providers
        (if the abort on failure configuration option isn't set)
        """

        retval = 0.5

        if self.state is runQueuePrepare:
            self.prepare_runqueue()

        if self.state is runQueueRunInit:
            logger.info("Executing runqueue")
            self.execute_runqueue_initVars()

        if self.state is runQueueRunning:
            self.execute_runqueue_internal()

        if self.state is runQueueCleanUp:
            self.finish_runqueue()

        if self.state is runQueueFailed:
            if not self.taskData.tryaltconfigs:
                raise bb.runqueue.TaskFailure(self.failed_fnids)
            for fnid in self.failed_fnids:
                self.taskData.fail_fnid(fnid)
            self.reset_runqueue()

        if self.state is runQueueComplete:
            # All done
            logger.info("Tasks Summary: Attempted %d tasks of which %d didn't need to be rerun and %d failed.", self.stats.completed, self.stats.skipped, self.stats.failed)
            return False

        if self.state is runQueueChildProcess:
            print("Child process, eeek, shouldn't happen!")
            return False

        # Loop
        return retval

    def execute_runqueue_initVars(self):

        self.stats = RunQueueStats(len(self.runq_fnid))

        self.runq_buildable = []
        self.runq_running = []
        self.runq_complete = []
        self.build_pids = {}
        self.build_pipes = {}
        self.failed_fnids = []

        # Mark initial buildable tasks
        for task in xrange(self.stats.total):
            self.runq_running.append(0)
            self.runq_complete.append(0)
            if len(self.runq_depends[task]) == 0:
                self.runq_buildable.append(1)
            else:
                self.runq_buildable.append(0)

        self.state = runQueueRunning

        event.fire(bb.event.StampUpdate(self.target_pairs, self.dataCache.stamp), self.cfgData)

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
                logger.debug(1, "Marking task %s (%s, %s) as buildable", revdep, fn, taskname)

    def task_fail(self, task, exitcode):
        """
        Called when a task has failed
        Updates the state engine with the failure
        """
        logger.error("Task %s (%s) failed with exit code '%s'", task,
                     self.get_user_idstring(task), exitcode)
        self.stats.taskFailed()
        fnid = self.runq_fnid[task]
        self.failed_fnids.append(fnid)
        bb.event.fire(runQueueTaskFailed(task, self.stats, self), self.cfgData)
        if self.taskData.abort:
            self.state = runQueueCleanUp

    def execute_runqueue_internal(self):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        """

        if self.stats.total == 0:
            # nothing to do
            self.state = runQueueCleanUp

        while True:
            for task in iter(self.sched.next, None):
                fn = self.taskData.fn_index[self.runq_fnid[task]]

                taskname = self.runq_task[task]
                if self.check_stamp_task(task, taskname):
                    logger.debug(2, "Stamp current task %s (%s)", task, self.get_user_idstring(task))
                    self.runq_running[task] = 1
                    self.runq_buildable[task] = 1
                    self.task_complete(task)
                    self.stats.taskCompleted()
                    self.stats.taskSkipped()
                    continue
                elif self.cooker.configuration.dry_run:
                    self.runq_running[task] = 1
                    self.runq_buildable[task] = 1
                    self.notify_task_started(task)
                    self.stats.taskActive()
                    self.task_complete(task)
                    self.stats.taskCompleted()
                    self.notify_task_completed(task)
                    continue

                pid, pipein, pipeout = self.fork_off_task(fn, task, taskname)

                self.build_pids[pid] = task
                self.build_pipes[pid] = runQueuePipe(pipein, pipeout, self.cfgData)
                self.runq_running[task] = 1
                self.stats.taskActive()

            for pipe in self.build_pipes:
                self.build_pipes[pipe].read()

            if self.stats.active > 0:
                if self.runqueue_process_waitpid(self.task_complete, self.task_fail) is None:
                    return
                continue

            if len(self.failed_fnids) != 0:
                self.state = runQueueFailed
                return

            # Sanity Checks
            for task in xrange(self.stats.total):
                if self.runq_buildable[task] == 0:
                    logger.error("Task %s never buildable!", task)
                if self.runq_running[task] == 0:
                    logger.error("Task %s never ran!", task)
                if self.runq_complete[task] == 0:
                    logger.error("Task %s never completed!", task)
            self.state = runQueueComplete
            return

    def runqueue_process_waitpid(self, success, failure):
        """
        Return none is there are no processes awaiting result collection, otherwise
        collect the process exit codes and close the information pipe.
        """
        result = os.waitpid(-1, os.WNOHANG)
        if result[0] is 0 and result[1] is 0:
            return None
        task = self.build_pids[result[0]]
        del self.build_pids[result[0]]
        self.build_pipes[result[0]].close()
        del self.build_pipes[result[0]]
        if result[1] != 0:
            failure(task, result[1]>>8)
        else:
            success(task)
            self.stats.taskCompleted()
            self.notify_task_completed(task)

    def finish_runqueue_now(self):
        if self.stats.active:
            logger.info("Sending SIGTERM to remaining %s tasks", self.stats.active)
            for k, v in self.build_pids.iteritems():
                try:
                    os.kill(-k, signal.SIGTERM)
                except:
                    pass
        for pipe in self.build_pipes:
            self.build_pipes[pipe].read()

    def finish_runqueue(self, now = False):
        self.state = runQueueCleanUp

        for pipe in self.build_pipes:
            self.build_pipes[pipe].read()

        if now:
            self.finish_runqueue_now()
        try:
            while self.stats.active > 0:
                bb.event.fire(runQueueExitWait(self.stats.active), self.cfgData)
                if self.runqueue_process_waitpid(self.task_complete, self.task_fail) is None:
                    return
        except:
            self.finish_runqueue_now()
            raise

        if len(self.failed_fnids) != 0:
            self.state = runQueueFailed
            return

        self.state = runQueueComplete
        return

    def notify_task_started(self, task):
        bb.event.fire(runQueueTaskStarted(task, self.stats, self), self.cfgData)
        logger.info("Running task %d of %d (ID: %s, %s)", self.stats.completed + self.stats.active + self.stats.failed + 1,
                                                          self.stats.total,
                                                          task,
                                                          self.get_user_idstring(task))

    def notify_task_completed(self, task):
        bb.event.fire(runQueueTaskCompleted(task, self.stats, self), self.cfgData)

    def fork_off_task(self, fn, task, taskname):
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            pipein, pipeout = os.pipe()
            pid = os.fork()
        except OSError as e:
            bb.msg.fatal(bb.msg.domain.RunQueue, "fork failed: %d (%s)" % (e.errno, e.strerror))
        if pid == 0:
            os.close(pipein)
            # Save out the PID so that the event can include it the
            # events
            bb.event.worker_pid = os.getpid()
            bb.event.worker_pipe = pipeout

            # Child processes should send their messages to the UI
            # process via the server process, not print them
            # themselves
            bblogger.handlers = [bb.event.LogHandler()]

            self.state = runQueueChildProcess
            # Make the child the process group leader
            os.setpgid(0, 0)
            # No stdin
            newsi = os.open('/dev/null', os.O_RDWR)
            os.dup2(newsi, sys.stdin.fileno())

            self.notify_task_started(task)

            bb.data.setVar("__RUNQUEUE_DO_NOT_USE_EXTERNALLY", self, self.cooker.configuration.data)
            bb.data.setVar("__RUNQUEUE_DO_NOT_USE_EXTERNALLY2", fn, self.cooker.configuration.data)
            try:
                the_data = bb.cache.Cache.loadDataFull(fn, self.cooker.get_file_appends(fn), self.cooker.configuration.data)
                bb.build.exec_task(fn, taskname, the_data)
            except Exception as exc:
                logger.critical(str(exc))
                os._exit(1)
            os._exit(0)
        return pid, pipein, pipeout


    def dump_data(self, taskQueue):
        """
        Dump some debug information on the internal data structures
        """
        logger.debug(3, "run_tasks:")
        for task in xrange(len(self.runq_task)):
            logger.debug(3, " (%s)%s - %s: %s   Deps %s RevDeps %s", task,
                       taskQueue.fn_index[self.runq_fnid[task]],
                       self.runq_task[task],
                       self.runq_weight[task],
                       self.runq_depends[task],
                       self.runq_revdeps[task])

        logger.debug(3, "sorted_tasks:")
        for task1 in xrange(len(self.runq_task)):
            if task1 in self.prio_map:
                task = self.prio_map[task1]
                logger.debug(3, " (%s)%s - %s: %s   Deps %s RevDeps %s", task,
                           taskQueue.fn_index[self.runq_fnid[task]],
                           self.runq_task[task],
                           self.runq_weight[task],
                           self.runq_depends[task],
                           self.runq_revdeps[task])


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

    def __init__(self, remain):
        self.remain = remain
        self.message = "Waiting for %s active tasks to finish" % remain
        bb.event.Event.__init__(self)

class runQueueEvent(bb.event.Event):
    """
    Base runQueue event class
    """
    def __init__(self, task, stats, rq):
        self.taskid = task
        self.taskstring = rq.get_user_idstring(task)
        self.stats = stats
        bb.event.Event.__init__(self)

class runQueueTaskStarted(runQueueEvent):
    """
    Event notifing a task was started
    """
    def __init__(self, task, stats, rq):
        runQueueEvent.__init__(self, task, stats, rq)
        self.message = "Running task %s (%d of %d) (%s)" % (task, stats.completed + stats.active + 1, self.stats.total, self.taskstring)

class runQueueTaskFailed(runQueueEvent):
    """
    Event notifing a task failed
    """
    def __init__(self, task, stats, rq):
        runQueueEvent.__init__(self, task, stats, rq)
        self.message = "Task %s failed (%s)" % (task, self.taskstring)

class runQueueTaskCompleted(runQueueEvent):
    """
    Event notifing a task completed
    """
    def __init__(self, task, stats, rq):
        runQueueEvent.__init__(self, task, stats, rq)
        self.message = "Task %s completed (%s)" % (task, self.taskstring)

def check_stamp_fn(fn, taskname, d):
    rq = bb.data.getVar("__RUNQUEUE_DO_NOT_USE_EXTERNALLY", d)
    fn = bb.data.getVar("__RUNQUEUE_DO_NOT_USE_EXTERNALLY2", d)
    fnid = rq.taskData.getfn_id(fn)
    taskid = rq.get_task_id(fnid, taskname)
    if taskid is not None:
        return rq.check_stamp_task(taskid)
    return None

class runQueuePipe():
    """
    Abstraction for a pipe between a worker thread and the server
    """
    def __init__(self, pipein, pipeout, d):
        self.fd = pipein
        os.close(pipeout)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, fcntl.fcntl(self.fd, fcntl.F_GETFL) | os.O_NONBLOCK)
        self.queue = ""
        self.d = d

    def read(self):
        start = len(self.queue)
        try:
            self.queue = self.queue + os.read(self.fd, 1024)
        except OSError:
            pass
        end = len(self.queue)
        index = self.queue.find("</event>")
        while index != -1:
            bb.event.fire_from_worker(self.queue[:index+8], self.d)
            self.queue = self.queue[index+8:]
            index = self.queue.find("</event>")
        return (end > start)

    def close(self):
        while self.read():
            continue
        if len(self.queue) > 0:
            print("Warning, worker left partial message")
        os.close(self.fd)
