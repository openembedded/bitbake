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

import re, bb.data, os, sys
from bb.parse import ParseError, resolve_file

#__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}]+)\s*(?P<colon>:)?(?P<ques>\?)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}/]+)(\[(?P<flag>[a-zA-Z0-9\-_+.]+)\])?\s*((?P<colon>:=)|(?P<ques>\?=)|(?P<append>\+=)|(?P<prepend>=\+)|(?P<predot>=\.)|(?P<postdot>\.=)|=)\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__include_regexp__ = re.compile( r"include\s+(.+)" )
__require_regexp__ = re.compile( r"require\s+(.+)" )
__export_regexp__ = re.compile( r"export\s+(.+)" )

def init(data):
    topdir = bb.data.getVar('TOPDIR', data)
    if not topdir:
        topdir = os.getcwd()
        bb.data.setVar('TOPDIR', topdir, data)
    if not bb.data.getVar('BBPATH', data):
        from pkg_resources import Requirement, resource_filename
        bitbake = Requirement.parse("bitbake")
        datadir = resource_filename(bitbake, "../share/bitbake")
        basedir = resource_filename(bitbake, "..")
        bb.data.setVar('BBPATH', '%s:%s:%s' % (topdir, datadir, basedir), data)


def supports(fn, d):
    return fn[-5:] == ".conf"

def include(oldfn, fn, data, error_out):
    """

    error_out If True a ParseError will be reaised if the to be included
    """
    if oldfn == fn: # prevent infinate recursion
        return None

    import bb
    fn = bb.data.expand(fn, data)
    oldfn = bb.data.expand(oldfn, data)

    if not os.path.isabs(fn):
        dname = os.path.dirname(oldfn)
        bbpath = "%s:%s" % (dname, bb.data.getVar("BBPATH", data, 1))
        abs_fn = bb.which(bbpath, fn)
        if abs_fn:
            fn = abs_fn

    from bb.parse import handle
    try:
        ret = handle(fn, data, True)
    except IOError:
        if error_out:
            raise ParseError("Could not %(error_out)s file %(fn)s" % vars() )
        bb.msg.debug(2, bb.msg.domain.Parsing, "CONF file '%s' not found" % fn)

def handle(fn, data, include = 0):
    init(data)

    if include == 0:
        oldfile = None
    else:
        oldfile = bb.data.getVar('FILE', data)

    (f, abs_fn) = resolve_file(fn, data)

    if include:
        bb.parse.mark_dependency(data, abs_fn)

    lineno = 0
    bb.data.setVar('FILE', fn, data)
    while 1:
        lineno = lineno + 1
        s = f.readline()
        if not s: break
        w = s.strip()
        if not w: continue          # skip empty lines
        s = s.rstrip()
        if s[0] == '#': continue    # skip comments
        while s[-1] == '\\':
            s2 = f.readline()[:-1].strip()
            lineno = lineno + 1
            s = s[:-1] + s2
        feeder(lineno, s, fn, data)

    if oldfile:
        bb.data.setVar('FILE', oldfile, data)
    return data

def feeder(lineno, s, fn, data):
    def getFunc(groupd, key, data):
        if 'flag' in groupd and groupd['flag'] != None:
            return bb.data.getVarFlag(key, groupd['flag'], data)
        else:
            return bb.data.getVar(key, data)

    m = __config_regexp__.match(s)
    if m:
        groupd = m.groupdict()
        key = groupd["var"]
        if "exp" in groupd and groupd["exp"] != None:
            bb.data.setVarFlag(key, "export", 1, data)
        if "ques" in groupd and groupd["ques"] != None:
            val = getFunc(groupd, key, data)
            if val == None:
                val = groupd["value"]
        elif "colon" in groupd and groupd["colon"] != None:
            e = data.createCopy()
            bb.data.update_data(e)
            val = bb.data.expand(groupd["value"], e)
        elif "append" in groupd and groupd["append"] != None:
            val = "%s %s" % ((getFunc(groupd, key, data) or ""), groupd["value"])
        elif "prepend" in groupd and groupd["prepend"] != None:
            val = "%s %s" % (groupd["value"], (getFunc(groupd, key, data) or ""))
        elif "postdot" in groupd and groupd["postdot"] != None:
            val = "%s%s" % ((getFunc(groupd, key, data) or ""), groupd["value"])
        elif "predot" in groupd and groupd["predot"] != None:
            val = "%s%s" % (groupd["value"], (getFunc(groupd, key, data) or ""))
        else:
            val = groupd["value"]
        if 'flag' in groupd and groupd['flag'] != None:
            bb.msg.debug(3, bb.msg.domain.Parsing, "setVarFlag(%s, %s, %s, data)" % (key, groupd['flag'], val))
            bb.data.setVarFlag(key, groupd['flag'], val, data)
        else:
            bb.data.setVar(key, val, data)
        return

    m = __include_regexp__.match(s)
    if m:
        s = bb.data.expand(m.group(1), data)
        bb.msg.debug(3, bb.msg.domain.Parsing, "CONF %s:%d: including %s" % (fn, lineno, s))
        include(fn, s, data, False)
        return

    m = __require_regexp__.match(s)
    if m:
        s = bb.data.expand(m.group(1), data)
        include(fn, s, data, "include required")
        return

    m = __export_regexp__.match(s)
    if m:
        bb.data.setVarFlag(m.group(1), "export", 1, data)
        return

    raise ParseError("%s:%d: unparsed line: '%s'" % (fn, lineno, s));

# Add us to the handlers list
from bb.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
