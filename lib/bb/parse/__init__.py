"""
BitBake Parsers

File parsers for the BitBake build tools.

Copyright (C) 2003, 2004  Chris Larson
Copyright (C) 2003, 2004  Phil Blundell

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

Based on functions from the base bb module, Copyright 2003 Holger Schurig
"""

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
        update_mtime(f)
    return __mtime_cache[f]

def update_mtime(f):
    __mtime_cache[f] = os.stat(f)[8]

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


from parse_py import __version__, ConfHandler, BBHandler
