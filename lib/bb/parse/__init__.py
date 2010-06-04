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

__all__ = [ 'ParseError', 'SkipPackage', 'cached_mtime', 'mark_dependency',
            'supports', 'handle', 'init' ]
handlers = []

import bb, os

class ParseError(Exception):
    """Exception raised when parsing fails"""

class SkipPackage(Exception):
    """Exception raised to skip this package"""

__mtime_cache = {}
def cached_mtime(f):
    if not __mtime_cache.has_key(f):
        __mtime_cache[f] = os.stat(f)[8]
    return __mtime_cache[f]

def cached_mtime_noerror(f):
    if not __mtime_cache.has_key(f):
        try:
            __mtime_cache[f] = os.stat(f)[8]
        except OSError:
            return 0
    return __mtime_cache[f]

def update_mtime(f):
    __mtime_cache[f] = os.stat(f)[8]
    return __mtime_cache[f]

def mark_dependency(d, f):
    if f.startswith('./'):
        f = "%s/%s" % (os.getcwd(), f[2:])
    deps = bb.data.getVar('__depends', d) or []
    deps.append( (f, cached_mtime(f)) )
    bb.data.setVar('__depends', deps, d)

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
    raise ParseError("%s is not a BitBake file" % fn)

def init(fn, data):
    for h in handlers:
        if h['supports'](fn):
            return h['init'](data)

def resolve_file(fn, d):
    if not os.path.isabs(fn):
        bbpath = bb.data.getVar("BBPATH", d, True)
        newfn = bb.which(bbpath, fn)
        if not newfn:
            raise IOError("file %s not found in %s" % (fn, bbpath))
        fn = newfn

    bb.msg.debug(2, bb.msg.domain.Parsing, "LOAD %s" % fn)
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
        raise ParseError("Unable to generate default variables from the filename: %s (too many underscores)" % mypkg)
    exp = 3 - len(parts)
    tmplist = []
    while exp != 0:
        exp -= 1
        tmplist.append(None)
    parts.extend(tmplist)
    return parts

from bb.parse.parse_py import __version__, ConfHandler, BBHandler
