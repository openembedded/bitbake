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


import os
import logging
from collections import defaultdict, namedtuple
import bb.data
import bb.utils

logger = logging.getLogger("BitBake.Cache")

try:
    import cPickle as pickle
except ImportError:
    import pickle
    logger.info("Importing cPickle failed. "
                "Falling back to a very slow implementation.")

__cache_version__ = "136"

recipe_fields = (
    'pn',
    'pv',
    'pr',
    'pe',
    'defaultpref',
    'depends',
    'provides',
    'task_deps',
    'stamp',
    'stamp_extrainfo',
    'broken',
    'not_world',
    'skipped',
    'timestamp',
    'packages',
    'packages_dynamic',
    'rdepends',
    'rdepends_pkg',
    'rprovides',
    'rprovides_pkg',
    'rrecommends',
    'rrecommends_pkg',
    'nocache',
    'variants',
    'file_depends',
    'tasks',
    'basetaskhashes',
    'hashfilename',
    'inherits',
    'summary',
    'license',
    'section',
)


class RecipeInfo(namedtuple('RecipeInfo', recipe_fields)):
    __slots__ = ()

    @classmethod
    def listvar(cls, var, metadata):
        return cls.getvar(var, metadata).split()

    @classmethod
    def intvar(cls, var, metadata):
        return int(cls.getvar(var, metadata) or 0)

    @classmethod
    def depvar(cls, var, metadata):
        return bb.utils.explode_deps(cls.getvar(var, metadata))

    @classmethod
    def pkgvar(cls, var, packages, metadata):
        return dict((pkg, cls.depvar("%s_%s" % (var, pkg), metadata))
                    for pkg in packages)

    @classmethod
    def taskvar(cls, var, tasks, metadata):
        return dict((task, cls.getvar("%s_task-%s" % (var, task), metadata))
                    for task in tasks)

    @classmethod
    def flaglist(cls, flag, varlist, metadata):
        return dict((var, metadata.getVarFlag(var, flag, True))
                    for var in varlist)

    @classmethod
    def getvar(cls, var, metadata):
        return metadata.getVar(var, True) or ''

    @classmethod
    def make_optional(cls, default=None, **kwargs):
        """Construct the namedtuple from the specified keyword arguments,
        with every value considered optional, using the default value if
        it was not specified."""
        for field in cls._fields:
            kwargs[field] = kwargs.get(field, default)
        return cls(**kwargs)

    @classmethod
    def from_metadata(cls, filename, metadata):
        if cls.getvar('__SKIPPED', metadata):
            return cls.make_optional(skipped=True)

        tasks = metadata.getVar('__BBTASKS', False)

        pn = cls.getvar('PN', metadata)
        packages = cls.listvar('PACKAGES', metadata)
        if not pn in packages:
            packages.append(pn)

        return RecipeInfo(
            tasks            = tasks,
            basetaskhashes   = cls.taskvar('BB_BASEHASH', tasks, metadata),
            hashfilename     = cls.getvar('BB_HASHFILENAME', metadata),

            file_depends     = metadata.getVar('__depends', False),
            task_deps        = metadata.getVar('_task_deps', False) or
                               {'tasks': [], 'parents': {}},
            variants         = cls.listvar('__VARIANTS', metadata) + [''],

            skipped          = False,
            timestamp        = bb.parse.cached_mtime(filename),
            packages         = cls.listvar('PACKAGES', metadata),
            pn               = pn,
            pe               = cls.getvar('PE', metadata),
            pv               = cls.getvar('PV', metadata),
            pr               = cls.getvar('PR', metadata),
            nocache          = cls.getvar('__BB_DONT_CACHE', metadata),
            defaultpref      = cls.intvar('DEFAULT_PREFERENCE', metadata),
            broken           = cls.getvar('BROKEN', metadata),
            not_world        = cls.getvar('EXCLUDE_FROM_WORLD', metadata),
            stamp            = cls.getvar('STAMP', metadata),
            stamp_extrainfo  = cls.flaglist('stamp-extra-info', tasks, metadata),
            packages_dynamic = cls.listvar('PACKAGES_DYNAMIC', metadata),
            depends          = cls.depvar('DEPENDS', metadata),
            provides         = cls.depvar('PROVIDES', metadata),
            rdepends         = cls.depvar('RDEPENDS', metadata),
            rprovides        = cls.depvar('RPROVIDES', metadata),
            rrecommends      = cls.depvar('RRECOMMENDS', metadata),
            rprovides_pkg    = cls.pkgvar('RPROVIDES', packages, metadata),
            rdepends_pkg     = cls.pkgvar('RDEPENDS', packages, metadata),
            rrecommends_pkg  = cls.pkgvar('RRECOMMENDS', packages, metadata),
            inherits         = cls.getvar('__inherit_cache', metadata),
            summary          = cls.getvar('SUMMARY', metadata),
            license          = cls.getvar('LICENSE', metadata),
            section          = cls.getvar('SECTION', metadata),
        )


