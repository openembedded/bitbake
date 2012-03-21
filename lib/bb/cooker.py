#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2003 - 2005 Michael 'Mickey' Lauer
# Copyright (C) 2005        Holger Hans Peter Freyther
# Copyright (C) 2005        ROAD GmbH
# Copyright (C) 2006 - 2007 Richard Purdie
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

from __future__ import print_function
import sys, os, glob, os.path, re, time
import atexit
import itertools
import logging
import multiprocessing
import sre_constants
import threading
from cStringIO import StringIO
from contextlib import closing
from functools import wraps
from collections import defaultdict
import bb, bb.exceptions, bb.command
from bb import utils, data, parse, event, cache, providers, taskdata, runqueue
import Queue
import prserv.serv

logger      = logging.getLogger("BitBake")
collectlog  = logging.getLogger("BitBake.Collection")
buildlog    = logging.getLogger("BitBake.Build")
parselog    = logging.getLogger("BitBake.Parsing")
providerlog = logging.getLogger("BitBake.Provider")

class NoSpecificMatch(bb.BBHandledException):
    """
    Exception raised when no or multiple file matches are found
    """

class NothingToBuild(Exception):
    """
    Exception raised when there is nothing to build
    """

class CollectionError(bb.BBHandledException):
    """
    Exception raised when layer configuration is incorrect
    """

class state:
    initial, parsing, running, shutdown, stop = range(5)


class SkippedPackage:
    def __init__(self, info = None, reason = None):
        self.pn = None
        self.skipreason = None
        self.provides = None
        self.rprovides = None

        if info:
            self.pn = info.pn
            self.skipreason = info.skipreason
            self.provides = info.provides
            self.rprovides = info.rprovides
        elif reason:
            self.skipreason = reason

