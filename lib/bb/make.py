# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Make' implementations

Functions for reading BB files, building a dependency graph and
building a set of BB files while walking along the dependency graph.

Copyright (C) 2003, 2004  Mickey Lauer
Copyright (C) 2003, 2004  Phil Blundell
Copyright (C) 2003, 2004  Chris Larson

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

This file is part of the BitBake build tools.
"""

from bb import debug, digraph, data, fetch, fatal, error, note, event, parse
import copy, bb, re, sys, os, glob, sre_constants
try:
    import cPickle as pickle
except ImportError:
    import pickle
    print "NOTE: Importing cPickle failed. Falling back to a very slow implementation."

pkgdata = {}
cfg = data.init()
cache = None
digits = "0123456789"
ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
mtime_cache = {}

def get_bbfiles( path = os.getcwd() ):
    """Get list of default .bb files by reading out the current directory"""
    contents = os.listdir(path)
    bbfiles = []
    for f in contents:
        (root, ext) = os.path.splitext(f)
        if ext == ".bb":
            bbfiles.append(os.path.abspath(os.path.join(os.getcwd(),f)))
    return bbfiles

def find_bbfiles( path ):
    """Find all the .bb files in a directory (uses find)"""
    findcmd = 'find ' + path + ' -name *.bb | grep -v SCCS/'
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

def load_bbfile( bbfile ):
    """Load and parse one .bb build file"""

    if not cache in [None, '']:
        cache_bbfile = bbfile.replace( '/', '_' )

        try:
            cache_mtime = os.stat( "%s/%s" % ( cache, cache_bbfile ) )[8]
        except OSError:
            cache_mtime = 0
        file_mtime = parse.cached_mtime(bbfile)

        if file_mtime > cache_mtime:
            #print " : '%s' dirty. reparsing..." % bbfile
            pass
        else:
            #print " : '%s' clean. loading from cache..." % bbfile
            cache_data = unpickle_bb( cache_bbfile )
            if deps_clean(cache_data):
                return cache_data, True

    topdir = data.getVar('TOPDIR', cfg)
    if not topdir:
        topdir = os.path.abspath(os.getcwd())
        # set topdir to here
        data.setVar('TOPDIR', topdir, cfg)
    bbfile = os.path.abspath(bbfile)
    bbfile_loc = os.path.abspath(os.path.dirname(bbfile))
    # expand tmpdir to include this topdir
    data.setVar('TMPDIR', data.getVar('TMPDIR', cfg, 1) or "", cfg)
    # set topdir to location of .bb file
    topdir = bbfile_loc
    #data.setVar('TOPDIR', topdir, cfg)
    # go there
    oldpath = os.path.abspath(os.getcwd())
    os.chdir(topdir)
    bb = data.createCopy(cfg)
    try:
        parse.handle(bbfile, bb) # read .bb data
        if not cache in [None, '']: pickle_bb( cache_bbfile, bb) # write cache
        os.chdir(oldpath)
        return bb, False
    finally:
        os.chdir(oldpath)

def pickle_bb( bbfile, bb ):
    p = pickle.Pickler( file( "%s/%s" % ( cache, bbfile ), "wb" ), -1 )
    p.dump( bb )

def unpickle_bb( bbfile ):
    p = pickle.Unpickler( file( "%s/%s" % ( cache, bbfile ), "rb" ) )
    bb = p.load()
    funcstr = data.getVar('__functions__', bb)
    if funcstr:
        comp = compile(funcstr, "<pickled>", "exec")
        exec comp in __builtins__
    return bb

def collect_bbfiles( progressCallback ):
    """Collect all available .bb build files"""

    parsed, cached, skipped, masked = 0, 0, 0, 0
    global cache
    cache = bb.data.getVar( "CACHE", cfg, 1 )
    if not cache in [None, '']:
        print "NOTE: Using cache in '%s'" % cache
        try:
            os.stat( cache )
        except OSError:
            bb.mkdirhier( cache )
    else: print "NOTE: Not using a cache. Set CACHE = <directory> to enable."
    files = (data.getVar( "BBFILES", cfg, 1 ) or "").split()
    data.setVar("BBFILES", " ".join(files), cfg)

    if not len(files):
        files = get_bbfiles()

    if not len(files):
        bb.error("no files to build.")

    newfiles = []
    for f in files:
        if os.path.isdir(f):
            dirfiles = find_bbfiles(f)
            if dirfiles:
                newfiles += dirfiles
                continue
        newfiles += glob.glob(f) or [ f ]

    bbmask = bb.data.getVar('BBMASK', cfg, 1) or ""
    try:
        bbmask_compiled = re.compile(bbmask)
    except sre_constants.error:
        bb.fatal("BBMASK is not a valid regular expression.")

    for i in xrange( len( newfiles ) ):
        f = newfiles[i]
        if bbmask and bbmask_compiled.search(f):
              bb.debug(1, "bbmake: skipping %s" % f)
              masked += 1
              continue
        progressCallback( i + 1, len( newfiles ), f )
        debug(1, "bbmake: parsing %s" % f)

        # read a file's metadata
        try:
            pkgdata[f], fromCache = load_bbfile(f)
            if fromCache: cached += 1
            else: parsed += 1
            deps = None
            if pkgdata[f] is not None:
                # allow metadata files to add items to BBFILES
                #data.update_data(pkgdata[f])
                addbbfiles = data.getVar('BBFILES', pkgdata[f]) or None
                if addbbfiles:
                    for aof in addbbfiles.split():
                        if not files.count(aof):
                            if not os.path.isabs(aof):
                                aof = os.path.join(os.path.dirname(f),aof)
                            files.append(aof)
                for var in pkgdata[f].keys():
                    if data.getVarFlag(var, "handler", pkgdata[f]) and data.getVar(var, pkgdata[f]):
                        event.register(data.getVar(var, pkgdata[f]))
        except IOError, e:
            bb.error("opening %s: %s" % (f, e))
            pass
        except bb.parse.SkipPackage:
            skipped += 1
            pass
        except KeyboardInterrupt:
            raise
        except Exception, e:
            bb.error("%s while parsing %s" % (e, f))
    print "\rNOTE: Parsing finished. %d cached, %d parsed, %d skipped, %d masked." % ( cached, parsed, skipped, masked ), 

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
