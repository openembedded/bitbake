# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'msg' implementation

Message handling infrastructure for bitbake

"""

# Copyright (C) 2006        Richard Purdie
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

import sys, bb
import collections
from bb import event

debug_level = collections.defaultdict(lambda: 0)
verbose = False

def _NamedTuple(name, fields):
    Tuple = collections.namedtuple(name, " ".join(fields))
    return Tuple(*range(len(fields)))

domain = _NamedTuple("Domain",(
    "Default",
    "Build",
    "Cache",
    "Collection",
    "Data",
    "Depends",
    "Fetcher",
    "Parsing",
    "PersistData",
    "Provider",
    "RunQueue",
    "TaskData",
    "Util"))


class MsgBase(bb.event.Event):
    """Base class for messages"""

    def __init__(self, msg):
        self._message = msg
        event.Event.__init__(self)

class MsgDebug(MsgBase):
    """Debug Message"""

class MsgNote(MsgBase):
    """Note Message"""

class MsgWarn(MsgBase):
    """Warning Message"""

class MsgError(MsgBase):
    """Error Message"""

class MsgFatal(MsgBase):
    """Fatal Message"""

class MsgPlain(MsgBase):
    """General output"""

#
# Message control functions
#

def set_debug_level(level):
    for d in domain:
        debug_level[d] = level
    debug_level[domain.Default] = level

def get_debug_level(msgdomain = domain.Default):
    return debug_level[msgdomain]

def set_verbose(level):
    verbose = level

def set_debug_domains(strdomains):
    for domainstr in strdomains:
        for d in domain:
            if domain._fields[d] == domainstr:
                debug_level[d] += 1
                break
        else:
            warn(None, "Logging domain %s is not valid, ignoring" % domainstr)

#
# Message handling functions
#

def debug(level, msgdomain, msg, fn = None):
    if not msgdomain:
        msgdomain = domain.Default

    if debug_level[msgdomain] >= level:
        bb.event.fire(MsgDebug(msg), None)
        if not bb.event._ui_handlers:
            print 'DEBUG: ' + msg

def note(level, msgdomain, msg, fn = None):
    if not msgdomain:
        msgdomain = domain.Default

    if level == 1 or verbose or debug_level[msgdomain] >= 1:
        bb.event.fire(MsgNote(msg), None)
        if not bb.event._ui_handlers:
            print 'NOTE: ' + msg

def warn(msgdomain, msg, fn = None):
    bb.event.fire(MsgWarn(msg), None)
    if not bb.event._ui_handlers:
        print 'WARNING: ' + msg

def error(msgdomain, msg, fn = None):
    bb.event.fire(MsgError(msg), None)
    if not bb.event._ui_handlers:
        print 'ERROR: ' + msg

def fatal(msgdomain, msg, fn = None):
    bb.event.fire(MsgFatal(msg), None)
    if not bb.event._ui_handlers:
        print 'FATAL: ' + msg
    sys.exit(1)

def plain(msg, fn = None):
    bb.event.fire(MsgPlain(msg), None)
    if not bb.event._ui_handlers:
        print msg
