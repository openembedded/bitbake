#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
OpenEmbedded Parsers

File parsers for the OpenEmbedded
(http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""
__version__ = '1.0'

__all__ = [ 'handlers', 'supports', 'handle', 'init', 'ConfHandler', 'OEHandler', 'SRPMHandler', 'ParseError' ]
handlers = []

class ParseError(Exception):
    """Exception raised when parsing fails"""

class SkipPackage(Exception):
    """Exception raised to skip this package"""

import ConfHandler
ConfHandler.ParseError = ParseError
import OEHandler
OEHandler.ParseError = ParseError
import SRPMHandler
SRPMHandler.ParseError = ParseError

__mtime_cache = {}

def cached_mtime(f):
    import os
    if not __mtime_cache.has_key(f):
        __mtime_cache[f] = os.stat(f)[8]
    return __mtime_cache[f]

def mark_dependency(d, f):
    import oe, os
    if f.startswith('./'):
        f = "%s/%s" % (os.getcwd(), f[2:])
    deps = (oe.data.getVar('__depends', d) or "").split()
    deps.append("%s@%s" % (f, cached_mtime(f)))
    oe.data.setVar('__depends', " ".join(deps), d)

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
    return None

def init(fn, data):
    for h in handlers:
        if h['supports'](fn):
            return h['init'](data)