#============================================================================#
# BBCooker
#============================================================================#
class BBCooker:
    """
    Manages one bitbake build run
    """

    def __init__(self, configuration, server_registration_cb, savedenv={}):
        self.status = None
        self.appendlist = {}
        self.skiplist = {}

        self.server_registration_cb = server_registration_cb

        self.configuration = configuration

        # Keep a datastore of the initial environment variables and their
        # values from when BitBake was launched to enable child processes
        # to use environment variables which have been cleaned from the
        # BitBake processes env
        self.savedenv = bb.data.init()
        for k in savedenv:
            self.savedenv.setVar(k, savedenv[k])

        self.caches_array = []
        # Currently, only Image Creator hob ui needs extra cache.
        # So, we save Extra Cache class name and container file
        # information into a extraCaches field in hob UI.  
        # TODO: In future, bin/bitbake should pass information into cooker,
        # instead of getting information from configuration.ui. Also, some
        # UI start up issues need to be addressed at the same time.
        caches_name_array = ['bb.cache:CoreRecipeInfo']
        if configuration.ui:
            try:
                module = __import__('bb.ui', fromlist=[configuration.ui])
                name_array = (getattr(module, configuration.ui)).extraCaches
                for recipeInfoName in name_array:
                    caches_name_array.append(recipeInfoName)
            except ImportError as exc:
                # bb.ui.XXX is not defined and imported. It's an error!
                logger.critical("Unable to import '%s' interface from bb.ui: %s" % (configuration.ui, exc))
                sys.exit("FATAL: Failed to import '%s' interface." % configuration.ui)
            except AttributeError:
                # This is not an error. If the field is not defined in the ui,
                # this interface might need no extra cache fields, so
                # just skip this error!
                logger.debug(2, "UI '%s' does not require extra cache!" % (configuration.ui))

        # At least CoreRecipeInfo will be loaded, so caches_array will never be empty!
        # This is the entry point, no further check needed!
        for var in caches_name_array:
            try:
                module_name, cache_name = var.split(':')
                module = __import__(module_name, fromlist=(cache_name,))
                self.caches_array.append(getattr(module, cache_name)) 
            except ImportError as exc:
                logger.critical("Unable to import extra RecipeInfo '%s' from '%s': %s" % (cache_name, module_name, exc))
                sys.exit("FATAL: Failed to import extra cache class '%s'." % cache_name)

        self.configuration.data = None
        self.loadConfigurationData()

        # Take a lock so only one copy of bitbake can run against a given build
        # directory at a time
        lockfile = self.configuration.data.expand("${TOPDIR}/bitbake.lock")
        self.lock = bb.utils.lockfile(lockfile, False, False)
        if not self.lock:
            bb.fatal("Only one copy of bitbake should be run against a build directory")

        bbpkgs = self.configuration.data.getVar('BBPKGS', True)
        if bbpkgs and len(self.configuration.pkgs_to_build) == 0:
            self.configuration.pkgs_to_build.extend(bbpkgs.split())

        #
        # Special updated configuration we use for firing events
        #
        self.configuration.event_data = bb.data.createCopy(self.configuration.data)
        bb.data.update_data(self.configuration.event_data)

        # TOSTOP must not be set or our children will hang when they output
        fd = sys.stdout.fileno()
        if os.isatty(fd):
            import termios
            tcattr = termios.tcgetattr(fd)
            if tcattr[3] & termios.TOSTOP:
                buildlog.info("The terminal had the TOSTOP bit set, clearing...")
                tcattr[3] = tcattr[3] & ~termios.TOSTOP
                termios.tcsetattr(fd, termios.TCSANOW, tcattr)

        self.command = bb.command.Command(self)
        self.state = state.initial

        self.parser = None

    def initConfigurationData(self):
        self.configuration.data = bb.data.init()

        if not self.server_registration_cb:
            self.configuration.data.setVar("BB_WORKERCONTEXT", "1")

        filtered_keys = bb.utils.approved_variables()
        bb.data.inheritFromOS(self.configuration.data, self.savedenv, filtered_keys)

    def loadConfigurationData(self):
        self.configuration.data = bb.data.init()

        if not self.server_registration_cb:
            self.configuration.data.setVar("BB_WORKERCONTEXT", "1")

        filtered_keys = bb.utils.approved_variables()
        bb.data.inheritFromOS(self.configuration.data, self.savedenv, filtered_keys)

        try:
            self.parseConfigurationFiles(self.configuration.prefile,
                                         self.configuration.postfile)
        except SyntaxError:
            sys.exit(1)
        except Exception:
            logger.exception("Error parsing configuration files")
            sys.exit(1)

        if not self.configuration.cmd:
            self.configuration.cmd = self.configuration.data.getVar("BB_DEFAULT_TASK", True) or "build"

    def parseConfiguration(self):

        # Set log file verbosity
        verboselogs = bb.utils.to_boolean(self.configuration.data.getVar("BB_VERBOSE_LOGS", "0"))
        if verboselogs:
            bb.msg.loggerVerboseLogs = True

        # Change nice level if we're asked to
        nice = self.configuration.data.getVar("BB_NICE_LEVEL", True)
        if nice:
            curnice = os.nice(0)
            nice = int(nice) - curnice
            buildlog.verbose("Renice to %s " % os.nice(nice))

    def parseCommandLine(self):
        # Parse any commandline into actions
        self.commandlineAction = {'action':None, 'msg':None}
        if self.configuration.show_environment:
            if 'world' in self.configuration.pkgs_to_build:
                self.commandlineAction['msg'] = "'world' is not a valid target for --environment."
            elif 'universe' in self.configuration.pkgs_to_build:
                self.commandlineAction['msg'] = "'universe' is not a valid target for --environment."
            elif len(self.configuration.pkgs_to_build) > 1:
                self.commandlineAction['msg'] = "Only one target can be used with the --environment option."
            elif self.configuration.buildfile and len(self.configuration.pkgs_to_build) > 0:
                self.commandlineAction['msg'] = "No target should be used with the --environment and --buildfile options."
            elif len(self.configuration.pkgs_to_build) > 0:
                self.commandlineAction['action'] = ["showEnvironmentTarget", self.configuration.pkgs_to_build]
            else:
                self.commandlineAction['action'] = ["showEnvironment", self.configuration.buildfile]
        elif self.configuration.buildfile is not None:
            self.commandlineAction['action'] = ["buildFile", self.configuration.buildfile, self.configuration.cmd]
        elif self.configuration.revisions_changed:
            self.commandlineAction['action'] = ["compareRevisions"]
        elif self.configuration.show_versions:
            self.commandlineAction['action'] = ["showVersions"]
        elif self.configuration.parse_only:
            self.commandlineAction['action'] = ["parseFiles"]
        elif self.configuration.dot_graph:
            if self.configuration.pkgs_to_build:
                self.commandlineAction['action'] = ["generateDotGraph", self.configuration.pkgs_to_build, self.configuration.cmd]
            else:
                self.commandlineAction['msg'] = "Please specify a package name for dependency graph generation."
        else:
            if self.configuration.pkgs_to_build:
                self.commandlineAction['action'] = ["buildTargets", self.configuration.pkgs_to_build, self.configuration.cmd]
            else:
                #self.commandlineAction['msg'] = "Nothing to do.  Use 'bitbake world' to build everything, or run 'bitbake --help' for usage information."
                self.commandlineAction = None

    def runCommands(self, server, data, abort):
        """
        Run any queued asynchronous command
        This is done by the idle handler so it runs in true context rather than
        tied to any UI.
        """

        return self.command.runAsyncCommand()

    def showVersions(self):

        # Need files parsed
        self.updateCache()

        pkg_pn = self.status.pkg_pn
        (latest_versions, preferred_versions) = bb.providers.findProviders(self.configuration.data, self.status, pkg_pn)

        logger.plain("%-35s %25s %25s", "Package Name", "Latest Version", "Preferred Version")
        logger.plain("%-35s %25s %25s\n", "============", "==============", "=================")

        for p in sorted(pkg_pn):
            pref = preferred_versions[p]
            latest = latest_versions[p]

            prefstr = pref[0][0] + ":" + pref[0][1] + '-' + pref[0][2]
            lateststr = latest[0][0] + ":" + latest[0][1] + "-" + latest[0][2]

            if pref == latest:
                prefstr = ""

            logger.plain("%-35s %25s %25s", p, lateststr, prefstr)

    def showEnvironment(self, buildfile = None, pkgs_to_build = []):
        """
        Show the outer or per-package environment
        """
        fn = None
        envdata = None

        if buildfile:
            # Parse the configuration here. We need to do it explicitly here since
            # this showEnvironment() code path doesn't use the cache
            self.parseConfiguration()
            self.status = bb.cache.CacheData(self.caches_array)
            self.handleCollections( self.configuration.data.getVar("BBFILE_COLLECTIONS", True) )

            fn, cls = bb.cache.Cache.virtualfn2realfn(buildfile)
            fn = self.matchFile(fn)
            fn = bb.cache.Cache.realfn2virtual(fn, cls)
        elif len(pkgs_to_build) == 1:
            self.updateCache()

            localdata = data.createCopy(self.configuration.data)
            bb.data.update_data(localdata)
            bb.data.expandKeys(localdata)

            taskdata = bb.taskdata.TaskData(self.configuration.abort)
            taskdata.add_provider(localdata, self.status, pkgs_to_build[0])
            taskdata.add_unresolved(localdata, self.status)

            targetid = taskdata.getbuild_id(pkgs_to_build[0])
            fnid = taskdata.build_targets[targetid][0]
            fn = taskdata.fn_index[fnid]
        else:
            envdata = self.configuration.data

        if fn:
            try:
                envdata = bb.cache.Cache.loadDataFull(fn, self.get_file_appends(fn), self.configuration.data)
            except Exception as e:
                parselog.exception("Unable to read %s", fn)
                raise

        # emit variables and shell functions
        data.update_data(envdata)
        with closing(StringIO()) as env:
            data.emit_env(env, envdata, True)
            logger.plain(env.getvalue())

        # emit the metadata which isnt valid shell
        data.expandKeys(envdata)
        for e in envdata.keys():
            if data.getVarFlag( e, 'python', envdata ):
                logger.plain("\npython %s () {\n%s}\n", e, data.getVar(e, envdata, 1))

    def prepareTreeData(self, pkgs_to_build, task):
        """
        Prepare a runqueue and taskdata object for iteration over pkgs_to_build
        """
        bb.event.fire(bb.event.TreeDataPreparationStarted(), self.configuration.data)
        # Need files parsed
        self.updateCache()
        # If we are told to do the None task then query the default task
        if (task == None):
            task = self.configuration.cmd

        pkgs_to_build = self.checkPackages(pkgs_to_build)

        localdata = data.createCopy(self.configuration.data)
        bb.data.update_data(localdata)
        bb.data.expandKeys(localdata)
        # We set abort to False here to prevent unbuildable targets raising
        # an exception when we're just generating data
        taskdata = bb.taskdata.TaskData(False, skiplist=self.skiplist)

        runlist = []
        current = 0
        for k in pkgs_to_build:
            taskdata.add_provider(localdata, self.status, k)
            runlist.append([k, "do_%s" % task])
            current += 1
            bb.event.fire(bb.event.TreeDataPreparationProgress(current, len(pkgs_to_build)), self.configuration.data)
        taskdata.add_unresolved(localdata, self.status)
        bb.event.fire(bb.event.TreeDataPreparationCompleted(len(pkgs_to_build)), self.configuration.data)
        return runlist, taskdata

    def generateTaskDepTreeData(self, pkgs_to_build, task):
        """
        Create a dependency graph of pkgs_to_build including reverse dependency
        information.
        """
        runlist, taskdata = self.prepareTreeData(pkgs_to_build, task)
        rq = bb.runqueue.RunQueue(self, self.configuration.data, self.status, taskdata, runlist)
        rq.rqdata.prepare()

        seen_fnids = []
        depend_tree = {}
        depend_tree["depends"] = {}
        depend_tree["tdepends"] = {}
        depend_tree["pn"] = {}
        depend_tree["rdepends-pn"] = {}
        depend_tree["packages"] = {}
        depend_tree["rdepends-pkg"] = {}
        depend_tree["rrecs-pkg"] = {}

        for task in xrange(len(rq.rqdata.runq_fnid)):
            taskname = rq.rqdata.runq_task[task]
            fnid = rq.rqdata.runq_fnid[task]
            fn = taskdata.fn_index[fnid]
            pn = self.status.pkg_fn[fn]
            version  = "%s:%s-%s" % self.status.pkg_pepvpr[fn]
            if pn not in depend_tree["pn"]:
                depend_tree["pn"][pn] = {}
                depend_tree["pn"][pn]["filename"] = fn
                depend_tree["pn"][pn]["version"] = version
            for dep in rq.rqdata.runq_depends[task]:
                depfn = taskdata.fn_index[rq.rqdata.runq_fnid[dep]]
                deppn = self.status.pkg_fn[depfn]
                dotname = "%s.%s" % (pn, rq.rqdata.runq_task[task])
                if not dotname in depend_tree["tdepends"]:
                    depend_tree["tdepends"][dotname] = []
                depend_tree["tdepends"][dotname].append("%s.%s" % (deppn, rq.rqdata.runq_task[dep]))
            if fnid not in seen_fnids:
                seen_fnids.append(fnid)
                packages = []

                depend_tree["depends"][pn] = []
                for dep in taskdata.depids[fnid]:
                    depend_tree["depends"][pn].append(taskdata.build_names_index[dep])

                depend_tree["rdepends-pn"][pn] = []
                for rdep in taskdata.rdepids[fnid]:
                    depend_tree["rdepends-pn"][pn].append(taskdata.run_names_index[rdep])

                rdepends = self.status.rundeps[fn]
                for package in rdepends:
                    depend_tree["rdepends-pkg"][package] = []
                    for rdepend in rdepends[package]:
                        depend_tree["rdepends-pkg"][package].append(rdepend)
                    packages.append(package)

                rrecs = self.status.runrecs[fn]
                for package in rrecs:
                    depend_tree["rrecs-pkg"][package] = []
                    for rdepend in rrecs[package]:
                        depend_tree["rrecs-pkg"][package].append(rdepend)
                    if not package in packages:
                        packages.append(package)

                for package in packages:
                    if package not in depend_tree["packages"]:
                        depend_tree["packages"][package] = {}
                        depend_tree["packages"][package]["pn"] = pn
                        depend_tree["packages"][package]["filename"] = fn
                        depend_tree["packages"][package]["version"] = version

        return depend_tree

    def generatePkgDepTreeData(self, pkgs_to_build, task):
        """
        Create a dependency tree of pkgs_to_build, returning the data.
        """
        _, taskdata = self.prepareTreeData(pkgs_to_build, task)
        tasks_fnid = []
        if len(taskdata.tasks_name) != 0:
            for task in xrange(len(taskdata.tasks_name)):
                tasks_fnid.append(taskdata.tasks_fnid[task])

        seen_fnids = []
        depend_tree = {}
        depend_tree["depends"] = {}
        depend_tree["pn"] = {}
        depend_tree["rdepends-pn"] = {}
        depend_tree["rdepends-pkg"] = {}
        depend_tree["rrecs-pkg"] = {}

        for task in xrange(len(tasks_fnid)):
            fnid = tasks_fnid[task]
            fn = taskdata.fn_index[fnid]
            pn = self.status.pkg_fn[fn]
            version  = "%s:%s-%s" % self.status.pkg_pepvpr[fn]
            summary = self.status.summary[fn]
            lic = self.status.license[fn]
            section = self.status.section[fn]
            description = self.status.description[fn]
            rdepends = self.status.rundeps[fn]
            rrecs = self.status.runrecs[fn]
            inherits = self.status.inherits.get(fn, None)
            if pn not in depend_tree["pn"]:
                depend_tree["pn"][pn] = {}
                depend_tree["pn"][pn]["filename"] = fn
                depend_tree["pn"][pn]["version"] = version
                depend_tree["pn"][pn]["summary"] = summary
                depend_tree["pn"][pn]["license"] = lic
                depend_tree["pn"][pn]["section"] = section
                depend_tree["pn"][pn]["description"] = description
                depend_tree["pn"][pn]["inherits"] = inherits

            if fnid not in seen_fnids:
                seen_fnids.append(fnid)

                depend_tree["depends"][pn] = []
                for dep in taskdata.depids[fnid]:
                    item = taskdata.build_names_index[dep]
                    pn_provider = ""
                    targetid = taskdata.getbuild_id(item)
                    if targetid in taskdata.build_targets and taskdata.build_targets[targetid]:
                        id = taskdata.build_targets[targetid][0]
                        fn_provider = taskdata.fn_index[id]
                        pn_provider = self.status.pkg_fn[fn_provider]
                    else:
                        pn_provider = item
                    depend_tree["depends"][pn].append(pn_provider)

                depend_tree["rdepends-pn"][pn] = []
                for rdep in taskdata.rdepids[fnid]:
                    item = taskdata.run_names_index[rdep]
                    pn_rprovider = ""
                    targetid = taskdata.getrun_id(item)
                    if targetid in taskdata.run_targets and taskdata.run_targets[targetid]:
                        id = taskdata.run_targets[targetid][0]
                        fn_rprovider = taskdata.fn_index[id]
                        pn_rprovider = self.status.pkg_fn[fn_rprovider]
                    else:
                        pn_rprovider = item
                    depend_tree["rdepends-pn"][pn].append(pn_rprovider)

                depend_tree["rdepends-pkg"].update(rdepends)
                depend_tree["rrecs-pkg"].update(rrecs)

        return depend_tree

    def generateDepTreeEvent(self, pkgs_to_build, task):
        """
        Create a task dependency graph of pkgs_to_build.
        Generate an event with the result
        """
        depgraph = self.generateTaskDepTreeData(pkgs_to_build, task)
        bb.event.fire(bb.event.DepTreeGenerated(depgraph), self.configuration.data)

    def generateDotGraphFiles(self, pkgs_to_build, task):
        """
        Create a task dependency graph of pkgs_to_build.
        Save the result to a set of .dot files.
        """

        depgraph = self.generateTaskDepTreeData(pkgs_to_build, task)

        # Prints a flattened form of package-depends below where subpackages of a package are merged into the main pn
        depends_file = file('pn-depends.dot', 'w' )
        print("digraph depends {", file=depends_file)
        for pn in depgraph["pn"]:
            fn = depgraph["pn"][pn]["filename"]
            version = depgraph["pn"][pn]["version"]
            print('"%s" [label="%s %s\\n%s"]' % (pn, pn, version, fn), file=depends_file)
        for pn in depgraph["depends"]:
            for depend in depgraph["depends"][pn]:
                print('"%s" -> "%s"' % (pn, depend), file=depends_file)
        for pn in depgraph["rdepends-pn"]:
            for rdepend in depgraph["rdepends-pn"][pn]:
                print('"%s" -> "%s" [style=dashed]' % (pn, rdepend), file=depends_file)
        print("}", file=depends_file)
        logger.info("PN dependencies saved to 'pn-depends.dot'")

        depends_file = file('package-depends.dot', 'w' )
        print("digraph depends {", file=depends_file)
        for package in depgraph["packages"]:
            pn = depgraph["packages"][package]["pn"]
            fn = depgraph["packages"][package]["filename"]
            version = depgraph["packages"][package]["version"]
            if package == pn:
                print('"%s" [label="%s %s\\n%s"]' % (pn, pn, version, fn), file=depends_file)
            else:
                print('"%s" [label="%s(%s) %s\\n%s"]' % (package, package, pn, version, fn), file=depends_file)
            for depend in depgraph["depends"][pn]:
                print('"%s" -> "%s"' % (package, depend), file=depends_file)
        for package in depgraph["rdepends-pkg"]:
            for rdepend in depgraph["rdepends-pkg"][package]:
                print('"%s" -> "%s" [style=dashed]' % (package, rdepend), file=depends_file)
        for package in depgraph["rrecs-pkg"]:
            for rdepend in depgraph["rrecs-pkg"][package]:
                print('"%s" -> "%s" [style=dashed]' % (package, rdepend), file=depends_file)
        print("}", file=depends_file)
        logger.info("Package dependencies saved to 'package-depends.dot'")

        tdepends_file = file('task-depends.dot', 'w' )
        print("digraph depends {", file=tdepends_file)
        for task in depgraph["tdepends"]:
            (pn, taskname) = task.rsplit(".", 1)
            fn = depgraph["pn"][pn]["filename"]
            version = depgraph["pn"][pn]["version"]
            print('"%s.%s" [label="%s %s\\n%s\\n%s"]' % (pn, taskname, pn, taskname, version, fn), file=tdepends_file)
            for dep in depgraph["tdepends"][task]:
                print('"%s" -> "%s"' % (task, dep), file=tdepends_file)
        print("}", file=tdepends_file)
        logger.info("Task dependencies saved to 'task-depends.dot'")

    def calc_bbfile_priority( self, filename, matched = None ):
        for _, _, regex, pri in self.status.bbfile_config_priorities:
            if regex.match(filename):
                if matched != None:
                    if not regex in matched:
                        matched.add(regex)
                return pri
        return 0

    def show_appends_with_no_recipes( self ):
        recipes = set(os.path.basename(f)
                      for f in self.status.pkg_fn.iterkeys())
        recipes |= set(os.path.basename(f)
                      for f in self.skiplist.iterkeys())
        appended_recipes = self.appendlist.iterkeys()
        appends_without_recipes = [self.appendlist[recipe]
                                   for recipe in appended_recipes
                                   if recipe not in recipes]
        if appends_without_recipes:
            appendlines = ('  %s' % append
                           for appends in appends_without_recipes
                           for append in appends)
            msg = 'No recipes available for:\n%s' % '\n'.join(appendlines)
            warn_only = data.getVar("BB_DANGLINGAPPENDS_WARNONLY", \
                 self.configuration.data, False) or "no"
            if warn_only.lower() in ("1", "yes", "true"):
                bb.warn(msg)
            else:
                bb.fatal(msg)

    def buildDepgraph( self ):
        all_depends = self.status.all_depends
        pn_provides = self.status.pn_provides

        localdata = data.createCopy(self.configuration.data)
        bb.data.update_data(localdata)
        bb.data.expandKeys(localdata)

        # Handle PREFERRED_PROVIDERS
        for p in (localdata.getVar('PREFERRED_PROVIDERS', True) or "").split():
            try:
                (providee, provider) = p.split(':')
            except:
                providerlog.critical("Malformed option in PREFERRED_PROVIDERS variable: %s" % p)
                continue
            if providee in self.status.preferred and self.status.preferred[providee] != provider:
                providerlog.error("conflicting preferences for %s: both %s and %s specified", providee, provider, self.status.preferred[providee])
            self.status.preferred[providee] = provider

        # Calculate priorities for each file
        matched = set()
        for p in self.status.pkg_fn:
            self.status.bbfile_priority[p] = self.calc_bbfile_priority(p, matched)
 
        # Don't show the warning if the BBFILE_PATTERN did match .bbappend files
        unmatched = set()
        for _, _, regex, pri in self.status.bbfile_config_priorities:        
            if not regex in matched:
                unmatched.add(regex)

        def findmatch(regex):
            for bbfile in self.appendlist:
                for append in self.appendlist[bbfile]:
                    if regex.match(append):
                        return True
            return False

        for unmatch in unmatched.copy():
            if findmatch(unmatch):
                unmatched.remove(unmatch)

        for collection, pattern, regex, _ in self.status.bbfile_config_priorities:
            if regex in unmatched:
                collectlog.warn("No bb files matched BBFILE_PATTERN_%s '%s'" % (collection, pattern))

    def findCoreBaseFiles(self, subdir, configfile):
        corebase = self.configuration.data.getVar('COREBASE', True) or ""
        paths = []
        for root, dirs, files in os.walk(corebase + '/' + subdir):
            for d in dirs:
                configfilepath = os.path.join(root, d, configfile)
                if os.path.exists(configfilepath):
                    paths.append(os.path.join(root, d))

        if paths:
            bb.event.fire(bb.event.CoreBaseFilesFound(paths), self.configuration.data)

    def findConfigFilePath(self, configfile):
        """
        Find the location on disk of configfile and if it exists and was parsed by BitBake
        emit the ConfigFilePathFound event with the path to the file.
        """
        path = self._findConfigFile(configfile)
        if not path:
            return

        # Generate a list of parsed configuration files by searching the files
        # listed in the __depends and __base_depends variables with a .conf suffix.
        conffiles = []
        dep_files = self.configuration.data.getVar('__depends') or set()
        dep_files.union(self.configuration.data.getVar('__base_depends') or set())

        for f in dep_files:
            if f[0].endswith(".conf"):
                conffiles.append(f[0])

        _, conf, conffile = path.rpartition("conf/")
        match = os.path.join(conf, conffile)
        # Try and find matches for conf/conffilename.conf as we don't always
        # have the full path to the file.
        for cfg in conffiles:
            if cfg.endswith(match):
                bb.event.fire(bb.event.ConfigFilePathFound(path),
                              self.configuration.data)
                break

    def findFilesMatchingInDir(self, filepattern, directory):
        """
        Searches for files matching the regex 'pattern' which are children of
        'directory' in each BBPATH. i.e. to find all rootfs package classes available
        to BitBake one could call findFilesMatchingInDir(self, 'rootfs_', 'classes')
        or to find all machine configuration files one could call:
        findFilesMatchingInDir(self, 'conf/machines', 'conf')
        """
        import re

        matches = []
        p = re.compile(re.escape(filepattern))
        bbpaths = self.configuration.data.getVar('BBPATH', True).split(':')
        for path in bbpaths:
            dirpath = os.path.join(path, directory)
            if os.path.exists(dirpath):
                for root, dirs, files in os.walk(dirpath):
                    for f in files:
                        if p.search(f):
                            matches.append(f)

        if matches:
            bb.event.fire(bb.event.FilesMatchingFound(filepattern, matches), self.configuration.data)

    def findConfigFiles(self, varname):
        """
        Find config files which are appropriate values for varname.
        i.e. MACHINE, DISTRO
        """
        possible = []
        var = varname.lower()

        data = self.configuration.data
        # iterate configs
        bbpaths = data.getVar('BBPATH', True).split(':')
        for path in bbpaths:
            confpath = os.path.join(path, "conf", var)
            if os.path.exists(confpath):
                for root, dirs, files in os.walk(confpath):
                    # get all child files, these are appropriate values
                    for f in files:
                        val, sep, end = f.rpartition('.')
                        if end == 'conf':
                            possible.append(val)

        if possible:
            bb.event.fire(bb.event.ConfigFilesFound(var, possible), self.configuration.data)

    def findInheritsClass(self, klass):
        """
        Find all recipes which inherit the specified class
        """
        pkg_list = []

        for pfn in self.status.pkg_fn:
            inherits = self.status.inherits.get(pfn, None)
            if inherits and inherits.count(klass) > 0:
                pkg_list.append(self.status.pkg_fn[pfn])

        return pkg_list

    def generateTargetsTree(self, klass=None, pkgs=[]):
        """
        Generate a dependency tree of buildable targets
        Generate an event with the result
        """
        # if the caller hasn't specified a pkgs list default to universe
        if not len(pkgs):
            pkgs = ['universe']
        # if inherited_class passed ensure all recipes which inherit the
        # specified class are included in pkgs
        if klass:
            extra_pkgs = self.findInheritsClass(klass)
            pkgs = pkgs + extra_pkgs

        # generate a dependency tree for all our packages
        tree = self.generatePkgDepTreeData(pkgs, 'build')
        bb.event.fire(bb.event.TargetsTreeGenerated(tree), self.configuration.data)

    def buildWorldTargetList(self):
        """
         Build package list for "bitbake world"
        """
        all_depends = self.status.all_depends
        pn_provides = self.status.pn_provides
        parselog.debug(1, "collating packages for \"world\"")
        for f in self.status.possible_world:
            terminal = True
            pn = self.status.pkg_fn[f]

            for p in pn_provides[pn]:
                if p.startswith('virtual/'):
                    parselog.debug(2, "World build skipping %s due to %s provider starting with virtual/", f, p)
                    terminal = False
                    break
                for pf in self.status.providers[p]:
                    if self.status.pkg_fn[pf] != pn:
                        parselog.debug(2, "World build skipping %s due to both us and %s providing %s", f, pf, p)
                        terminal = False
                        break
            if terminal:
                self.status.world_target.add(pn)

    def interactiveMode( self ):
        """Drop off into a shell"""
        try:
            from bb import shell
        except ImportError:
            parselog.exception("Interactive mode not available")
            sys.exit(1)
        else:
            shell.start( self )

    def _findConfigFile(self, configfile):
        path = os.getcwd()
        while path != "/":
            confpath = os.path.join(path, "conf", configfile)
            if os.path.exists(confpath):
                return confpath

            path, _ = os.path.split(path)
        return None

    def _findLayerConf(self):
        return self._findConfigFile("bblayers.conf")

    def parseConfigurationFiles(self, prefiles, postfiles):
        data = self.configuration.data
        bb.parse.init_parser(data)

        # Parse files for loading *before* bitbake.conf and any includes
        for f in prefiles:
            data = _parse(f, data)

        layerconf = self._findLayerConf()
        if layerconf:
            parselog.debug(2, "Found bblayers.conf (%s)", layerconf)
            data = _parse(layerconf, data)

            layers = (data.getVar('BBLAYERS', True) or "").split()

            data = bb.data.createCopy(data)
            for layer in layers:
                parselog.debug(2, "Adding layer %s", layer)
                data.setVar('LAYERDIR', layer)
                data = _parse(os.path.join(layer, "conf", "layer.conf"), data)
                data.expandVarref('LAYERDIR')

            data.delVar('LAYERDIR')

        if not data.getVar("BBPATH", True):
            raise SystemExit("The BBPATH variable is not set")

        data = _parse(os.path.join("conf", "bitbake.conf"), data)

        # Parse files for loading *after* bitbake.conf and any includes
        for p in postfiles:
            data = _parse(p, data)

        # Handle any INHERITs and inherit the base class
        bbclasses  = ["base"] + (data.getVar('INHERIT', True) or "").split()
        for bbclass in bbclasses:
            data = _inherit(bbclass, data)

        # Nomally we only register event handlers at the end of parsing .bb files
        # We register any handlers we've found so far here...
        for var in data.getVar('__BBHANDLERS') or []:
            bb.event.register(var, data.getVar(var))

        if data.getVar("BB_WORKERCONTEXT", False) is None:
            bb.fetch.fetcher_init(data)
        bb.codeparser.parser_cache_init(data)
        bb.event.fire(bb.event.ConfigParsed(), data)
        bb.parse.init_parser(data)
        data.setVar('BBINCLUDED',bb.parse.get_file_depends(data))
        self.configuration.data = data
        self.configuration.data_hash = data.get_hash()

    def handleCollections( self, collections ):
        """Handle collections"""
        errors = False
        self.status.bbfile_config_priorities = []
        if collections:
            collection_priorities = {}
            collection_depends = {}
            collection_list = collections.split()
            min_prio = 0
            for c in collection_list:
                # Get collection priority if defined explicitly
                priority = self.configuration.data.getVar("BBFILE_PRIORITY_%s" % c, True)
                if priority:
                    try:
                        prio = int(priority)
                    except ValueError:
                        parselog.error("invalid value for BBFILE_PRIORITY_%s: \"%s\"", c, priority)
                        errors = True
                    if min_prio == 0 or prio < min_prio:
                        min_prio = prio
                    collection_priorities[c] = prio
                else:
                    collection_priorities[c] = None

                # Check dependencies and store information for priority calculation
                deps = self.configuration.data.getVar("LAYERDEPENDS_%s" % c, True)
                if deps:
                    depnamelist = []
                    deplist = deps.split()
                    for dep in deplist:
                        depsplit = dep.split(':')
                        if len(depsplit) > 1:
                            try:
                                depver = int(depsplit[1])
                            except ValueError:
                                parselog.error("invalid version value in LAYERDEPENDS_%s: \"%s\"", c, dep)
                                errors = True
                                continue
                        else:
                            depver = None
                        dep = depsplit[0]
                        depnamelist.append(dep)

                        if dep in collection_list:
                            if depver:
                                layerver = self.configuration.data.getVar("LAYERVERSION_%s" % dep, True)
                                if layerver:
                                    try:
                                        lver = int(layerver)
                                    except ValueError:
                                        parselog.error("invalid value for LAYERVERSION_%s: \"%s\"", c, layerver)
                                        errors = True
                                        continue
                                    if lver <> depver:
                                        parselog.error("Layer dependency %s of layer %s is at version %d, expected %d", dep, c, lver, depver)
                                        errors = True
                                else:
                                    parselog.error("Layer dependency %s of layer %s has no version, expected %d", dep, c, depver)
                                    errors = True
                        else:
                            parselog.error("Layer dependency %s of layer %s not found", dep, c)
                            errors = True
                    collection_depends[c] = depnamelist
                else:
                    collection_depends[c] = []

            # Recursively work out collection priorities based on dependencies
            def calc_layer_priority(collection):
                if not collection_priorities[collection]:
                    max_depprio = min_prio
                    for dep in collection_depends[collection]:
                        calc_layer_priority(dep)
                        depprio = collection_priorities[dep]
                        if depprio > max_depprio:
                            max_depprio = depprio
                    max_depprio += 1
                    parselog.debug(1, "Calculated priority of layer %s as %d", collection, max_depprio)
                    collection_priorities[collection] = max_depprio

            # Calculate all layer priorities using calc_layer_priority and store in bbfile_config_priorities
            for c in collection_list:
                calc_layer_priority(c)
                regex = self.configuration.data.getVar("BBFILE_PATTERN_%s" % c, True)
                if regex == None:
                    parselog.error("BBFILE_PATTERN_%s not defined" % c)
                    errors = True
                    continue
                try:
                    cre = re.compile(regex)
                except re.error:
                    parselog.error("BBFILE_PATTERN_%s \"%s\" is not a valid regular expression", c, regex)
                    errors = True
                    continue
                self.status.bbfile_config_priorities.append((c, regex, cre, collection_priorities[c]))
        if errors:
            # We've already printed the actual error(s)
            raise CollectionError("Errors during parsing layer configuration")

    def buildSetVars(self):
        """
        Setup any variables needed before starting a build
        """
        if not self.configuration.data.getVar("BUILDNAME"):
            self.configuration.data.setVar("BUILDNAME", time.strftime('%Y%m%d%H%M'))
        self.configuration.data.setVar("BUILDSTART", time.strftime('%m/%d/%Y %H:%M:%S', time.gmtime()))

    def matchFiles(self, bf):
        """
        Find the .bb files which match the expression in 'buildfile'.
        """

        if bf.startswith("/") or bf.startswith("../"):
            bf = os.path.abspath(bf)
        filelist, masked = self.collect_bbfiles()
        try:
            os.stat(bf)
            return [bf]
        except OSError:
            regexp = re.compile(bf)
            matches = []
            for f in filelist:
                if regexp.search(f) and os.path.isfile(f):
                    matches.append(f)
            return matches

    def matchFile(self, buildfile):
        """
        Find the .bb file which matches the expression in 'buildfile'.
        Raise an error if multiple files
        """
        matches = self.matchFiles(buildfile)
        if len(matches) != 1:
            if matches:
                msg = "Unable to match '%s' to a specific recipe file - %s matches found:" % (buildfile, len(matches))
                if matches:
                    for f in matches:
                        msg += "\n    %s" % f
                parselog.error(msg)
            else:
                parselog.error("Unable to find any recipe file matching '%s'" % buildfile)
            raise NoSpecificMatch
        return matches[0]

    def buildFile(self, buildfile, task):
        """
        Build the file matching regexp buildfile
        """

        # Too many people use -b because they think it's how you normally
        # specify a target to be built, so show a warning
        bb.warn("Buildfile specified, dependencies will not be handled. If this is not what you want, do not use -b / --buildfile.")

        # Parse the configuration here. We need to do it explicitly here since
        # buildFile() doesn't use the cache
        self.parseConfiguration()
        self.status = bb.cache.CacheData(self.caches_array)
        self.handleCollections( self.configuration.data.getVar("BBFILE_COLLECTIONS", True) )

        # If we are told to do the None task then query the default task
        if (task == None):
            task = self.configuration.cmd

        fn, cls = bb.cache.Cache.virtualfn2realfn(buildfile)
        fn = self.matchFile(fn)

        self.buildSetVars()

        self.status = bb.cache.CacheData(self.caches_array)
        infos = bb.cache.Cache.parse(fn, self.get_file_appends(fn), \
                                     self.configuration.data,
                                     self.caches_array)
        infos = dict(infos)

        fn = bb.cache.Cache.realfn2virtual(fn, cls)
        try:
            info_array = infos[fn]
        except KeyError:
            bb.fatal("%s does not exist" % fn)
        self.status.add_from_recipeinfo(fn, info_array)

        # Tweak some variables
        item = info_array[0].pn
        self.status.ignored_dependencies = set()
        self.status.bbfile_priority[fn] = 1

        # Remove external dependencies
        self.status.task_deps[fn]['depends'] = {}
        self.status.deps[fn] = []
        self.status.rundeps[fn] = []
        self.status.runrecs[fn] = []

        # Remove stamp for target if force mode active
        if self.configuration.force:
            logger.verbose("Remove stamp %s, %s", task, fn)
            bb.build.del_stamp('do_%s' % task, self.status, fn)

        # Setup taskdata structure
        taskdata = bb.taskdata.TaskData(self.configuration.abort)
        taskdata.add_provider(self.configuration.data, self.status, item)

        buildname = self.configuration.data.getVar("BUILDNAME")
        bb.event.fire(bb.event.BuildStarted(buildname, [item]), self.configuration.event_data)

        # Execute the runqueue
        runlist = [[item, "do_%s" % task]]

        rq = bb.runqueue.RunQueue(self, self.configuration.data, self.status, taskdata, runlist)

        def buildFileIdle(server, rq, abort):

            if abort or self.state == state.stop:
                rq.finish_runqueue(True)
            elif self.state == state.shutdown:
                rq.finish_runqueue(False)
            failures = 0
            try:
                retval = rq.execute_runqueue()
            except runqueue.TaskFailure as exc:
                failures += len(exc.args)
                retval = False
            except SystemExit as exc:
                self.command.finishAsyncCommand()
                return False

            if not retval:
                bb.event.fire(bb.event.BuildCompleted(len(rq.rqdata.runq_fnid), buildname, item, failures), self.configuration.event_data)
                self.command.finishAsyncCommand()
                return False
            if retval is True:
                return True
            return retval

        self.server_registration_cb(buildFileIdle, rq)

    def buildTargets(self, targets, task):
        """
        Attempt to build the targets specified
        """

        # Need files parsed
        self.updateCache()

        # If we are told to do the NULL task then query the default task
        if (task == None):
            task = self.configuration.cmd

        universe = ('universe' in targets)
        targets = self.checkPackages(targets)

        def buildTargetsIdle(server, rq, abort):
            if abort or self.state == state.stop:
                rq.finish_runqueue(True)
            elif self.state == state.shutdown:
                rq.finish_runqueue(False)
            failures = 0
            try:
                retval = rq.execute_runqueue()
            except runqueue.TaskFailure as exc:
                failures += len(exc.args)
                retval = False
            except SystemExit as exc:
                self.command.finishAsyncCommand()
                return False

            if not retval:
                bb.event.fire(bb.event.BuildCompleted(len(rq.rqdata.runq_fnid), buildname, targets, failures), self.configuration.data)
                self.command.finishAsyncCommand()
                return False
            if retval is True:
                return True
            return retval

        self.buildSetVars()

        buildname = self.configuration.data.getVar("BUILDNAME")
        bb.event.fire(bb.event.BuildStarted(buildname, targets), self.configuration.data)

        localdata = data.createCopy(self.configuration.data)
        bb.data.update_data(localdata)
        bb.data.expandKeys(localdata)

        taskdata = bb.taskdata.TaskData(self.configuration.abort, skiplist=self.skiplist)

        runlist = []
        for k in targets:
            taskdata.add_provider(localdata, self.status, k)
            runlist.append([k, "do_%s" % task])
        taskdata.add_unresolved(localdata, self.status)

        rq = bb.runqueue.RunQueue(self, self.configuration.data, self.status, taskdata, runlist)
        if universe:
            rq.rqdata.warn_multi_bb = True

        self.server_registration_cb(buildTargetsIdle, rq)

    def updateCache(self):
        if self.state == state.running:
            return

        if self.state in (state.shutdown, state.stop):
            self.parser.shutdown(clean=False)
            sys.exit(1)

        if self.state != state.parsing:
            self.parseConfiguration ()

            if self.status:
                del self.status
            self.status = bb.cache.CacheData(self.caches_array)

            ignore = self.configuration.data.getVar("ASSUME_PROVIDED", True) or ""
            self.status.ignored_dependencies = set(ignore.split())

            for dep in self.configuration.extra_assume_provided:
                self.status.ignored_dependencies.add(dep)

            self.handleCollections( self.configuration.data.getVar("BBFILE_COLLECTIONS", True) )

            (filelist, masked) = self.collect_bbfiles()
            self.configuration.data.renameVar("__depends", "__base_depends")

            self.parser = CookerParser(self, filelist, masked)
            self.state = state.parsing

        if not self.parser.parse_next():
            collectlog.debug(1, "parsing complete")
            self.show_appends_with_no_recipes()
            self.buildDepgraph()
            self.state = state.running
            return None

        return True

    def checkPackages(self, pkgs_to_build):

        if len(pkgs_to_build) == 0:
            raise NothingToBuild

        if 'world' in pkgs_to_build:
            self.buildWorldTargetList()
            pkgs_to_build.remove('world')
            for t in self.status.world_target:
                pkgs_to_build.append(t)

        if 'universe' in pkgs_to_build:
            parselog.warn("The \"universe\" target is only intended for testing and may produce errors.")
            parselog.debug(1, "collating packages for \"universe\"")
            pkgs_to_build.remove('universe')
            for t in self.status.universe_target:
                pkgs_to_build.append(t)

        return pkgs_to_build

    def get_bbfiles( self, path = os.getcwd() ):
        """Get list of default .bb files by reading out the current directory"""
        contents = os.listdir(path)
        bbfiles = []
        for f in contents:
            (root, ext) = os.path.splitext(f)
            if ext == ".bb":
                bbfiles.append(os.path.abspath(os.path.join(os.getcwd(), f)))
        return bbfiles

    def find_bbfiles( self, path ):
        """Find all the .bb and .bbappend files in a directory"""
        from os.path import join

        found = []
        for dir, dirs, files in os.walk(path):
            for ignored in ('SCCS', 'CVS', '.svn'):
                if ignored in dirs:
                    dirs.remove(ignored)
            found += [join(dir, f) for f in files if (f.endswith('.bb') or f.endswith('.bbappend'))]

        return found

    def collect_bbfiles( self ):
        """Collect all available .bb build files"""
        parsed, cached, skipped, masked = 0, 0, 0, 0

        collectlog.debug(1, "collecting .bb files")

        files = (data.getVar( "BBFILES", self.configuration.data, True) or "").split()
        data.setVar("BBFILES", " ".join(files), self.configuration.data)

        # Sort files by priority
        files.sort( key=lambda fileitem: self.calc_bbfile_priority(fileitem) )

        if not len(files):
            files = self.get_bbfiles()

        if not len(files):
            collectlog.error("no recipe files to build, check your BBPATH and BBFILES?")
            bb.event.fire(CookerExit(), self.configuration.event_data)

        # Can't use set here as order is important
        newfiles = []
        for f in files:
            if os.path.isdir(f):
                dirfiles = self.find_bbfiles(f)
                for g in dirfiles:
                    if g not in newfiles:
                        newfiles.append(g)
            else:
                globbed = glob.glob(f)
                if not globbed and os.path.exists(f):
                    globbed = [f]
                for g in globbed:
                    if g not in newfiles:
                        newfiles.append(g)

        bbmask = self.configuration.data.getVar('BBMASK', True)

        if bbmask:
            try:
                bbmask_compiled = re.compile(bbmask)
            except sre_constants.error:
                collectlog.critical("BBMASK is not a valid regular expression, ignoring.")
                return list(newfiles), 0

        bbfiles = []
        bbappend = []
        for f in newfiles:
            if bbmask and bbmask_compiled.search(f):
                collectlog.debug(1, "skipping masked file %s", f)
                masked += 1
                continue
            if f.endswith('.bb'):
                bbfiles.append(f)
            elif f.endswith('.bbappend'):
                bbappend.append(f)
            else:
                collectlog.debug(1, "skipping %s: unknown file extension", f)

        # Build a list of .bbappend files for each .bb file
        for f in bbappend:
            base = os.path.basename(f).replace('.bbappend', '.bb')
            if not base in self.appendlist:
               self.appendlist[base] = []
            if f not in self.appendlist[base]:
                self.appendlist[base].append(f)

        # Find overlayed recipes
        # bbfiles will be in priority order which makes this easy
        bbfile_seen = dict()
        self.overlayed = defaultdict(list)
        for f in reversed(bbfiles):
            base = os.path.basename(f)
            if base not in bbfile_seen:
                bbfile_seen[base] = f
            else:
                topfile = bbfile_seen[base]
                self.overlayed[topfile].append(f)

        return (bbfiles, masked)

    def get_file_appends(self, fn):
        """
        Returns a list of .bbappend files to apply to fn
        NB: collect_bbfiles() must have been called prior to this
        """
        f = os.path.basename(fn)
        if f in self.appendlist:
            return self.appendlist[f]
        return []

    def pre_serve(self):
        # Empty the environment. The environment will be populated as
        # necessary from the data store.
        #bb.utils.empty_environment()
        prserv.serv.auto_start(self.configuration.data)
        return

    def post_serve(self):
        prserv.serv.auto_shutdown(self.configuration.data)
        bb.event.fire(CookerExit(), self.configuration.event_data)

    def shutdown(self):
        self.state = state.shutdown

    def stop(self):
        self.state = state.stop

    def reparseFiles(self):
        return

    def initialize(self):
        self.state = state.initial
        self.initConfigurationData()

    def reset(self):
        self.state = state.initial
        self.loadConfigurationData()