class Cache(object):
    """
    BitBake Cache implementation
    """

    def __init__(self, data):
        self.cachedir = bb.data.getVar("CACHE", data, True)
        self.clean = set()
        self.checked = set()
        self.depends_cache = {}
        self.data = None
        self.data_fn = None
        self.cacheclean = True

        if self.cachedir in [None, '']:
            self.has_cache = False
            logger.info("Not using a cache. "
                        "Set CACHE = <directory> to enable.")
            return

        self.has_cache = True
        self.cachefile = os.path.join(self.cachedir, "bb_cache.dat")

        logger.debug(1, "Using cache in '%s'", self.cachedir)
        bb.utils.mkdirhier(self.cachedir)

        # If any of configuration.data's dependencies are newer than the
        # cache there isn't even any point in loading it...
        newest_mtime = 0
        deps = bb.data.getVar("__base_depends", data)

        old_mtimes = [old_mtime for _, old_mtime in deps]
        old_mtimes.append(newest_mtime)
        newest_mtime = max(old_mtimes)

        if bb.parse.cached_mtime_noerror(self.cachefile) >= newest_mtime:
            self.load_cachefile()
        elif os.path.isfile(self.cachefile):
            logger.info("Out of date cache found, rebuilding...")

    def load_cachefile(self):
        with open(self.cachefile, "rb") as cachefile:
            pickled = pickle.Unpickler(cachefile)
            try:
                cache_ver = pickled.load()
                bitbake_ver = pickled.load()
            except Exception:
                logger.info('Invalid cache, rebuilding...')
                return

            if cache_ver != __cache_version__:
                logger.info('Cache version mismatch, rebuilding...')
                return
            elif bitbake_ver != bb.__version__:
                logger.info('Bitbake version mismatch, rebuilding...')
                return

            cachesize = os.fstat(cachefile.fileno()).st_size
            bb.event.fire(bb.event.CacheLoadStarted(cachesize), self.data)

            previous_percent = 0
            while cachefile:
                try:
                    key = pickled.load()
                    value = pickled.load()
                except Exception:
                    break

                self.depends_cache[key] = value

                # only fire events on even percentage boundaries
                current_progress = cachefile.tell()
                current_percent = 100 * current_progress / cachesize
                if current_percent > previous_percent:
                    previous_percent = current_percent
                    bb.event.fire(bb.event.CacheLoadProgress(current_progress),
                                  self.data)

            bb.event.fire(bb.event.CacheLoadCompleted(cachesize,
                                                      len(self.depends_cache)),
                          self.data)

    @staticmethod
    def virtualfn2realfn(virtualfn):
        """
        Convert a virtual file name to a real one + the associated subclass keyword
        """

        fn = virtualfn
        cls = ""
        if virtualfn.startswith('virtual:'):
            cls = virtualfn.split(':', 2)[1]
            fn = virtualfn.replace('virtual:' + cls + ':', '')
        return (fn, cls)

    @staticmethod
    def realfn2virtual(realfn, cls):
        """
        Convert a real filename + the associated subclass keyword to a virtual filename
        """
        if cls == "":
            return realfn
        return "virtual:" + cls + ":" + realfn

    @classmethod
    def loadDataFull(cls, virtualfn, appends, cfgData):
        """
        Return a complete set of data for fn.
        To do this, we need to parse the file.
        """

        (fn, virtual) = cls.virtualfn2realfn(virtualfn)

        logger.debug(1, "Parsing %s (full)", fn)

        bb_data = cls.load_bbfile(fn, appends, cfgData)
        return bb_data[virtual]

    @classmethod
    def parse(cls, filename, appends, configdata):
        """Parse the specified filename, returning the recipe information"""
        infos = []
        datastores = cls.load_bbfile(filename, appends, configdata)
        depends = set()
        for variant, data in sorted(datastores.iteritems(),
                                    key=lambda i: i[0],
                                    reverse=True):
            virtualfn = cls.realfn2virtual(filename, variant)
            depends |= (data.getVar("__depends", False) or set())
            if depends and not variant:
                data.setVar("__depends", depends)
            info = RecipeInfo.from_metadata(filename, data)
            infos.append((virtualfn, info))
        return infos

    def load(self, filename, appends, configdata):
        """Obtain the recipe information for the specified filename,
        using cached values if available, otherwise parsing.

        Note that if it does parse to obtain the info, it will not
        automatically add the information to the cache or to your
        CacheData.  Use the add or add_info method to do so after
        running this, or use loadData instead."""
        cached = self.cacheValid(filename)
        if cached:
            infos = []
            info = self.depends_cache[filename]
            for variant in info.variants:
                virtualfn = self.realfn2virtual(filename, variant)
                infos.append((virtualfn, self.depends_cache[virtualfn]))
        else:
            logger.debug(1, "Parsing %s", filename)
            return self.parse(filename, appends, configdata)

        return cached, infos

    def loadData(self, fn, appends, cfgData, cacheData):
        """Load the recipe info for the specified filename,
        parsing and adding to the cache if necessary, and adding
        the recipe information to the supplied CacheData instance."""
        skipped, virtuals = 0, 0

        cached, infos = self.load(fn, appends, cfgData)
        for virtualfn, info in infos:
            if info.skipped:
                logger.debug(1, "Skipping %s", virtualfn)
                skipped += 1
            else:
                self.add_info(virtualfn, info, cacheData, not cached)
                virtuals += 1

        return cached, skipped, virtuals

    def cacheValid(self, fn):
        """
        Is the cache valid for fn?
        Fast version, no timestamps checked.
        """
        if fn not in self.checked:
            self.cacheValidUpdate(fn)

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

        self.checked.add(fn)

        # File isn't in depends_cache
        if not fn in self.depends_cache:
            logger.debug(2, "Cache: %s is not cached", fn)
            return False

        mtime = bb.parse.cached_mtime_noerror(fn)

        # Check file still exists
        if mtime == 0:
            logger.debug(2, "Cache: %s no longer exists", fn)
            self.remove(fn)
            return False

        info = self.depends_cache[fn]
        # Check the file's timestamp
        if mtime != info.timestamp:
            logger.debug(2, "Cache: %s changed", fn)
            self.remove(fn)
            return False

        # Check dependencies are still valid
        depends = info.file_depends
        if depends:
            for f, old_mtime in depends:
                fmtime = bb.parse.cached_mtime_noerror(f)
                # Check if file still exists
                if old_mtime != 0 and fmtime == 0:
                    logger.debug(2, "Cache: %s's dependency %s was removed",
                                    fn, f)
                    self.remove(fn)
                    return False

                if (fmtime != old_mtime):
                    logger.debug(2, "Cache: %s's dependency %s changed",
                                    fn, f)
                    self.remove(fn)
                    return False

        invalid = False
        for cls in info.variants:
            virtualfn = self.realfn2virtual(fn, cls)
            self.clean.add(virtualfn)
            if virtualfn not in self.depends_cache:
                logger.debug(2, "Cache: %s is not cached", virtualfn)
                invalid = True

        # If any one of the variants is not present, mark as invalid for all
        if invalid:
            for cls in info.variants:
                virtualfn = self.realfn2virtual(fn, cls)
                if virtualfn in self.clean:
                    logger.debug(2, "Cache: Removing %s from cache", virtualfn)
                    self.clean.remove(virtualfn)
            if fn in self.clean:
                logger.debug(2, "Cache: Marking %s as not clean", fn)
                self.clean.remove(fn)
            return False

        self.clean.add(fn)
        return True

    def remove(self, fn):
        """
        Remove a fn from the cache
        Called from the parser in error cases
        """
        if fn in self.depends_cache:
            logger.debug(1, "Removing %s from cache", fn)
            del self.depends_cache[fn]
        if fn in self.clean:
            logger.debug(1, "Marking %s as unclean", fn)
            self.clean.remove(fn)

    def sync(self):
        """
        Save the cache
        Called from the parser when complete (or exiting)
        """

        if not self.has_cache:
            return

        if self.cacheclean:
            logger.debug(2, "Cache is clean, not saving.")
            return

        with open(self.cachefile, "wb") as cachefile:
            pickler = pickle.Pickler(cachefile, pickle.HIGHEST_PROTOCOL)
            pickler.dump(__cache_version__)
            pickler.dump(bb.__version__)
            for key, value in self.depends_cache.iteritems():
                pickler.dump(key)
                pickler.dump(value)

        del self.depends_cache

    @staticmethod
    def mtime(cachefile):
        return bb.parse.cached_mtime_noerror(cachefile)

    def add_info(self, filename, info, cacheData, parsed=None):
        cacheData.add_from_recipeinfo(filename, info)
        if not self.has_cache:
            return

        if 'SRCREVINACTION' not in info.pv and not info.nocache:
            if parsed:
                self.cacheclean = False
            self.depends_cache[filename] = info

    def add(self, file_name, data, cacheData, parsed=None):
        """
        Save data we need into the cache
        """

        realfn = self.virtualfn2realfn(file_name)[0]
        info = RecipeInfo.from_metadata(realfn, data)
        self.add_info(file_name, info, cacheData, parsed)

    @staticmethod
    def load_bbfile(bbfile, appends, config):
        """
        Load and parse one .bb build file
        Return the data and whether parsing resulted in the file being skipped
        """
        chdir_back = False

        from bb import data, parse

        # expand tmpdir to include this topdir
        data.setVar('TMPDIR', data.getVar('TMPDIR', config, 1) or "", config)
        bbfile_loc = os.path.abspath(os.path.dirname(bbfile))
        oldpath = os.path.abspath(os.getcwd())
        parse.cached_mtime_noerror(bbfile_loc)
        bb_data = data.init_db(config)
        # The ConfHandler first looks if there is a TOPDIR and if not
        # then it would call getcwd().
        # Previously, we chdir()ed to bbfile_loc, called the handler
        # and finally chdir()ed back, a couple of thousand times. We now
        # just fill in TOPDIR to point to bbfile_loc if there is no TOPDIR yet.
        if not data.getVar('TOPDIR', bb_data):
            chdir_back = True
            data.setVar('TOPDIR', bbfile_loc, bb_data)
        try:
            if appends:
                data.setVar('__BBAPPEND', " ".join(appends), bb_data)
            bb_data = parse.handle(bbfile, bb_data)
            if chdir_back:
                os.chdir(oldpath)
            return bb_data
        except:
            if chdir_back:
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
    return Cache(cooker.configuration.data)


