#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
OpenEmbedded 'Make' implementations

Functions for reading OE files, building a dependency graph and
building a set of OE files while walking along the dependency graph.

This file is part of the OpenEmbedded (http://openembedded.org) build infrastructure.
"""

from oe import debug, digraph, data, fetch, fatal, error, note, event, parse
import copy, oe, re, sys, os, glob
try:
    import cPickle as pickle
except ImportError:
    import pickle
    print "NOTE: Importing cPickle failed. Falling back to a very slow implementation."

pkgdata = {}
cfg = {}
cache = None
digits = "0123456789"
ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
mtime_cache = {}

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

def deps_clean(d):
    depstr = data.getVar('__depends', d)
    if depstr:
        deps = depstr.split(" ")
        for dep in deps:
            (f,old_mtime_s) = dep.split("@")
            old_mtime = int(old_mtime_s)
            new_mtime = parse.cached_mtime(f)
            if (new_mtime > old_mtime):
                return False
    return True

def load_oefile( oefile ):
    """Load and parse one .oe build file"""

    if cache is not None:
        cache_oefile = oefile.replace( '/', '_' )

        try:
            cache_mtime = os.stat( "%s/%s" % ( cache, cache_oefile ) )[8]
        except OSError:
            cache_mtime = 0
        file_mtime = parse.cached_mtime(oefile)

        if file_mtime > cache_mtime:
            #print " : '%s' dirty. reparsing..." % oefile
            pass
        else:
            #print " : '%s' clean. loading from cache..." % oefile
            cache_data = unpickle_oe( cache_oefile )
            if deps_clean(cache_data):
                return cache_data

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
        if cache is not None: pickle_oe( cache_oefile, oe) # write cache
        os.chdir(oldpath)
        return oe
    finally:
        os.chdir(oldpath)

def pickle_oe( oefile, oe ):
    p = pickle.Pickler( file( "%s/%s" % ( cache, oefile ), "wb" ), -1 )
    p.dump( oe )

def unpickle_oe( oefile ):
    p = pickle.Unpickler( file( "%s/%s" % ( cache, oefile ), "rb" ) )
    return p.load()

def collect_oefiles( progressCallback ):
    """Collect all available .oe build files"""

    global cache
    cache = oe.data.getVar( "CACHE", cfg, 1 )
    if cache is not None:
        print "NOTE: Using cache in '%s'" % cache
        try:
            os.stat( cache )
        except OSError:
            oe.mkdirhier( cache )
    else: print "NOTE: Not using a cache. Set CACHE = <directory> to enable."
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

        progressCallback( i + 1, len( newfiles ), f )
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
        except IOError, e:
            oe.error("opening %s: %s" % (f, e))
            pass
        except oe.parse.SkipPackage:
            pass

def explode_version(s):
    import string
    r = []
    alpha_regexp = re.compile('^([a-zA-Z]+)(.*)$')
    numeric_regexp = re.compile('^(\d+)(.*)$')
    while (s != ''):
        if s[0] in digits:
            m = numeric_regexp.match(s)
            r.append(int(m.group(1)))
            s = m.group(2)
            continue
        if s[0] in ascii_letters:
            m = alpha_regexp.match(s)
            r.append(m.group(1))
            s = m.group(2)
            continue
        s = s[1:]
    return r

def vercmp_part(a, b):
    va = explode_version(a)
    vb = explode_version(b)
    while True:
        if va == []:
            ca = None
        else:
            ca = va.pop(0)
        if vb == []:
            cb = None
        else:
            cb = vb.pop(0)
        if ca == None and cb == None:
            return 0
        if ca > cb:
            return 1
        if ca < cb:
            return -1

def vercmp(ta, tb):
    (va, ra) = ta
    (vb, rb) = tb

    r = vercmp_part(va, vb)
    if (r == 0):
        r = vercmp_part(ra, rb)
    return r