def server_main(cooker, func, *args):
    cooker.pre_serve()

    if cooker.configuration.profile:
        try:
            import cProfile as profile
        except:
            import profile
        prof = profile.Profile()

        ret = profile.Profile.runcall(prof, func, *args)

        prof.dump_stats("profile.log")

        # Redirect stdout to capture profile information
        pout = open('profile.log.processed', 'w')
        so = sys.stdout.fileno()
        orig_so = os.dup(sys.stdout.fileno())
        os.dup2(pout.fileno(), so)
   
        import pstats
        p = pstats.Stats('profile.log')
        p.sort_stats('time')
        p.print_stats()
        p.print_callers()
        p.sort_stats('cumulative')
        p.print_stats()

        os.dup2(orig_so, so)
        pout.flush()
        pout.close()  

        print("Raw profiling information saved to profile.log and processed statistics to profile.log.processed")

    else:
        ret = func(*args)

    cooker.post_serve()

    return ret

class CookerExit(bb.event.Event):
    """
    Notify clients of the Cooker shutdown
    """

    def __init__(self):
        bb.event.Event.__init__(self)

def catch_parse_error(func):
    """Exception handling bits for our parsing"""
    @wraps(func)
    def wrapped(fn, *args):
        try:
            return func(fn, *args)
        except (IOError, bb.parse.ParseError, bb.data_smart.ExpansionError) as exc:
            parselog.critical("Unable to parse %s: %s" % (fn, exc))
            sys.exit(1)
    return wrapped

