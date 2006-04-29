#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Event' implementation

Caching of bitbake variables before task execution

# Copyright (C) 2006        Richard Purdie

# but small sections based on code from bin/bitbake:
# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2003 - 2005 Michael 'Mickey' Lauer
# Copyright (C) 2005        Holger Hans Peter Freyther
# Copyright (C) 2005        ROAD GmbH

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc., 59 Temple
Place, Suite 330, Boston, MA 02111-1307 USA. 

"""

import os, re
import bb.data
import bb.utils

try:
    import cPickle as pickle
except ImportError:
    import pickle
    print "NOTE: Importing cPickle failed. Falling back to a very slow implementation."

# __cache_version__ = "123"
__cache_version__ = "124" # changes the __depends structure

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
            if cooker.cb is not None:
                print "NOTE: Not using a cache. Set CACHE = <directory> to enable."
        else:
            self.has_cache = True
            self.cachefile = os.path.join(self.cachedir,"bb_cache.dat")
            
            if cooker.cb is not None:
                print "NOTE: Using cache in '%s'" % self.cachedir
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
            except (ValueError, KeyError):
                bb.note("Invalid cache found, rebuilding...")
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
            bb.error("Parsing error data_fn %s and fn %s don't match" % (self.data_fn, fn))

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

    def loadDataFull(self, fn, cooker):
        """
        Return a complete set of data for fn.
        To do this, we need to parse the file.
        """
        bb_data, skipped = self.load_bbfile(fn, cooker)
        return bb_data

    def loadData(self, fn, cooker):
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

        bb_data, skipped = self.load_bbfile(fn, cooker)
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
            bb.debug(2, "Cache: %s not longer exists" % fn)
            self.remove(fn)
            return False

        # File isn't in depends_cache
        if not fn in self.depends_cache:
            bb.debug(2, "Cache: %s is not cached" % fn)
            self.remove(fn)
            return False

        # Check the file's timestamp
        if bb.parse.cached_mtime(fn) > self.getVar("CACHETIMESTAMP", fn, True):
            bb.debug(2, "Cache: %s changed" % fn)
            self.remove(fn)
            return False

        # Check dependencies are still valid
        depends = self.getVar("__depends", fn, True)
        for f,old_mtime in depends:
            new_mtime = bb.parse.cached_mtime(f)
            if (new_mtime > old_mtime):
                bb.debug(2, "Cache: %s's dependency %s changed" % (fn, f))
                self.remove(fn)
                return False

        bb.debug(2, "Depends Cache: %s is clean" % fn)
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
        bb.debug(1, "Removing %s from cache" % fn)
        if fn in self.depends_cache:
            del self.depends_cache[fn]
        if fn in self.clean:
            del self.clean[fn]

    def sync(self):
        """
        Save the cache
        Called from the parser when complete (or exitting)
        """

        if not self.has_cache:
            return

        version_data = {}
        version_data['CACHE_VER'] = __cache_version__
        version_data['BITBAKE_VER'] = bb.__version__

        p = pickle.Pickler(file(self.cachefile, "wb" ), -1 )
        p.dump([self.depends_cache, version_data])

    def mtime(self, cachefile):
        try:
            return os.stat(cachefile)[8]
        except OSError:
            return 0

    def load_bbfile( self, bbfile , cooker):
        """
        Load and parse one .bb build file
        Return the data and whether parsing resulted in the file being skipped
        """

        import bb
        from bb import utils, data, parse, debug, event, fatal

        topdir = data.getVar('TOPDIR', cooker.configuration.data)
        if not topdir:
            topdir = os.path.abspath(os.getcwd())
            # set topdir to here
            data.setVar('TOPDIR', topdir, cooker.configuration)
        bbfile = os.path.abspath(bbfile)
        bbfile_loc = os.path.abspath(os.path.dirname(bbfile))
        # expand tmpdir to include this topdir
        data.setVar('TMPDIR', data.getVar('TMPDIR', cooker.configuration.data, 1) or "", cooker.configuration.data)
        # set topdir to location of .bb file
        topdir = bbfile_loc
        #data.setVar('TOPDIR', topdir, cfg)
        # go there
        oldpath = os.path.abspath(os.getcwd())
        if self.mtime(topdir):
            os.chdir(topdir)
        bb_data = data.init_db(cooker.configuration.data)
        try:
            parse.handle(bbfile, bb_data) # read .bb data
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

