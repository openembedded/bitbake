"""
BitBake Parsers

File parsers for the BitBake build tools.

"""


# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
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
#
# Based on functions from the base bb module, Copyright 2003 Holger Schurig

handlers = []

import os
import stat
import logging
import bb
import bb.utils
import bb.siggen

logger = logging.getLogger("BitBake.Parsing")

class ParseError(Exception):
    """Exception raised when parsing fails"""
    def __init__(self, msg, filename, lineno=0):
        self.msg = msg
        self.filename = filename
        self.lineno = lineno
        Exception.__init__(self, msg, filename, lineno)

    def __str__(self):
        if self.lineno:
            return "ParseError at %s:%d: %s" % (self.filename, self.lineno, self.msg)
        else:
            return "ParseError in %s: %s" % (self.filename, self.msg)

class SkipPackage(Exception):
    """Exception raised to skip this package"""

__mtime_cache = {}
def cached_mtime(f):
    if f not in __mtime_cache:
        __mtime_cache[f] = os.stat(f)[stat.ST_MTIME]
    return __mtime_cache[f]

def cached_mtime_noerror(f):
    if f not in __mtime_cache:
        try:
            __mtime_cache[f] = os.stat(f)[stat.ST_MTIME]
        except OSError:
            return 0
    return __mtime_cache[f]

def update_mtime(f):
    __mtime_cache[f] = os.stat(f)[stat.ST_MTIME]
    return __mtime_cache[f]

def mark_dependency(d, f):
    if f.startswith('./'):
        f = "%s/%s" % (os.getcwd(), f[2:])
    deps = d.getVar('__depends') or set()
    deps.update([(f, cached_mtime(f))])
    d.setVar('__depends', deps)

def supports(fn, data):
    """Returns true if we have a handler for this file, false otherwise"""
    for h in handlers:
        if h['supports'](fn, data):
            return 1
    return 0

def handle(fn, data, include = 0):
    """Call the handler that is appropriate for this file"""
    for h in handlers:
        if h['supports'](fn, data):
            return h['handle'](fn, data, include)
    raise ParseError("not a BitBake file", fn)

def init(fn, data):
    for h in handlers:
        if h['supports'](fn):
            return h['init'](data)

def init_parser(d):
    bb.parse.siggen = bb.siggen.init(d)

def resolve_file(fn, d):
    if not os.path.isabs(fn):
        bbpath = d.getVar("BBPATH", True)
        newfn = bb.utils.which(bbpath, fn)
        if not newfn:
            raise IOError("file %s not found in %s" % (fn, bbpath))
        fn = newfn

    logger.debug(2, "LOAD %s", fn)
    return fn

# Used by OpenEmbedded metadata
__pkgsplit_cache__={}
def vars_from_file(mypkg, d):
    if not mypkg:
        return (None, None, None)
    if mypkg in __pkgsplit_cache__:
        return __pkgsplit_cache__[mypkg]

    myfile = os.path.splitext(os.path.basename(mypkg))
    parts = myfile[0].split('_')
    __pkgsplit_cache__[mypkg] = parts
    if len(parts) > 3:
        raise ParseError("Unable to generate default variables from filename (too many underscores)", mypkg)
    exp = 3 - len(parts)
    tmplist = []
    while exp != 0:
        exp -= 1
        tmplist.append(None)
    parts.extend(tmplist)
    return parts

def get_file_depends(d):
    '''Return the dependent files'''
    dep_files = []
    depends = d.getVar('__depends', True) or set()
    depends = depends.union(d.getVar('__base_depends', True) or set())
    for (fn, _) in depends:
        dep_files.append(os.path.abspath(fn))
    return " ".join(dep_files)

from bb.parse.parse_py import __version__, ConfHandler, BBHandler
