#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
   class for handling configuration data files

   Reads a .conf file and obtains its metadata

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

import re, bb.data, os
import logging
import bb.utils
from bb.parse import ParseError, resolve_file, ast, logger

#__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}]+)\s*(?P<colon>:)?(?P<ques>\?)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}/]+)(\[(?P<flag>[a-zA-Z0-9\-_+.]+)\])?\s*((?P<colon>:=)|(?P<lazyques>\?\?=)|(?P<ques>\?=)|(?P<append>\+=)|(?P<prepend>=\+)|(?P<predot>=\.)|(?P<postdot>\.=)|=)\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__include_regexp__ = re.compile( r"include\s+(.+)" )
__require_regexp__ = re.compile( r"require\s+(.+)" )
__export_regexp__ = re.compile( r"export\s+(.+)" )

def init(data):
    topdir = bb.data.getVar('TOPDIR', data)
    if not topdir:
        bb.data.setVar('TOPDIR', os.getcwd(), data)


def supports(fn, d):
    return fn[-5:] == ".conf"

def include(oldfn, fn, data, error_out):
    """
    error_out If True a ParseError will be raised if the to be included
    config-files could not be included.
    """
    if oldfn == fn: # prevent infinite recursion
        return None

    import bb
    fn = bb.data.expand(fn, data)
    oldfn = bb.data.expand(oldfn, data)

    if not os.path.isabs(fn):
        dname = os.path.dirname(oldfn)
        bbpath = "%s:%s" % (dname, bb.data.getVar("BBPATH", data, 1))
        abs_fn = bb.utils.which(bbpath, fn)
        if abs_fn:
            fn = abs_fn

    from bb.parse import handle
    try:
        ret = handle(fn, data, True)
    except IOError:
        if error_out:
            raise ParseError("Could not %(error_out)s file %(fn)s" % vars() )
        logger.debug(2, "CONF file '%s' not found", fn)

def handle(fn, data, include):
    init(data)

    if include == 0:
        oldfile = None
    else:
        oldfile = bb.data.getVar('FILE', data)

    abs_fn = resolve_file(fn, data)
    f = open(abs_fn, 'r')

    if include:
        bb.parse.mark_dependency(data, abs_fn)

    statements = ast.StatementGroup()
    lineno = 0
    while True:
        lineno = lineno + 1
        s = f.readline()
        if not s: break
        w = s.strip()
        if not w: continue          # skip empty lines
        s = s.rstrip()
        if s[0] == '#': continue    # skip comments
        while s[-1] == '\\':
            s2 = f.readline().strip()
            lineno = lineno + 1
            s = s[:-1] + s2
        feeder(lineno, s, fn, statements)

    # DONE WITH PARSING... time to evaluate
    bb.data.setVar('FILE', abs_fn, data)
    statements.eval(data)
    if oldfile:
        bb.data.setVar('FILE', oldfile, data)

    return data

def feeder(lineno, s, fn, statements):
    m = __config_regexp__.match(s)
    if m:
        groupd = m.groupdict()
        ast.handleData(statements, fn, lineno, groupd)
        return

    m = __include_regexp__.match(s)
    if m:
        ast.handleInclude(statements, fn, lineno, m, False)
        return

    m = __require_regexp__.match(s)
    if m:
        ast.handleInclude(statements, fn, lineno, m, True)
        return

    m = __export_regexp__.match(s)
    if m:
        ast.handleExport(statements, fn, lineno, m)
        return

    raise ParseError("%s:%d: unparsed line: '%s'" % (fn, lineno, s));

# Add us to the handlers list
from bb.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
