# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake 'Event' implementation
#
# Caching of bitbake variables before task execution

# Copyright (C) 2006        Richard Purdie

# but small sections based on code from bin/bitbake:
# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2003 - 2005 Michael 'Mickey' Lauer
# Copyright (C) 2005        Holger Hans Peter Freyther
# Copyright (C) 2005        ROAD GmbH
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


import os, re
import bb.data
import bb.utils
from sets import Set

try:
    import cPickle as pickle
except ImportError:
    import pickle
    bb.msg.note(1, bb.msg.domain.Cache, "Importing cPickle failed. Falling back to a very slow implementation.")

__cache_version__ = "126"

class Cache:
    """
    BitBake Cache implementation
    """
    def __init__(self, cooker):


        self.cachedir = bb.data.getVar("CACHE", cooker.configuration.data, True)
        self.clean = {}
        self.depends_cache = {}
        self.data = None
        self.data_fn = None

        if self.cachedir in [None, '']:
            self.has_cache = False
            bb.msg.note(1, bb.msg.domain.Cache, "Not using a cache. Set CACHE = <directory> to enable.")
        else:
            self.has_cache = True
            self.cachefile = os.path.join(self.cachedir,"bb_cache.dat")
            
            bb.msg.debug(1, bb.msg.domain.Cache, "Using cache in '%s'" % self.cachedir)
            try:
                os.stat( self.cachedir )
            except OSError:
                bb.mkdirhier( self.cachedir )

        if self.has_cache and (self.mtime(self.cachefile)):
            try:
                p = pickle.Unpickler( file(self.cachefile,"rb"))
                self.depends_cache, version_data = p.load()
                if version_data['CACHE_VER'] != __cache_version__:
                    raise ValueError, 'Cache Version Mismatch'
                if version_data['BITBAKE_VER'] != bb.__version__:
                    raise ValueError, 'Bitbake Version Mismatch'
            except EOFError:
                bb.msg.note(1, bb.msg.domain.Cache, "Truncated cache found, rebuilding...")
                self.depends_cache = {}
            except (ValueError, KeyError):
                bb.msg.note(1, bb.msg.domain.Cache, "Invalid cache found, rebuilding...")
                self.depends_cache = {}

        if self.depends_cache:
            for fn in self.depends_cache.keys():
                self.clean[fn] = ""
                self.cacheValidUpdate(fn)

    def getVar(self, var, fn, exp = 0):
        """
        Gets the value of a variable
        (similar to getVar in the data class)
        
        There are two scenarios:
          1. We have cached data - serve from depends_cache[fn]
          2. We're learning what data to cache - serve from data 
             backend but add a copy of the data to the cache.
        """

        if fn in self.clean:
            return self.depends_cache[fn][var]

        if not fn in self.depends_cache:
            self.depends_cache[fn] = {}

        if fn != self.data_fn:
            # We're trying to access data in the cache which doesn't exist
            # yet setData hasn't been called to setup the right access. Very bad.
            bb.msg.error(bb.msg.domain.Cache, "Parsing error data_fn %s and fn %s don't match" % (self.data_fn, fn))

        result = bb.data.getVar(var, self.data, exp)
        self.depends_cache[fn][var] = result
        return result

    def setData(self, fn, data):
        """
        Called to prime bb_cache ready to learn which variables to cache.
        Will be followed by calls to self.getVar which aren't cached
        but can be fulfilled from self.data.
        """
        self.data_fn = fn
        self.data = data

        # Make sure __depends makes the depends_cache
        self.getVar("__depends", fn, True)
        self.depends_cache[fn]["CACHETIMESTAMP"] = bb.parse.cached_mtime(fn)

    def loadDataFull(self, fn, cfgData):
        """
        Return a complete set of data for fn.
        To do this, we need to parse the file.
        """
        bb_data, skipped = self.load_bbfile(fn, cfgData)
        return bb_data

    def loadData(self, fn, cfgData):
        """
        Load a subset of data for fn.
        If the cached data is valid we do nothing,
        To do this, we need to parse the file and set the system
        to record the variables accessed.
        Return the cache status and whether the file was skipped when parsed
        """
        if self.cacheValid(fn):
            if "SKIPPED" in self.depends_cache[fn]:
                return True, True
            return True, False

        bb_data, skipped = self.load_bbfile(fn, cfgData)
        self.setData(fn, bb_data)
        return False, skipped

    def cacheValid(self, fn):
        """
        Is the cache valid for fn?
        Fast version, no timestamps checked.
        """
        # Is cache enabled?
        if not self.has_cache:
            return False
        if fn in self.clean:
            return True
        return False

    def cacheValidUpdate(self, fn):
        """
        Is the cache valid for fn?
        Make thorough (slower) checks including timestamps.
        """
        # Is cache enabled?
        if not self.has_cache:
            return False

        # Check file still exists
        if self.mtime(fn) == 0:
            bb.msg.debug(2, bb.msg.domain.Cache, "Cache: %s not longer exists" % fn)
            self.remove(fn)
            return False

        # File isn't in depends_cache
        if not fn in self.depends_cache:
            bb.msg.debug(2, bb.msg.domain.Cache, "Cache: %s is not cached" % fn)
            self.remove(fn)
            return False

        # Check the file's timestamp
        if bb.parse.cached_mtime(fn) > self.getVar("CACHETIMESTAMP", fn, True):
            bb.msg.debug(2, bb.msg.domain.Cache, "Cache: %s changed" % fn)
            self.remove(fn)
            return False

        # Check dependencies are still valid
        depends = self.getVar("__depends", fn, True)
        for f,old_mtime in depends:
            # Check if file still exists
            if self.mtime(f) == 0:
                return False

            new_mtime = bb.parse.cached_mtime(f)
            if (new_mtime > old_mtime):
                bb.msg.debug(2, bb.msg.domain.Cache, "Cache: %s's dependency %s changed" % (fn, f))
                self.remove(fn)
                return False

        bb.msg.debug(2, bb.msg.domain.Cache, "Depends Cache: %s is clean" % fn)
        if not fn in self.clean:
            self.clean[fn] = ""

        return True

    def skip(self, fn):
        """
        Mark a fn as skipped
        Called from the parser
        """
        if not fn in self.depends_cache:
            self.depends_cache[fn] = {}
        self.depends_cache[fn]["SKIPPED"] = "1"

    def remove(self, fn):
        """
        Remove a fn from the cache
        Called from the parser in error cases
        """
        bb.msg.debug(1, bb.msg.domain.Cache, "Removing %s from cache" % fn)
        if fn in self.depends_cache:
            del self.depends_cache[fn]
        if fn in self.clean:
            del self.clean[fn]

    def sync(self):
        """
        Save the cache
        Called from the parser when complete (or exiting)
        """

        if not self.has_cache:
            return

        version_data = {}
        version_data['CACHE_VER'] = __cache_version__
        version_data['BITBAKE_VER'] = bb.__version__

        p = pickle.Pickler(file(self.cachefile, "wb" ), -1 )
        p.dump([self.depends_cache, version_data])

    def mtime(self, cachefile):
        return bb.parse.cached_mtime_noerror(cachefile)

    def handle_data(self, file_name, cacheData):
        """
        Save data we need into the cache 
        """

        pn       = self.getVar('PN', file_name, True)
        pe       = self.getVar('PE', file_name, True) or "0"
        pv       = self.getVar('PV', file_name, True)
        pr       = self.getVar('PR', file_name, True)
        dp       = int(self.getVar('DEFAULT_PREFERENCE', file_name, True) or "0")
        provides  = Set([pn] + (self.getVar("PROVIDES", file_name, True) or "").split())
        depends   = bb.utils.explode_deps(self.getVar("DEPENDS", file_name, True) or "")
        packages  = (self.getVar('PACKAGES', file_name, True) or "").split()
        packages_dynamic = (self.getVar('PACKAGES_DYNAMIC', file_name, True) or "").split()
        rprovides = (self.getVar("RPROVIDES", file_name, True) or "").split()

        cacheData.task_queues[file_name] = self.getVar("_task_graph", file_name, True)
        cacheData.task_deps[file_name] = self.getVar("_task_deps", file_name, True)

        # build PackageName to FileName lookup table
        if pn not in cacheData.pkg_pn:
            cacheData.pkg_pn[pn] = []
        cacheData.pkg_pn[pn].append(file_name)

        cacheData.stamp[file_name] = self.getVar('STAMP', file_name, True)

        # build FileName to PackageName lookup table
        cacheData.pkg_fn[file_name] = pn
        cacheData.pkg_pepvpr[file_name] = (pe,pv,pr)
        cacheData.pkg_dp[file_name] = dp

        # Build forward and reverse provider hashes
        # Forward: virtual -> [filenames]
        # Reverse: PN -> [virtuals]
        if pn not in cacheData.pn_provides:
            cacheData.pn_provides[pn] = Set()
        cacheData.pn_provides[pn] |= provides

        for provide in provides:
            if provide not in cacheData.providers:
                cacheData.providers[provide] = []
            cacheData.providers[provide].append(file_name)

        cacheData.deps[file_name] = Set()
        for dep in depends:
            cacheData.all_depends.add(dep)
            cacheData.deps[file_name].add(dep)

        # Build reverse hash for PACKAGES, so runtime dependencies 
        # can be be resolved (RDEPENDS, RRECOMMENDS etc.)
        for package in packages:
            if not package in cacheData.packages:
                cacheData.packages[package] = []
            cacheData.packages[package].append(file_name)
            rprovides += (self.getVar("RPROVIDES_%s" % package, file_name, 1) or "").split() 

        for package in packages_dynamic:
            if not package in cacheData.packages_dynamic:
                cacheData.packages_dynamic[package] = []
            cacheData.packages_dynamic[package].append(file_name)

        for rprovide in rprovides:
            if not rprovide in cacheData.rproviders:
                cacheData.rproviders[rprovide] = []
            cacheData.rproviders[rprovide].append(file_name)

        # Build hash of runtime depends and rececommends

        def add_dep(deplist, deps):
            for dep in deps:
                if not dep in deplist:
                    deplist[dep] = ""

        if not file_name in cacheData.rundeps:
            cacheData.rundeps[file_name] = {}
        if not file_name in cacheData.runrecs:
            cacheData.runrecs[file_name] = {}

        for package in packages + [pn]:
            if not package in cacheData.rundeps[file_name]:
                cacheData.rundeps[file_name][package] = {}
            if not package in cacheData.runrecs[file_name]:
                cacheData.runrecs[file_name][package] = {}

            add_dep(cacheData.rundeps[file_name][package], bb.utils.explode_deps(self.getVar('RDEPENDS', file_name, True) or ""))
            add_dep(cacheData.runrecs[file_name][package], bb.utils.explode_deps(self.getVar('RRECOMMENDS', file_name, True) or ""))
            add_dep(cacheData.rundeps[file_name][package], bb.utils.explode_deps(self.getVar("RDEPENDS_%s" % package, file_name, True) or ""))
            add_dep(cacheData.runrecs[file_name][package], bb.utils.explode_deps(self.getVar("RRECOMMENDS_%s" % package, file_name, True) or ""))

        # Collect files we may need for possible world-dep
        # calculations
        if not self.getVar('BROKEN', file_name, True) and not self.getVar('EXCLUDE_FROM_WORLD', file_name, True):
            cacheData.possible_world.append(file_name)


    def load_bbfile( self, bbfile , config):
        """
        Load and parse one .bb build file
        Return the data and whether parsing resulted in the file being skipped
        """

        import bb
        from bb import utils, data, parse, debug, event, fatal

        # expand tmpdir to include this topdir
        data.setVar('TMPDIR', data.getVar('TMPDIR', config, 1) or "", config)
        bbfile_loc = os.path.abspath(os.path.dirname(bbfile))
        oldpath = os.path.abspath(os.getcwd())
        if self.mtime(bbfile_loc):
            os.chdir(bbfile_loc)
        bb_data = data.init_db(config)
        try:
            bb_data = parse.handle(bbfile, bb_data) # read .bb data
            os.chdir(oldpath)
            return bb_data, False
        except bb.parse.SkipPackage:
            os.chdir(oldpath)
            return bb_data, True
        except:
            os.chdir(oldpath)
            raise

