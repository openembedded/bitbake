#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2003 - 2005 Michael 'Mickey' Lauer
# Copyright (C) 2005        Holger Hans Peter Freyther
# Copyright (C) 2005        ROAD GmbH
# Copyright (C) 2006        Richard Purdie
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

import sys, os, getopt, glob, copy, os.path, re, time
import bb
from bb import utils, data, parse, event, cache, providers, taskdata, runqueue
from sets import Set
import itertools, sre_constants

parsespin = itertools.cycle( r'|/-\\' )

#============================================================================#
# BBCooker
#============================================================================#
class BBCooker:
    """
    Manages one bitbake build run
    """

    def __init__(self, configuration):
        self.status = None

        self.cache = None
        self.bb_cache = None

        self.configuration = configuration

        if self.configuration.verbose:
            bb.msg.set_verbose(True)

        if self.configuration.debug:
            bb.msg.set_debug_level(self.configuration.debug)
        else:
            bb.msg.set_debug_level(0)

        if self.configuration.debug_domains:
            bb.msg.set_debug_domains(self.configuration.debug_domains)

        self.configuration.data = bb.data.init()

        for f in self.configuration.file:
            self.parseConfigurationFile( f )

        self.parseConfigurationFile( os.path.join( "conf", "bitbake.conf" ) )

        if not self.configuration.cmd:
            self.configuration.cmd = bb.data.getVar("BB_DEFAULT_TASK", self.configuration.data) or "build"

        #
        # Special updated configuration we use for firing events
        #
        self.configuration.event_data = bb.data.createCopy(self.configuration.data)
        bb.data.update_data(self.configuration.event_data)

        #
        # TOSTOP must not be set or our children will hang when they output
        #
        fd = sys.stdout.fileno()
        if os.isatty(fd):
            import termios
            tcattr = termios.tcgetattr(fd)
            if tcattr[3] & termios.TOSTOP:
                bb.msg.note(1, bb.msg.domain.Build, "The terminal had the TOSTOP bit set, clearing...")
                tcattr[3] = tcattr[3] & ~termios.TOSTOP
                termios.tcsetattr(fd, termios.TCSANOW, tcattr)


    def tryBuildPackage(self, fn, item, task, the_data, build_depends):
        """
        Build one task of a package, optionally build following task depends
        """
        bb.event.fire(bb.event.PkgStarted(item, the_data))
        try:
            if not build_depends:
                bb.data.setVarFlag('do_%s' % task, 'dontrundeps', 1, the_data)
            if not self.configuration.dry_run:
                bb.build.exec_task('do_%s' % task, the_data)
            bb.event.fire(bb.event.PkgSucceeded(item, the_data))
            return True
        except bb.build.FuncFailed:
            bb.msg.error(bb.msg.domain.Build, "task stack execution failed")
            bb.event.fire(bb.event.PkgFailed(item, the_data))
            raise
        except bb.build.EventException, e:
            event = e.args[1]
            bb.msg.error(bb.msg.domain.Build, "%s event exception, aborting" % bb.event.getName(event))
            bb.event.fire(bb.event.PkgFailed(item, the_data))
            raise

    def tryBuild( self, fn, build_depends):
        """
        Build a provider and its dependencies. 
        build_depends is a list of previous build dependencies (not runtime)
        If build_depends is empty, we're dealing with a runtime depends
        """

        the_data = self.bb_cache.loadDataFull(fn, self.configuration.data)

        item = self.status.pkg_fn[fn]

        if bb.build.stamp_is_current('do_%s' % self.configuration.cmd, the_data):
            return True

        return self.tryBuildPackage(fn, item, self.configuration.cmd, the_data, build_depends)

    def showVersions(self):
        pkg_pn = self.status.pkg_pn
        preferred_versions = {}
        latest_versions = {}

        # Sort by priority
        for pn in pkg_pn.keys():
            (last_ver,last_file,pref_ver,pref_file) = bb.providers.findBestProvider(pn, self.configuration.data, self.status)
            preferred_versions[pn] = (pref_ver, pref_file)
            latest_versions[pn] = (last_ver, last_file)

        pkg_list = pkg_pn.keys()
        pkg_list.sort()

        for p in pkg_list:
            pref = preferred_versions[p]
            latest = latest_versions[p]

            if pref != latest:
                prefstr = pref[0][0] + ":" + pref[0][1] + '-' + pref[0][2]
            else:
                prefstr = ""

            print "%-30s %20s %20s" % (p, latest[0][0] + ":" + latest[0][1] + "-" + latest[0][2],
                                        prefstr)


    def showEnvironment( self ):
        """Show the outer or per-package environment"""
        if self.configuration.buildfile:
            self.cb = None
            self.bb_cache = bb.cache.init(self)
            bf = self.matchFile(self.configuration.buildfile)
            try:
                self.configuration.data = self.bb_cache.loadDataFull(bf, self.configuration.data)
            except IOError, e:
                bb.msg.fatal(bb.msg.domain.Parsing, "Unable to read %s: %s" % (bf, e))
            except Exception, e:
                bb.msg.fatal(bb.msg.domain.Parsing, "%s" % e)
        # emit variables and shell functions
        try:
            data.update_data( self.configuration.data )
            data.emit_env(sys.__stdout__, self.configuration.data, True)
        except Exception, e:
            bb.msg.fatal(bb.msg.domain.Parsing, "%s" % e)
        # emit the metadata which isnt valid shell
        data.expandKeys( self.configuration.data )	
        for e in self.configuration.data.keys():
            if data.getVarFlag( e, 'python', self.configuration.data ):
                sys.__stdout__.write("\npython %s () {\n%s}\n" % (e, data.getVar(e, self.configuration.data, 1)))

    def generateDotGraph( self, pkgs_to_build, ignore_deps ):
        """
        Generate a task dependency graph. 

        pkgs_to_build A list of packages that needs to be built
        ignore_deps   A list of names where processing of dependencies
                      should be stopped. e.g. dependencies that get
        """

        for dep in ignore_deps:
            self.status.ignored_dependencies.add(dep)

        localdata = data.createCopy(self.configuration.data)
        bb.data.update_data(localdata)
        bb.data.expandKeys(localdata)
        taskdata = bb.taskdata.TaskData(self.configuration.abort)

        runlist = []
        try:
            for k in pkgs_to_build:
                taskdata.add_provider(localdata, self.status, k)
                runlist.append([k, "do_%s" % self.configuration.cmd])
            taskdata.add_unresolved(localdata, self.status)
        except bb.providers.NoProvider:
            sys.exit(1)
        rq = bb.runqueue.RunQueue(self, self.configuration.data, self.status, taskdata, runlist)
        rq.prepare_runqueue()

        seen_fnids = []  
        depends_file = file('depends.dot', 'w' )
        tdepends_file = file('task-depends.dot', 'w' )
        print >> depends_file, "digraph depends {"
        print >> tdepends_file, "digraph depends {"
        rq.prio_map.reverse()
        for task1 in range(len(rq.runq_fnid)):
            task = rq.prio_map[task1]
            taskname = rq.runq_task[task]
            fnid = rq.runq_fnid[task]
            fn = taskdata.fn_index[fnid]
            pn = self.status.pkg_fn[fn]
            version  = "%s:%s-%s" % self.status.pkg_pepvpr[fn]
            print >> tdepends_file, '"%s.%s" [label="%s %s\\n%s\\n%s"]' % (pn, taskname, pn, taskname, version, fn)
            for dep in rq.runq_depends[task]:
                depfn = taskdata.fn_index[rq.runq_fnid[dep]]
                deppn = self.status.pkg_fn[depfn]
                print >> tdepends_file, '"%s.%s" -> "%s.%s"' % (pn, rq.runq_task[task], deppn, rq.runq_task[dep])
            if fnid not in seen_fnids:
                seen_fnids.append(fnid)
                packages = []
                print >> depends_file, '"%s" [label="%s %s\\n%s"]' % (pn, pn, version, fn)		
                for depend in self.status.deps[fn]:
                    print >> depends_file, '"%s" -> "%s"' % (pn, depend)
                rdepends = self.status.rundeps[fn]
                for package in rdepends:
                    for rdepend in rdepends[package]:
                        print >> depends_file, '"%s" -> "%s" [style=dashed]' % (package, rdepend)
                    packages.append(package)
                rrecs = self.status.runrecs[fn]
                for package in rrecs:
                    for rdepend in rrecs[package]:
                        print >> depends_file, '"%s" -> "%s" [style=dashed]' % (package, rdepend)
                    if not package in packages:
                        packages.append(package)
                for package in packages:
                    if package != pn:
                        print >> depends_file, '"%s" [label="%s(%s) %s\\n%s"]' % (package, package, pn, version, fn)
                        for depend in self.status.deps[fn]:
                            print >> depends_file, '"%s" -> "%s"' % (package, depend)
                # Prints a flattened form of the above where subpackages of a package are merged into the main pn
                #print >> depends_file, '"%s" [label="%s %s\\n%s\\n%s"]' % (pn, pn, taskname, version, fn)
                #for rdep in taskdata.rdepids[fnid]:
                #    print >> depends_file, '"%s" -> "%s" [style=dashed]' % (pn, taskdata.run_names_index[rdep])
                #for dep in taskdata.depids[fnid]:
                #    print >> depends_file, '"%s" -> "%s"' % (pn, taskdata.build_names_index[dep])
        print >> depends_file,  "}"
        print >> tdepends_file,  "}"
        bb.msg.note(1, bb.msg.domain.Collection, "Dependencies saved to 'depends.dot'")
        bb.msg.note(1, bb.msg.domain.Collection, "Task dependencies saved to 'task-depends.dot'")

    def buildDepgraph( self ):
        all_depends = self.status.all_depends
        pn_provides = self.status.pn_provides

        localdata = data.createCopy(self.configuration.data)
        bb.data.update_data(localdata)
        bb.data.expandKeys(localdata)

        def calc_bbfile_priority(filename):
            for (regex, pri) in self.status.bbfile_config_priorities:
                if regex.match(filename):
                    return pri
            return 0

        # Handle PREFERRED_PROVIDERS
        for p in (bb.data.getVar('PREFERRED_PROVIDERS', localdata, 1) or "").split():
            (providee, provider) = p.split(':')
            if providee in self.status.preferred and self.status.preferred[providee] != provider:
                bb.msg.error(bb.msg.domain.Provider, "conflicting preferences for %s: both %s and %s specified" % (providee, provider, self.status.preferred[providee]))
            self.status.preferred[providee] = provider

        # Calculate priorities for each file
        for p in self.status.pkg_fn.keys():
            self.status.bbfile_priority[p] = calc_bbfile_priority(p)

    def buildWorldTargetList(self):
        """
         Build package list for "bitbake world"
        """
        all_depends = self.status.all_depends
        pn_provides = self.status.pn_provides
        bb.msg.debug(1, bb.msg.domain.Parsing, "collating packages for \"world\"")
        for f in self.status.possible_world:
            terminal = True
            pn = self.status.pkg_fn[f]

            for p in pn_provides[pn]:
                if p.startswith('virtual/'):
                    bb.msg.debug(2, bb.msg.domain.Parsing, "World build skipping %s due to %s provider starting with virtual/" % (f, p))
                    terminal = False
                    break
                for pf in self.status.providers[p]:
                    if self.status.pkg_fn[pf] != pn:
                        bb.msg.debug(2, bb.msg.domain.Parsing, "World build skipping %s due to both us and %s providing %s" % (f, pf, p))
                        terminal = False
                        break
            if terminal:
                self.status.world_target.add(pn)

            # drop reference count now
            self.status.possible_world = None
            self.status.all_depends    = None

    def myProgressCallback( self, x, y, f, from_cache ):
        """Update any tty with the progress change"""
        if os.isatty(sys.stdout.fileno()):
            sys.stdout.write("\rNOTE: Handling BitBake files: %s (%04d/%04d) [%2d %%]" % ( parsespin.next(), x, y, x*100/y ) )
            sys.stdout.flush()
        else:
            if x == 1:
                sys.stdout.write("Parsing .bb files, please wait...")
                sys.stdout.flush()
            if x == y:
                sys.stdout.write("done.")
                sys.stdout.flush()

    def interactiveMode( self ):
        """Drop off into a shell"""
        try:
            from bb import shell
        except ImportError, details:
            bb.msg.fatal(bb.msg.domain.Parsing, "Sorry, shell not available (%s)" % details )
        else:
            bb.data.update_data( self.configuration.data )
            bb.data.expandKeys( self.configuration.data )
            shell.start( self )
            sys.exit( 0 )

    def parseConfigurationFile( self, afile ):
        try:
            self.configuration.data = bb.parse.handle( afile, self.configuration.data )

            # Add the handlers we inherited by INHERIT
            # we need to do this manually as it is not guranteed
            # we will pick up these classes... as we only INHERIT
            # on .inc and .bb files but not on .conf
            data = bb.data.createCopy( self.configuration.data )
            inherits  = ["base"] + (bb.data.getVar('INHERIT', data, True ) or "").split()
            for inherit in inherits:
                data = bb.parse.handle( os.path.join('classes', '%s.bbclass' % inherit ), data, True )

            # FIXME: This assumes that we included at least one .inc file
            for var in bb.data.keys(data):
                if bb.data.getVarFlag(var, 'handler', data):
                    bb.event.register(var,bb.data.getVar(var, data))

            bb.fetch.fetcher_init(self.configuration.data)

            bb.event.fire(bb.event.ConfigParsed(self.configuration.data))

        except IOError:
            bb.msg.fatal(bb.msg.domain.Parsing, "Unable to open %s" % afile )
        except bb.parse.ParseError, details:
            bb.msg.fatal(bb.msg.domain.Parsing, "Unable to parse %s (%s)" % (afile, details) )

    def handleCollections( self, collections ):
        """Handle collections"""
        if collections:
            collection_list = collections.split()
            for c in collection_list:
                regex = bb.data.getVar("BBFILE_PATTERN_%s" % c, self.configuration.data, 1)
                if regex == None:
                    bb.msg.error(bb.msg.domain.Parsing, "BBFILE_PATTERN_%s not defined" % c)
                    continue
                priority = bb.data.getVar("BBFILE_PRIORITY_%s" % c, self.configuration.data, 1)
                if priority == None:
                    bb.msg.error(bb.msg.domain.Parsing, "BBFILE_PRIORITY_%s not defined" % c)
                    continue
                try:
                    cre = re.compile(regex)
                except re.error:
                    bb.msg.error(bb.msg.domain.Parsing, "BBFILE_PATTERN_%s \"%s\" is not a valid regular expression" % (c, regex))
                    continue
                try:
                    pri = int(priority)
                    self.status.bbfile_config_priorities.append((cre, pri))
                except ValueError:
                    bb.msg.error(bb.msg.domain.Parsing, "invalid value for BBFILE_PRIORITY_%s: \"%s\"" % (c, priority))

    def buildSetVars(self):
        """
        Setup any variables needed before starting a build
        """
        if not bb.data.getVar("BUILDNAME", self.configuration.data):
            bb.data.setVar("BUILDNAME", os.popen('date +%Y%m%d%H%M').readline().strip(), self.configuration.data)
        bb.data.setVar("BUILDSTART", time.strftime('%m/%d/%Y %H:%M:%S',time.gmtime()),self.configuration.data)

    def matchFile(self, buildfile):
        """
        Convert the fragment buildfile into a real file
        Error if there are too many matches
        """
        bf = os.path.abspath(buildfile)
        try:
            os.stat(bf)
            return bf
        except OSError:
            (filelist, masked) = self.collect_bbfiles()
            regexp = re.compile(buildfile)
            matches = []
            for f in filelist:
                if regexp.search(f) and os.path.isfile(f):
                    bf = f
                    matches.append(f)
            if len(matches) != 1:
                bb.msg.error(bb.msg.domain.Parsing, "Unable to match %s (%s matches found):" % (buildfile, len(matches)))
                for f in matches:
                    bb.msg.error(bb.msg.domain.Parsing, "    %s" % f)
                sys.exit(1)
            return matches[0]		    

    def buildFile(self, buildfile):
        """
        Build the file matching regexp buildfile
        """

        bf = self.matchFile(buildfile)

        bbfile_data = bb.parse.handle(bf, self.configuration.data)

        # Remove stamp for target if force mode active
        if self.configuration.force:
            bb.msg.note(2, bb.msg.domain.RunQueue, "Remove stamp %s, %s" % (self.configuration.cmd, bf))
            bb.build.del_stamp('do_%s' % self.configuration.cmd, bbfile_data)

        item = bb.data.getVar('PN', bbfile_data, 1)
        try:
            self.tryBuildPackage(bf, item, self.configuration.cmd, bbfile_data, True)
        except bb.build.EventException:
            bb.msg.error(bb.msg.domain.Build,  "Build of '%s' failed" % item )

        sys.exit(0)

    def buildTargets(self, targets):
        """
        Attempt to build the targets specified
        """

        buildname = bb.data.getVar("BUILDNAME", self.configuration.data)
        bb.event.fire(bb.event.BuildStarted(buildname, targets, self.configuration.event_data))

        localdata = data.createCopy(self.configuration.data)
        bb.data.update_data(localdata)
        bb.data.expandKeys(localdata)

        taskdata = bb.taskdata.TaskData(self.configuration.abort)

        runlist = []
        try:
            for k in targets:
                taskdata.add_provider(localdata, self.status, k)
                runlist.append([k, "do_%s" % self.configuration.cmd])
            taskdata.add_unresolved(localdata, self.status)
        except bb.providers.NoProvider:
            sys.exit(1)

        rq = bb.runqueue.RunQueue(self, self.configuration.data, self.status, taskdata, runlist)
        rq.prepare_runqueue()
        try:
            failures = rq.execute_runqueue()
        except runqueue.TaskFailure, fnids:
            for fnid in fnids:
                bb.msg.error(bb.msg.domain.Build, "'%s' failed" % taskdata.fn_index[fnid])
            sys.exit(1)
        bb.event.fire(bb.event.BuildCompleted(buildname, targets, self.configuration.event_data, failures))

        sys.exit(0)

    def updateCache(self):
        # Import Psyco if available and not disabled
        if not self.configuration.disable_psyco:
            try:
                import psyco
            except ImportError:
                bb.msg.note(1, bb.msg.domain.Collection, "Psyco JIT Compiler (http://psyco.sf.net) not available. Install it to increase performance.")
            else:
                psyco.bind( self.parse_bbfiles )
        else:
            bb.msg.note(1, bb.msg.domain.Collection, "You have disabled Psyco. This decreases performance.")

        self.status = bb.cache.CacheData()

        ignore = bb.data.getVar("ASSUME_PROVIDED", self.configuration.data, 1) or ""
        self.status.ignored_dependencies = Set( ignore.split() )

        self.handleCollections( bb.data.getVar("BBFILE_COLLECTIONS", self.configuration.data, 1) )

        bb.msg.debug(1, bb.msg.domain.Collection, "collecting .bb files")
        (filelist, masked) = self.collect_bbfiles()
        self.parse_bbfiles(filelist, masked, self.myProgressCallback)
        bb.msg.debug(1, bb.msg.domain.Collection, "parsing complete")

        self.buildDepgraph()

    def cook(self):
        """
        We are building stuff here. We do the building
        from here. By default we try to execute task
        build.
        """

        if self.configuration.show_environment:
            self.showEnvironment()
            sys.exit( 0 )

        self.buildSetVars()

        if self.configuration.interactive:
            self.interactiveMode()

        if self.configuration.buildfile is not None:
            return self.buildFile(self.configuration.buildfile)

        # initialise the parsing status now we know we will need deps
        self.updateCache()

        if self.configuration.parse_only:
            bb.msg.note(1, bb.msg.domain.Collection, "Requested parsing .bb files only.  Exiting.")
            return 0

        pkgs_to_build = self.configuration.pkgs_to_build

        bbpkgs = bb.data.getVar('BBPKGS', self.configuration.data, 1)
        if bbpkgs:
            pkgs_to_build.extend(bbpkgs.split())
        if len(pkgs_to_build) == 0 and not self.configuration.show_versions \
                             and not self.configuration.show_environment:
                print "Nothing to do.  Use 'bitbake world' to build everything, or run 'bitbake --help'"
                print "for usage information."
                sys.exit(0)

        try:
            if self.configuration.show_versions:
                self.showVersions()
                sys.exit( 0 )
            if 'world' in pkgs_to_build:
                self.buildWorldTargetList()
                pkgs_to_build.remove('world')
                for t in self.status.world_target:
                    pkgs_to_build.append(t)

            if self.configuration.dot_graph:
                self.generateDotGraph( pkgs_to_build, self.configuration.ignored_dot_deps )
                sys.exit( 0 )

            return self.buildTargets(pkgs_to_build)

        except KeyboardInterrupt:
            bb.msg.note(1, bb.msg.domain.Collection, "KeyboardInterrupt - Build not completed.")
            sys.exit(1)

    def get_bbfiles( self, path = os.getcwd() ):
        """Get list of default .bb files by reading out the current directory"""
        contents = os.listdir(path)
        bbfiles = []
        for f in contents:
            (root, ext) = os.path.splitext(f)
            if ext == ".bb":
                bbfiles.append(os.path.abspath(os.path.join(os.getcwd(),f)))
        return bbfiles

    def find_bbfiles( self, path ):
        """Find all the .bb files in a directory"""
        from os.path import join

        found = []
        for dir, dirs, files in os.walk(path):
            for ignored in ('SCCS', 'CVS', '.svn'):
                if ignored in dirs:
                    dirs.remove(ignored)
            found += [join(dir,f) for f in files if f.endswith('.bb')]

        return found

    def collect_bbfiles( self ):
        """Collect all available .bb build files"""
        parsed, cached, skipped, masked = 0, 0, 0, 0
        self.bb_cache = bb.cache.init(self)

        files = (data.getVar( "BBFILES", self.configuration.data, 1 ) or "").split()
        data.setVar("BBFILES", " ".join(files), self.configuration.data)

        if not len(files):
            files = self.get_bbfiles()

        if not len(files):
            bb.msg.error(bb.msg.domain.Collection, "no files to build.")

        newfiles = []
        for f in files:
            if os.path.isdir(f):
                dirfiles = self.find_bbfiles(f)
                if dirfiles:
                    newfiles += dirfiles
                    continue
            newfiles += glob.glob(f) or [ f ]

        bbmask = bb.data.getVar('BBMASK', self.configuration.data, 1)

        if not bbmask:
            return (newfiles, 0)

        try:
            bbmask_compiled = re.compile(bbmask)
        except sre_constants.error:
            bb.msg.fatal(bb.msg.domain.Collection, "BBMASK is not a valid regular expression.")

        finalfiles = []
        for i in xrange( len( newfiles ) ):
            f = newfiles[i]
            if bbmask and bbmask_compiled.search(f):
                bb.msg.debug(1, bb.msg.domain.Collection, "skipping masked file %s" % f)
                masked += 1
                continue
            finalfiles.append(f)

        return (finalfiles, masked)

    def parse_bbfiles(self, filelist, masked, progressCallback = None):
        parsed, cached, skipped, error = 0, 0, 0, 0
        for i in xrange( len( filelist ) ):
            f = filelist[i]

            bb.msg.debug(1, bb.msg.domain.Collection, "parsing %s" % f)

            # read a file's metadata
            try:
                fromCache, skip = self.bb_cache.loadData(f, self.configuration.data)
                if skip:
                    skipped += 1
                    bb.msg.debug(2, bb.msg.domain.Collection, "skipping %s" % f)
                    self.bb_cache.skip(f)
                    continue
                elif fromCache: cached += 1
                else: parsed += 1
                deps = None

                # Disabled by RP as was no longer functional
                # allow metadata files to add items to BBFILES
                #data.update_data(self.pkgdata[f])
                #addbbfiles = self.bb_cache.getVar('BBFILES', f, False) or None
                #if addbbfiles:
                #    for aof in addbbfiles.split():
                #        if not files.count(aof):
                #            if not os.path.isabs(aof):
                #                aof = os.path.join(os.path.dirname(f),aof)
                #            files.append(aof)

                self.bb_cache.handle_data(f, self.status)

                # now inform the caller
                if progressCallback is not None:
                    progressCallback( i + 1, len( filelist ), f, fromCache )

            except IOError, e:
                self.bb_cache.remove(f)
                bb.msg.error(bb.msg.domain.Collection, "opening %s: %s" % (f, e))
                pass
            except KeyboardInterrupt:
                self.bb_cache.sync()
                raise
            except Exception, e:
                error += 1
                self.bb_cache.remove(f)
                bb.msg.error(bb.msg.domain.Collection, "%s while parsing %s" % (e, f))
            except:
                self.bb_cache.remove(f)
                raise

        if progressCallback is not None:
            print "\r" # need newline after Handling Bitbake files message
            bb.msg.note(1, bb.msg.domain.Collection, "Parsing finished. %d cached, %d parsed, %d skipped, %d masked." % ( cached, parsed, skipped, masked ))

        self.bb_cache.sync()

        if error > 0:
            bb.msg.fatal(bb.msg.domain.Collection, "Parsing errors found, exiting...")
