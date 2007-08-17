#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'RunQueue' implementation

Handles preparation and execution of a queue of tasks
"""

# Copyright (C) 2006  Richard Purdie
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
    def __init__(self):
        self.completed = 0
        self.skipped = 0
        self.failed = 0

    def taskFailed(self):
        self.failed = self.failed + 1

    def taskCompleted(self):
        self.completed = self.completed + 1

    def taskSkipped(self):
        self.skipped = self.skipped + 1

class RunQueue:
    """
    BitBake Run Queue implementation
    """
    def __init__(self, cooker, cfgData, dataCache, taskData, targets):
        self.reset_runqueue()
        self.cooker = cooker
        self.dataCache = dataCache
        self.taskData = taskData
        self.targets = targets

        self.number_tasks = int(bb.data.getVar("BB_NUMBER_THREADS", cfgData) or 1)

    def reset_runqueue(self):

        self.runq_fnid = []
        self.runq_task = []
        self.runq_depends = []
        self.runq_revdeps = []
        self.runq_weight = []
        self.prio_map = []

    def get_user_idstring(self, task):
        fn = self.taskData.fn_index[self.runq_fnid[task]]
        taskname = self.runq_task[task]
        return "%s, %s" % (fn, taskname)

    def prepare_runqueue(self):
        """
        Turn a set of taskData into a RunQueue and compute data needed 
        to optimise the execution order.
        """

        depends = []
        runq_weight1 = []
        runq_build = []
        runq_done = []

        taskData = self.taskData

        if len(taskData.tasks_name) == 0:
            # Nothing to do
            return

        bb.msg.note(1, bb.msg.domain.RunQueue, "Preparing runqueue")

        for task in range(len(taskData.tasks_name)):
            fnid = taskData.tasks_fnid[task]
            fn = taskData.fn_index[fnid]
            task_deps = self.dataCache.task_deps[fn]

            if fnid not in taskData.failed_fnids:

                depends = taskData.tasks_tdepends[task]

                # Resolve Depends
                if 'deptask' in task_deps and taskData.tasks_name[task] in task_deps['deptask']:
                    taskname = task_deps['deptask'][taskData.tasks_name[task]]
                    for depid in taskData.depids[fnid]:
                        # Won't be in build_targets if ASSUME_PROVIDED
                        if depid in taskData.build_targets:
                            depdata = taskData.build_targets[depid][0]
                            if depdata is not None:
                                dep = taskData.fn_index[depdata]
                                depends.append(taskData.gettask_id(dep, taskname))

                # Resolve Runtime Depends
                if 'rdeptask' in task_deps and taskData.tasks_name[task] in task_deps['rdeptask']:
                    taskname = task_deps['rdeptask'][taskData.tasks_name[task]]
                    for depid in taskData.rdepids[fnid]:
                        if depid in taskData.run_targets:
                            depdata = taskData.run_targets[depid][0]
                            if depdata is not None:
                                dep = taskData.fn_index[depdata]
                                depends.append(taskData.gettask_id(dep, taskname))

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


                # Resolve Recursive Runtime Depends
                # Also includes all thier build depends, intertask depends and runtime depends
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

            listid = taskData.tasks_lookup[fnid][target[1]]

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
            if not taskData.abort:
                bb.msg.note(1, bb.msg.domain.RunQueue, "All possible tasks have been run but build incomplete (--continue mode). See errors above for incomplete tasks.")
                return
            bb.msg.fatal(bb.msg.domain.RunQueue, "No active tasks and not in --continue mode?! Please report this bug.")

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
                deps_seen = []
                def print_chain(taskid, finish):
                    seen.append(taskid)
                    for revdep in self.runq_revdeps[taskid]:
                        if runq_done[revdep] == 0 and revdep not in seen and not finish:
                            bb.msg.error(bb.msg.domain.RunQueue, "Task %s (%s) (depends: %s)" % (revdep, self.get_user_idstring(revdep), self.runq_depends[revdep]))
                            if revdep in deps_seen:
                                bb.msg.error(bb.msg.domain.RunQueue, "Chain ends at Task %s (%s)" % (revdep, self.get_user_idstring(revdep)))
                                finish = True
                                return
                            for dep in self.runq_depends[revdep]:
                                deps_seen.append(dep)
                            print_chain(revdep, finish)
                print_chain(task, False)
                bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s (%s) not processed!\nThis is probably a circular dependency (the chain might be printed above)." % (task, self.get_user_idstring(task)))
            if runq_weight1[task] != 0:
                bb.msg.fatal(bb.msg.domain.RunQueue, "Task %s (%s) count not zero!" % (task, self.get_user_idstring(task)))

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

        #self.dump_data(taskData)

    def execute_runqueue(self):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        Upon failure, optionally try to recover the build using any alternate providers
        (if the abort on failure configuration option isn't set)
        """

        failures = 0
        while 1:
            failed_fnids = []
            try:
                self.execute_runqueue_internal()
            finally:
                if self.master_process:
                    failed_fnids = self.finish_runqueue()
            if len(failed_fnids) == 0:
                return failures
            if self.taskData.abort:
                raise bb.runqueue.TaskFailure(failed_fnids)
            for fnid in failed_fnids:
                #print "Failure: %s %s %s" % (fnid, self.taskData.fn_index[fnid],  self.runq_task[fnid])
                self.taskData.fail_fnid(fnid)
                failures = failures + 1
            self.reset_runqueue()
            self.prepare_runqueue()

    def execute_runqueue_initVars(self):

        self.stats = RunQueueStats()

        self.active_builds = 0
        self.runq_buildable = []
        self.runq_running = []
        self.runq_complete = []
        self.build_pids = {}
        self.failed_fnids = []
        self.master_process = True

        # Mark initial buildable tasks
        for task in range(len(self.runq_fnid)):
            self.runq_running.append(0)
            self.runq_complete.append(0)
            if len(self.runq_depends[task]) == 0:
                self.runq_buildable.append(1)
            else:
                self.runq_buildable.append(0)

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

    def get_next_task(self):
        """
        Return the id of the highest priority task that is buildable
        """
        for task1 in range(len(self.runq_fnid)):
            task = self.prio_map[task1]
            if self.runq_running[task] == 1:
                continue
            if self.runq_buildable[task] == 1:
                return task
        return None

    def execute_runqueue_internal(self):
        """
        Run the tasks in a queue prepared by prepare_runqueue
        """

        bb.msg.note(1, bb.msg.domain.RunQueue, "Executing runqueue")

        self.execute_runqueue_initVars()

        if len(self.runq_fnid) == 0:
            # nothing to do
            return []

        def sigint_handler(signum, frame):
            raise KeyboardInterrupt

        # Find any tasks with current stamps and remove them from the queue
        for task1 in range(len(self.runq_fnid)):
            task = self.prio_map[task1]
            fn = self.taskData.fn_index[self.runq_fnid[task]]
            taskname = self.runq_task[task]
            if bb.build.stamp_is_current(taskname, self.dataCache, fn):
                bb.msg.debug(2, bb.msg.domain.RunQueue, "Stamp current task %s (%s)" % (task, self.get_user_idstring(task)))
                self.runq_running[task] = 1
                self.task_complete(task)
                self.stats.taskCompleted()
                self.stats.taskSkipped()

        while True:
            task = self.get_next_task()
            if task is not None:
                fn = self.taskData.fn_index[self.runq_fnid[task]]

                taskname = self.runq_task[task]
                if bb.build.stamp_is_current(taskname, self.dataCache, fn):
                    bb.msg.debug(2, bb.msg.domain.RunQueue, "Stamp current task %s (%s)" % (task, self.get_user_idstring(task)))
                    self.runq_running[task] = 1
                    self.task_complete(task)
                    self.stats.taskCompleted()
                    self.stats.taskSkipped()
                    continue

                bb.msg.note(1, bb.msg.domain.RunQueue, "Running task %d of %d (ID: %s, %s)" % (self.stats.completed + self.active_builds + 1, len(self.runq_fnid), task, self.get_user_idstring(task)))
                try: 
                    pid = os.fork() 
                except OSError, e: 
                    bb.msg.fatal(bb.msg.domain.RunQueue, "fork failed: %d (%s)" % (e.errno, e.strerror))
                if pid == 0:
                    # Bypass master process' handling
                    self.master_process = False
                    # Stop Ctrl+C being sent to children
                    # signal.signal(signal.SIGINT, signal.SIG_IGN)
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
                self.active_builds = self.active_builds + 1
                if self.active_builds < self.number_tasks:
                    continue
            if self.active_builds > 0:
                result = os.waitpid(-1, 0)
                self.active_builds = self.active_builds - 1
                task = self.build_pids[result[0]]
                if result[1] != 0:
                    del self.build_pids[result[0]]
                    bb.msg.error(bb.msg.domain.RunQueue, "Task %s (%s) failed" % (task, self.get_user_idstring(task)))
                    self.failed_fnids.append(self.runq_fnid[task])
                    self.stats.taskFailed()
                    break
                self.task_complete(task)
                self.stats.taskCompleted()
                del self.build_pids[result[0]]
                continue
            return

    def finish_runqueue(self):
        try:
            while self.active_builds > 0:
                bb.msg.note(1, bb.msg.domain.RunQueue, "Waiting for %s active tasks to finish" % self.active_builds)
                tasknum = 1
                for k, v in self.build_pids.iteritems():
                     bb.msg.note(1, bb.msg.domain.RunQueue, "%s: %s (%s)" % (tasknum, self.get_user_idstring(v), k))
                     tasknum = tasknum + 1
                result = os.waitpid(-1, 0)
                task = self.build_pids[result[0]]
                if result[1] != 0:
                     bb.msg.error(bb.msg.domain.RunQueue, "Task %s (%s) failed" % (task, self.get_user_idstring(task)))
                     self.failed_fnids.append(self.runq_fnid[task])
                     self.stats.taskFailed()
                del self.build_pids[result[0]]
                self.active_builds = self.active_builds - 1
            bb.msg.note(1, bb.msg.domain.RunQueue, "Tasks Summary: Attempted %d tasks of which %d didn't need to be rerun and %d failed." % (self.stats.completed, self.stats.skipped, self.stats.failed))
            return self.failed_fnids
        except KeyboardInterrupt:
            bb.msg.note(1, bb.msg.domain.RunQueue, "Sending SIGINT to remaining %s tasks" % self.active_builds)
            for k, v in self.build_pids.iteritems():
                 try:
                     os.kill(-k, signal.SIGINT)
                 except:
                     pass
            raise

        # Sanity Checks
        for task in range(len(self.runq_fnid)):
            if self.runq_buildable[task] == 0:
                bb.msg.error(bb.msg.domain.RunQueue, "Task %s never buildable!" % task)
            if self.runq_running[task] == 0:
                bb.msg.error(bb.msg.domain.RunQueue, "Task %s never ran!" % task)
            if self.runq_complete[task] == 0:
                bb.msg.error(bb.msg.domain.RunQueue, "Task %s never completed!" % task)

        bb.msg.note(1, bb.msg.domain.RunQueue, "Tasks Summary: Attempted %d tasks of which %d didn't need to be rerun and %d failed." % (self.stats.completed, self.stats.skipped, self.stats.failed))

        return self.failed_fnids

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