@catch_parse_error
def _parse(fn, data, include=True):
    return bb.parse.handle(fn, data, include)

@catch_parse_error
def _inherit(bbclass, data):
    bb.parse.BBHandler.inherit(bbclass, "configuration INHERITs", 0, data)
    return data

class ParsingFailure(Exception):
    def __init__(self, realexception, recipe):
        self.realexception = realexception
        self.recipe = recipe
        Exception.__init__(self, realexception, recipe)

class Feeder(multiprocessing.Process):
    def __init__(self, jobs, to_parsers, quit):
        self.quit = quit
        self.jobs = jobs
        self.to_parsers = to_parsers
        multiprocessing.Process.__init__(self)

    def run(self):
        while True:
            try:
                quit = self.quit.get_nowait()
            except Queue.Empty:
                pass
            else:
                if quit == 'cancel':
                    self.to_parsers.cancel_join_thread()
                break

            try:
                job = self.jobs.pop()
            except IndexError:
                break

            try:
                self.to_parsers.put(job, timeout=0.5)
            except Queue.Full:
                self.jobs.insert(0, job)
                continue

class Parser(multiprocessing.Process):
    def __init__(self, jobs, results, quit, init):
        self.jobs = jobs
        self.results = results
        self.quit = quit
        self.init = init
        multiprocessing.Process.__init__(self)

    def run(self):
        if self.init:
            self.init()

        pending = []
        while True:
            try:
                self.quit.get_nowait()
            except Queue.Empty:
                pass
            else:
                self.results.cancel_join_thread()
                break

            if pending:
                result = pending.pop()
            else:
                try:
                    job = self.jobs.get(timeout=0.25)
                except Queue.Empty:
                    continue

                if job is None:
                    break
                result = self.parse(*job)

            try:
                self.results.put(result, timeout=0.25)
            except Queue.Full:
                pending.append(result)

    def parse(self, filename, appends, caches_array):
        try:
            return True, bb.cache.Cache.parse(filename, appends, self.cfg, caches_array)
        except Exception as exc:
            tb = sys.exc_info()[2]
            exc.recipe = filename
            exc.traceback = list(bb.exceptions.extract_traceback(tb, context=3))
            return True, exc
        # Need to turn BaseExceptions into Exceptions here so we gracefully shutdown
        # and for example a worker thread doesn't just exit on its own in response to
        # a SystemExit event for example.
        except BaseException as exc:
            return True, ParsingFailure(exc, filename)

