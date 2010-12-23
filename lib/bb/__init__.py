# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Build System Python Library
#
# Copyright (C) 2003  Holger Schurig
# Copyright (C) 2003, 2004  Chris Larson
#
# Based on Gentoo's portage.py.
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

__version__ = "1.10.2"

__all__ = [

    "debug",
    "note",
    "error",
    "fatal",

    "mkdirhier",
    "movefile",
    "vercmp",

# fetch
    "decodeurl",
    "encodeurl",

# modules
    "parse",
    "data",
    "command",
    "event",
    "build",
    "fetch",
    "manifest",
    "methodpool",
    "cache",
    "runqueue",
    "taskdata",
    "providers",
 ]

import sys, os, types, re, string

if "BBDEBUG" in os.environ:
    level = int(os.environ["BBDEBUG"])
    if level:
        bb.msg.set_debug_level(level)


# Messaging convenience functions
def plain(*args):
    bb.msg.plain(''.join(args))

def debug(lvl, *args):
    bb.msg.debug(lvl, None, ''.join(args))

def note(*args):
    bb.msg.note(1, None, ''.join(args))

def warn(*args):
    bb.msg.warn(None, ''.join(args))

def error(*args):
    bb.msg.error(None, ''.join(args))

def fatal(*args):
    bb.msg.fatal(None, ''.join(args))


# For compatibility
from bb.fetch import MalformedUrl, encodeurl, decodeurl
from bb.data import VarExpandError
from bb.utils import mkdirhier, movefile, copyfile, which
from bb.utils import vercmp_string as vercmp


if __name__ == "__main__":
    import doctest, bb
    bb.msg.set_debug_level(0)
    doctest.testmod(bb)