def init(cooker):
    """
    The Objective: Cache the minimum amount of data possible yet get to the 
    stage of building packages (i.e. tryBuild) without reparsing any .bb files.

    To do this, we intercept getVar calls and only cache the variables we see 
    being accessed. We rely on the cache getVar calls being made for all 
    variables bitbake might need to use to reach this stage. For each cached 
    file we need to track:

    * Its mtime
    * The mtimes of all its dependencies
    * Whether it caused a parse.SkipPackage exception

    Files causing parsing errors are evicted from the cache.

    """
    return Cache(cooker)



#============================================================================#
# CacheData
#============================================================================#
class CacheData:
    """
    The data structures we compile from the cached data
    """

    def __init__(self):
        """
        Direct cache variables
        (from Cache.handle_data)
        """
        self.providers   = {}
        self.rproviders = {}
        self.packages = {}
        self.packages_dynamic = {}
        self.possible_world = []
        self.pkg_pn = {}
        self.pkg_fn = {}
        self.pkg_pepvpr = {}
        self.pkg_dp = {}
        self.pn_provides = {}
        self.all_depends = Set()
        self.deps = {}
        self.rundeps = {}
        self.runrecs = {}
        self.task_queues = {}
        self.task_deps = {}
        self.stamp = {}
        self.preferred = {}

        """
        Indirect Cache variables
        (set elsewhere)
        """
        self.ignored_dependencies = []
        self.world_target = Set()
        self.bbfile_priority = {}
        self.bbfile_config_priorities = []
