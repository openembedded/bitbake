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

__version__ = "1.11.0"

import sys
if sys.version_info < (2, 6, 0):
    raise RuntimeError("Sorry, python 2.6.0 or later is required for this version of bitbake")

import os
import logging
import bb.msg

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

logging.raiseExceptions = False
logger = logging.getLogger("BitBake")
logger.addHandler(NullHandler())
logger.setLevel(logging.INFO)

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


def deprecated(func, name = None, advice = ""):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emmitted
    when the function is used."""
    import warnings

    if advice:
        advice = ": %s" % advice
    if name is None:
        name = func.__name__

    def newFunc(*args, **kwargs):
        warnings.warn("Call to deprecated function %s%s." % (name,
                                                             advice),
                      category = PendingDeprecationWarning,
                      stacklevel = 2)
        return func(*args, **kwargs)
    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc

# For compatibility
def deprecate_import(current, modulename, fromlist, renames = None):
    """Import objects from one module into another, wrapping them with a DeprecationWarning"""
    import sys

    module = __import__(modulename, fromlist = fromlist)
    for position, objname in enumerate(fromlist):
        obj = getattr(module, objname)
        newobj = deprecated(obj, "{0}.{1}".format(current, objname),
                            "Please use {0}.{1} instead".format(modulename, objname))
        if renames:
            newname = renames[position]
        else:
            newname = objname

        setattr(sys.modules[current], newname, newobj)

deprecate_import(__name__, "bb.fetch", ("MalformedUrl", "encodeurl", "decodeurl"))
deprecate_import(__name__, "bb.utils", ("mkdirhier", "movefile", "copyfile", "which"))
deprecate_import(__name__, "bb.utils", ["vercmp_string"], ["vercmp"])
