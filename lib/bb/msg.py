#!/usr/bin/env python
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
from bb import utils

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
    'Provider',
    'RunQueue',
    'TaskData',
    'Util')

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
            std_warn("Logging domain %s is not valid, ignoring" % domain)

#
# Message handling functions
#

def debug(level, domain, msg, fn = None):
    if debug_level[domain] >= level:
        print 'DEBUG: ' + msg

def note(level, domain, msg, fn = None):
    if level == 1 or verbose or debug_level[domain] >= 1:
        std_note(msg)

def warn(domain, msg, fn = None):
    std_warn(msg)

def error(domain, msg, fn = None):
    std_error(msg)

def fatal(domain, msg, fn = None):
    std_fatal(msg)

#
# Compatibility functions for the original message interface
#
def std_debug(lvl, msg):
    if debug_level['default'] >= lvl:
        print 'DEBUG: ' + msg

def std_note(msg):
    print 'NOTE: ' + msg

def std_warn(msg):
    print 'WARNING: ' + msg

def std_error(msg):
    print 'ERROR: ' + msg

def std_fatal(msg):
    print 'ERROR: ' + msg
    sys.exit(1)