class CookerParser(object):
    def __init__(self, cooker, filelist, masked):
        self.filelist = filelist
        self.cooker = cooker
        self.cfgdata = cooker.configuration.data
        self.cfghash = cooker.configuration.data_hash

        # Accounting statistics
        self.parsed = 0
        self.cached = 0
        self.error = 0
        self.masked = masked

        self.skipped = 0
        self.virtuals = 0
        self.total = len(filelist)

        self.current = 0
        self.num_processes = int(self.cfgdata.getVar("BB_NUMBER_PARSE_THREADS", True) or
                                 multiprocessing.cpu_count())

        self.bb_cache = bb.cache.Cache(self.cfgdata, self.cfghash, cooker.caches_array)
        self.fromcache = []
        self.willparse = []
        for filename in self.filelist:
            appends = self.cooker.get_file_appends(filename)
            if not self.bb_cache.cacheValid(filename, appends):
                self.willparse.append((filename, appends, cooker.caches_array))
            else:
                self.fromcache.append((filename, appends))
        self.toparse = self.total - len(self.fromcache)
        self.progress_chunk = max(self.toparse / 100, 1)

        self.start()
        self.haveshutdown = False

    def start(self):
        self.results = self.load_cached()
        self.processes = []
        if self.toparse:
            bb.event.fire(bb.event.ParseStarted(self.toparse), self.cfgdata)
            def init():
                Parser.cfg = self.cfgdata
                multiprocessing.util.Finalize(None, bb.codeparser.parser_cache_save, args=(self.cfgdata,), exitpriority=1)

            self.feeder_quit = multiprocessing.Queue(maxsize=1)
            self.parser_quit = multiprocessing.Queue(maxsize=self.num_processes)
            self.jobs = multiprocessing.Queue(maxsize=self.num_processes)
            self.result_queue = multiprocessing.Queue()
            self.feeder = Feeder(self.willparse, self.jobs, self.feeder_quit)
            self.feeder.start()
            for i in range(0, self.num_processes):
                parser = Parser(self.jobs, self.result_queue, self.parser_quit, init)
                parser.start()
                self.processes.append(parser)

            self.results = itertools.chain(self.results, self.parse_generator())

    def shutdown(self, clean=True, force=False):
        if not self.toparse:
            return
        if self.haveshutdown:
            return
        self.haveshutdown = True

        if clean:
            event = bb.event.ParseCompleted(self.cached, self.parsed,
                                            self.skipped, self.masked,
                                            self.virtuals, self.error,
                                            self.total)
            bb.event.fire(event, self.cfgdata)
            self.feeder_quit.put(None)
            for process in self.processes:
                self.jobs.put(None)
        else:
            self.feeder_quit.put('cancel')

            self.parser_quit.cancel_join_thread()
            for process in self.processes:
                self.parser_quit.put(None)

            self.jobs.cancel_join_thread()
            sys.exit(1)

        for process in self.processes:
            process.join()
        self.feeder.join()

        sync = threading.Thread(target=self.bb_cache.sync)
        sync.start()
        multiprocessing.util.Finalize(None, sync.join, exitpriority=-100)
        bb.codeparser.parser_cache_savemerge(self.cooker.configuration.data)

    def load_cached(self):
        for filename, appends in self.fromcache:
            cached, infos = self.bb_cache.load(filename, appends, self.cfgdata)
            yield not cached, infos

    def parse_generator(self):
        while True:
            if self.parsed >= self.toparse:
                break

            try:
                result = self.result_queue.get(timeout=0.25)
            except Queue.Empty:
                pass
            else:
                value = result[1]
                if isinstance(value, BaseException):
                    raise value
                else:
                    yield result

    def parse_next(self):
        try:
            parsed, result = self.results.next()
        except StopIteration:
            self.shutdown()
            return False
        except ParsingFailure as exc:
            logger.error('Unable to parse %s: %s' %
                     (exc.recipe, bb.exceptions.to_string(exc.realexception)))
            self.shutdown(clean=False)
        except (bb.parse.ParseError, bb.data_smart.ExpansionError) as exc:
            logger.error(str(exc))
            self.shutdown(clean=False)
        except SyntaxError as exc:
            logger.error('Unable to parse %s', exc.recipe)
            self.shutdown(clean=False)
        except Exception as exc:
            etype, value, tb = sys.exc_info()
            logger.error('Unable to parse %s', value.recipe,
                         exc_info=(etype, value, exc.traceback))
            self.shutdown(clean=False)

        self.current += 1
        self.virtuals += len(result)
        if parsed:
            self.parsed += 1
            if self.parsed % self.progress_chunk == 0:
                bb.event.fire(bb.event.ParseProgress(self.parsed, self.toparse),
                              self.cfgdata)
        else:
            self.cached += 1

        for virtualfn, info_array in result:
            if info_array[0].skipped:
                self.skipped += 1
                self.cooker.skiplist[virtualfn] = SkippedPackage(info_array[0])
            self.bb_cache.add_info(virtualfn, info_array, self.cooker.status,
                                        parsed=parsed)
        return True

    def reparse(self, filename):
        infos = self.bb_cache.parse(filename,
                                    self.cooker.get_file_appends(filename),
                                    self.cfgdata, self.cooker.caches_array)
        for vfn, info_array in infos:
            self.cooker.status.add_from_recipeinfo(vfn, info_array)
