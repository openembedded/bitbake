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

import sys, os, re, bb
from bb import utils, event

debug_level = {}

verbose = False

domain = bb.utils.Enum(
    'Build',
    'Cache',
    'Collection',
    'Data',
    'Depends',
    'Fetcher',
    'Parsing',
    'PersistData',
    'Provider',
    'RunQueue',
    'TaskData',
    'Util')


class MsgBase(bb.event.Event):
    """Base class for messages"""

    def __init__(self, msg, d ):
        self._message = msg
        event.Event.__init__(self, d)

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
    bb.msg.debug_level = {}
    for domain in bb.msg.domain:
        bb.msg.debug_level[domain] = level
    bb.msg.debug_level['default'] = level

def set_verbose(level):
    bb.msg.verbose = level

def set_debug_domains(domains):
    for domain in domains:
        found = False
        for ddomain in bb.msg.domain:
            if domain == str(ddomain):
                bb.msg.debug_level[ddomain] = bb.msg.debug_level[ddomain] + 1
                found = True
        if not found:
            bb.msg.warn(None, "Logging domain %s is not valid, ignoring" % domain)

#
# Message handling functions
#

def debug(level, domain, msg, fn = None):
    bb.event.fire(MsgDebug(msg, None))
    if not domain:
        domain = 'default'
    if debug_level[domain] >= level:
        print 'DEBUG: ' + msg

def note(level, domain, msg, fn = None):
    bb.event.fire(MsgNote(msg, None))
    if not domain:
        domain = 'default'
    if level == 1 or verbose or debug_level[domain] >= 1:
        print 'NOTE: ' + msg

def warn(domain, msg, fn = None):
    bb.event.fire(MsgWarn(msg, None))
    print 'WARNING: ' + msg

def error(domain, msg, fn = None):
    bb.event.fire(MsgError(msg, None))
    print 'ERROR: ' + msg

def fatal(domain, msg, fn = None):
    bb.event.fire(MsgFatal(msg, None))
    print 'ERROR: ' + msg
    sys.exit(1)

def plain(msg, fn = None):
    bb.event.fire(MsgPlain(msg, None))
    print msg

