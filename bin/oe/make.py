#!/usr/bin/python
"""
OpenEmbedded 'Make' implementations

Functions for reading OE files, building a dependency graph and
building a set of OE files while walking along the dependency graph.

This file is part of the OpenEmbedded (http://openembedded.org) build infrastructure.
"""

from oe import debug, digraph, data, fetch, fatal, error, note, event, parse
import copy, oe, re, sys, os, glob

__build_cache_fail = []
__build_cache = []

# These variables are allowed to be reinitialized by client code
pkgdata = {}
pkgs = {}
cfg = {}
graph = digraph()

def buildPackage(graph, item):
    if item in __build_cache:
        return 1
    if item in __build_cache_fail:
        return 0
    fn = pkgs[item][1]
    if fn is None:
        return 1
    command = options.cmd
    debug(1, "oebuild %s %s" % (command, fn))
    event.fire(event.PkgStarted(item, pkgdata[fn]))
    try:
        oe.build.exec_task('do_%s' % command, pkgdata[fn])
        event.fire(event.PkgSucceeded(item, pkgdata[fn]))
        __build_cache.append(item)
        del pkgdata[fn]
        return 1
    except oe.build.FuncFailed:
        error("task stack execution failed")
        event.fire(event.PkgFailed(item, pkgdata[fn]))
        __build_cache_fail.append(item)
        del pkgdata[fn]
        return 0
    except oe.build.EventException:
        (type, value, traceback) = sys.exc_info()
        e = value.event
        error("%s event exception, aborting" % event.getName(e))
        event.fire(event.PkgFailed(item, pkgdata[fn]))
        __build_cache_fail.append(item)
        del pkgdata[fn]
        return 0

def get_oefiles( path = os.getcwd() ):
    """Get list of default .oe files by reading out the current directory"""
    contents = os.listdir(path)
    oefiles = []
    for f in contents:
        (root, ext) = os.path.splitext(f)
        if ext == ".oe":
            oefiles.append(os.path.abspath(os.path.join(os.getcwd(),f)))
    return oefiles

def find_oefiles( path ):
    """Find all the .oe files in a directory (uses find)"""
    findcmd = 'find ' + path + ' -name *.oe | grep -v SCCS/'
    try:
        finddata = os.popen(findcmd)
    except OSError:
        return []
    return finddata.readlines()

def load_oefile( oefile ):
    """Load and parse one .oe build file"""
    oepath = data.getVar('OEPATH', cfg)
    topdir = data.getVar('TOPDIR', cfg)
    if not topdir:
        topdir = os.path.abspath(os.getcwd())
        # set topdir to here
        data.setVar('TOPDIR', topdir, cfg)
    oefile = os.path.abspath(oefile)
    oefile_loc = os.path.abspath(os.path.dirname(oefile))
    # expand tmpdir to include this topdir
    data.setVar('TMPDIR', data.getVar('TMPDIR', cfg, 1) or "", cfg)
    # add topdir to oepath
    oepath += ":%s" % topdir
    # set topdir to location of .oe file
    topdir = oefile_loc
    #data.setVar('TOPDIR', topdir, cfg)
    # add that topdir to oepath
    oepath += ":%s" % topdir
    # go there
    oldpath = os.path.abspath(os.getcwd())
    os.chdir(topdir)
    data.setVar('OEPATH', oepath, cfg)
    oe = copy.deepcopy(cfg)
    try:
        parse.handle(oefile, oe) # read .oe data
        os.chdir(oldpath)
        return oe
    except IOError, OSError:
        os.chdir(oldpath)
        return None

def collect_oefiles( progressCallback ):
    """Collect all available .oe build files"""

    files = (data.getVar( "OEFILES", cfg, 1 ) or "").split()
    data.setVar("OEFILES", " ".join(files), cfg)

    if not len(files):
        files = get_oefiles()

    if not len(files):
        oe.error("no files to build.")

    newfiles = []
    for f in files:
        if os.path.isdir(f):
            dirfiles = find_oefiles(f)
            if dirfiles:
                newfiles += dirfiles
                continue
    newfiles += glob.glob(f) or [ f ]

    for i in xrange( len( newfiles ) ):
        f = newfiles[i]
        oemask = oe.data.getVar('OEMASK', cfg, 1)
        if oemask:
            if re.search(oemask, f):
                oe.debug(1, "oemake: skipping %s" % f)
                continue

        progressCallback( i, len( newfiles ), f )
        debug(1, "oemake: parsing %s" % f)

        # read a file's metadata
        try:
            pkgdata[f] = load_oefile(f)
            deps = None
            if pkgdata[f] is not None:
                # allow metadata files to add items to OEFILES
                #data.update_data(pkgdata[f])
                addoefiles = data.getVar('OEFILES', pkgdata[f]) or None
                if addoefiles:
                    for aof in addoefiles.split():
                        if not files.count(aof):
                            if not os.path.isabs(aof):
                                aof = os.path.join(os.path.dirname(f),aof)
                            files.append(aof)
                for var in pkgdata[f].keys():
                    if data.getVarFlag(var, "handler", pkgdata[f]) and data.getVar(var, pkgdata[f]):
                        event.register(data.getVar(var, pkgdata[f]))
                depstr = data.getVar("DEPENDS", pkgdata[f], 1)
                if depstr is not None:
                    deps = depstr.split()
                pkg = []
                pkg.append(data.getVar('CATEGORY', pkgdata[f], 1))
                pkg.append(data.getVar('PN', pkgdata[f], 1))
                pkg.append(data.getVar('PV', pkgdata[f], 1))
                pkg.append(data.getVar('PR', pkgdata[f], 1))
                root = "%s/%s-%s-%s" % (pkg[0], pkg[1], pkg[2], pkg[3])
                provides = []
                providestr = data.getVar("PROVIDES", pkgdata[f], 1)
                if providestr is not None:
                    provides += providestr.split()
                for provide in provides:
                    pkgs[provide] = [[root], None]
                pkgs[root] = [deps, f]
        except IOError:
            oe.error("opening %s" % f)
            pass

def build_depgraph( depcmd ):
    # add every provide relationship to the dependency graph, depending
    # on all the packages that provide it

    tokill = []
    unsatisfied = []

    for pkg in pkgs.keys():
        graph.addnode(pkg, None)

    for pkg in pkgs.keys():
        (deps, fn) = pkgs[pkg]
        if depcmd is not None:
            if deps is not None:
                for d in deps:
                    if not graph.hasnode(d):
                        def killitem(graph, item):
                            tokill.append(item)
                        graph.walkup(pkg, killitem)
                        unsatisfied.append([pkg, d])
                        break
                    graph.addnode(pkg, d)

    for u in unsatisfied:
        event.fire(event.UnsatisfiedDep(u[0], pkgdata[pkgs[u[0]][1]], u[1]))

    for k in tokill:
        def reallykillitem(graph, item):
            graph.delnode(item)
        graph.walkup(k, reallykillitem)