class CacheData(object):
    """
    The data structures we compile from the cached data
    """

    def __init__(self):
        # Direct cache variables
        self.providers = defaultdict(list)
        self.rproviders = defaultdict(list)
        self.packages = defaultdict(list)
        self.packages_dynamic = defaultdict(list)
        self.possible_world = []
        self.pkg_pn = defaultdict(list)
        self.pkg_fn = {}
        self.pkg_pepvpr = {}
        self.pkg_dp = {}
        self.pn_provides = defaultdict(list)
        self.fn_provides = {}
        self.all_depends = []
        self.deps = defaultdict(list)
        self.rundeps = defaultdict(lambda: defaultdict(list))
        self.runrecs = defaultdict(lambda: defaultdict(list))
        self.task_queues = {}
        self.task_deps = {}
        self.stamp = {}
        self.stamp_extrainfo = {}
        self.preferred = {}
        self.tasks = {}
        self.basetaskhash = {}
        self.hashfn = {}
        self.inherits = {}
        self.summary = {}
        self.license = {}
        self.section = {}

        # Indirect Cache variables (set elsewhere)
        self.ignored_dependencies = []
        self.world_target = set()
        self.bbfile_priority = {}
        self.bbfile_config_priorities = []

    def add_from_recipeinfo(self, fn, info):
        self.task_deps[fn] = info.task_deps
        self.pkg_fn[fn] = info.pn
        self.pkg_pn[info.pn].append(fn)
        self.pkg_pepvpr[fn] = (info.pe, info.pv, info.pr)
        self.pkg_dp[fn] = info.defaultpref
        self.stamp[fn] = info.stamp
        self.stamp_extrainfo[fn] = info.stamp_extrainfo

        provides = [info.pn]
        for provide in info.provides:
            if provide not in provides:
                provides.append(provide)
        self.fn_provides[fn] = provides

        for provide in provides:
            self.providers[provide].append(fn)
            if provide not in self.pn_provides[info.pn]:
                self.pn_provides[info.pn].append(provide)

        for dep in info.depends:
            if dep not in self.deps[fn]:
                self.deps[fn].append(dep)
            if dep not in self.all_depends:
                self.all_depends.append(dep)

        rprovides = info.rprovides
        for package in info.packages:
            self.packages[package].append(fn)
            rprovides += info.rprovides_pkg[package]

        for rprovide in rprovides:
            self.rproviders[rprovide].append(fn)

        for package in info.packages_dynamic:
            self.packages_dynamic[package].append(fn)

        # Build hash of runtime depends and rececommends
        for package in info.packages + [info.pn]:
            self.rundeps[fn][package] = list(info.rdepends) + info.rdepends_pkg[package]
            self.runrecs[fn][package] = list(info.rrecommends) + info.rrecommends_pkg[package]

        # Collect files we may need for possible world-dep
        # calculations
        if not info.broken and not info.not_world:
            self.possible_world.append(fn)

        self.hashfn[fn] = info.hashfilename
        for task, taskhash in info.basetaskhashes.iteritems():
            identifier = '%s.%s' % (fn, task)
            self.basetaskhash[identifier] = taskhash

        self.inherits[fn] = info.inherits
        self.summary[fn] = info.summary
        self.license[fn] = info.license
        self.section[fn] = info.section
