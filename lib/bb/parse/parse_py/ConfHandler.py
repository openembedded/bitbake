#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""class for handling configuration data files

   Reads a .conf file and obtains its metadata

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
   Place, Suite 330, Boston, MA 02111-1307 USA.""" 

import re, bb.data, os, sys
from bb import debug, fatal
from bb.parse import ParseError

#__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}]+)\s*(?P<colon>:)?(?P<ques>\?)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_+.${}/]+)(\[(?P<flag>[a-zA-Z0-9\-_+.]+)\])?\s*((?P<colon>:=)|(?P<ques>\?=)|(?P<append>\+=)|(?P<prepend>=\+)|(?P<predot>=\.)|(?P<postdot>\.=)|=)\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__include_regexp__ = re.compile( r"include\s+(.+)" )
__require_regexp__ = re.compile( r"require\s+(.+)" )

def init(data):
    if not bb.data.getVar('TOPDIR', data):
        bb.data.setVar('TOPDIR', os.getcwd(), data)
    if not bb.data.getVar('BBPATH', data):
        bb.data.setVar('BBPATH', os.path.join(sys.prefix, 'share', 'bitbake'), data)

def supports(fn, d):
    return localpath(fn, d)[-5:] == ".conf"

def localpath(fn, d):
    if os.path.exists(fn):
        return fn

    localfn = None
    try:
        localfn = bb.fetch.localpath(fn, d)
    except bb.MalformedUrl:
        pass

    if not localfn:
        localfn = fn
    return localfn

def obtain(fn, data = bb.data.init()):
    import sys, bb
    fn = bb.data.expand(fn, data)
    localfn = bb.data.expand(localpath(fn, data), data)

    if localfn != fn:
        dldir = bb.data.getVar('DL_DIR', data, 1)
        if not dldir:
            debug(1, "obtain: DL_DIR not defined")
            return localfn
        bb.mkdirhier(dldir)
        try:
            bb.fetch.init([fn])
        except bb.fetch.NoMethodError:
            (type, value, traceback) = sys.exc_info()
            debug(1, "obtain: no method: %s" % value)
            return localfn

        try:
            bb.fetch.go(data)
        except bb.fetch.MissingParameterError:
            (type, value, traceback) = sys.exc_info()
            debug(1, "obtain: missing parameters: %s" % value)
            return localfn
        except bb.fetch.FetchError:
            (type, value, traceback) = sys.exc_info()
            debug(1, "obtain: failed: %s" % value)
            return localfn
    return localfn


def include(oldfn, fn, data = bb.data.init(), error_out = False):
    """

    error_out If True a ParseError will be reaised if the to be included
    """
    if oldfn == fn: # prevent infinate recursion
        return None

    import bb
    fn = bb.data.expand(fn, data)
    oldfn = bb.data.expand(oldfn, data)

    from bb.parse import handle
    try:
        ret = handle(fn, data, True)
    except IOError:
        if error_out:
            raise ParseError("Could not include required file %(fn)s" % vars() )
        debug(2, "CONF file '%s' not found" % fn)

def handle(fn, data = bb.data.init(), include = 0):
    if include:
        inc_string = "including"
    else:
        inc_string = "reading"
    init(data)

    if include == 0:
        bb.data.inheritFromOS(data)
        oldfile = None
    else:
        oldfile = bb.data.getVar('FILE', data)

    fn = obtain(fn, data)
    bbpath = []
    if not os.path.isabs(fn):
        f = None
        vbbpath = bb.data.getVar("BBPATH", data)
        if vbbpath:
            bbpath += vbbpath.split(":")
        for p in bbpath:
            currname = os.path.join(bb.data.expand(p, data), fn)
            if os.access(currname, os.R_OK):
                f = open(currname, 'r')
                abs_fn = currname
                debug(1, "CONF %s %s" % (inc_string, currname))
                break
        if f is None:
            raise IOError("file '%s' not found" % fn)
    else:
        f = open(fn,'r')
        debug(1, "CONF %s %s" % (inc_string,fn))
        abs_fn = fn

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

def feeder(lineno, s, fn, data = bb.data.init()):
    m = __config_regexp__.match(s)
    if m:
        groupd = m.groupdict()
        key = groupd["var"]
        if "exp" in groupd and groupd["exp"] != None:
            bb.data.setVarFlag(key, "export", 1, data)
        if "ques" in groupd and groupd["ques"] != None:
            val = bb.data.getVar(key, data)
            if val == None:
                val = groupd["value"]
        elif "colon" in groupd and groupd["colon"] != None:
            val = bb.data.expand(groupd["value"], data)
        elif "append" in groupd and groupd["append"] != None:
            val = "%s %s" % ((bb.data.getVar(key, data) or ""), groupd["value"])
        elif "prepend" in groupd and groupd["prepend"] != None:
            val = "%s %s" % (groupd["value"], (bb.data.getVar(key, data) or ""))
        elif "postdot" in groupd and groupd["postdot"] != None:
            val = "%s%s" % ((bb.data.getVar(key, data) or ""), groupd["value"])
        elif "predot" in groupd and groupd["predot"] != None:
            val = "%s%s" % (groupd["value"], (bb.data.getVar(key, data) or ""))
        else:
            val = groupd["value"]
        if 'flag' in groupd and groupd['flag'] != None:
#           bb.note("setVarFlag(%s, %s, %s, data)" % (key, groupd['flag'], val))
            bb.data.setVarFlag(key, groupd['flag'], val, data)
        else:
            bb.data.setVar(key, val, data)
        return

    m = __include_regexp__.match(s)
    if m:
        s = bb.data.expand(m.group(1), data)
#       debug(2, "CONF %s:%d: including %s" % (fn, lineno, s))
        include(fn, s, data)
        return

    m = __require_regexp__.match(s)
    if m:
        s = bb.data.expand(m.group(1), data)
        include(fn, s, data, True)
        return

    raise ParseError("%s:%d: unparsed line: '%s'" % (fn, lineno, s));

# Add us to the handlers list
from bb.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
