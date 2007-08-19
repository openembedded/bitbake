# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Event' implementation

Classes and functions for manipulating 'events' in the
BitBake build tools.
"""

# Copyright (C) 2003, 2004  Chris Larson
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

import os, re
import bb.utils

class Event:
    """Base class for events"""
    type = "Event"

    def __init__(self, d):
        self._data = d

    def getData(self):
        return self._data

    def setData(self, data):
        self._data = data

    data = property(getData, setData, None, "data property")

NotHandled = 0
Handled = 1

Registered        = 10
AlreadyRegistered = 14

# Internal
_handlers = []
_handlers_dict = {}
_ui_handlers = {}
_ui_handler_seq = 0

def tmpHandler(event):
    """Default handler for code events"""
    return NotHandled

def defaultTmpHandler():
    tmp = "def tmpHandler(e):\n\t\"\"\"heh\"\"\"\n\treturn NotHandled"
    comp = bb.utils.better_compile(tmp, "tmpHandler(e)", "bb.event.defaultTmpHandler")
    return comp

def fire(event):
    """Fire off an Event"""
    databack = event.data
    databack1 = event._data
    event.data = None
    event._data = None

    errors = []
    for h in _ui_handlers:
        #print "Sending event %s" % event
        classid = "%s.%s" % (event.__class__.__module__, event.__class__.__name__)
        try:
            _ui_handlers[h].event.send((classid, event))
        except:
            errors.append(h)
    for h in errors:
        del _ui_handlers[h]

    event.data = databack
    event._data = databack1

    for h in _handlers:
        if type(h).__name__ == "code":
            exec(h)
            if tmpHandler(event) == Handled:
                return Handled
        else:
            if h(event) == Handled:
                return Handled
    return NotHandled

def register(name, handler):
    """Register an Event handler"""

    # already registered
    if name in _handlers_dict:
        return AlreadyRegistered

    if handler is not None:
#       handle string containing python code
        if type(handler).__name__ == "str":
            _registerCode(handler)
        else:
            _handlers.append(handler)

        _handlers_dict[name] = 1
        return Registered

def register_UIHhandler(handler):
    bb.event._ui_handler_seq = bb.event._ui_handler_seq + 1
    _ui_handlers[_ui_handler_seq] = handler
    return _ui_handler_seq

def unregister_UIHhandler(handlerNum):
    if handlerNum in _ui_handlers:
        del _ui_handlers[handlerNum]
    return

def _registerCode(handlerStr):
    """Register a 'code' Event.
       Deprecated interface; call register instead.

       Expects to be passed python code as a string, which will
       be passed in turn to compile() and then exec().  Note that
       the code will be within a function, so should have had
       appropriate tabbing put in place."""
    tmp = "def tmpHandler(e):\n%s" % handlerStr
    comp = bb.utils.better_compile(tmp, "tmpHandler(e)", "bb.event._registerCode")
#   prevent duplicate registration
    _handlers.append(comp)

def remove(name, handler):
    """Remove an Event handler"""

    _handlers_dict.pop(name)
    if type(handler).__name__ == "str":
        return _removeCode(handler)
    else:
        _handlers.remove(handler)

def _removeCode(handlerStr):
    """Remove a 'code' Event handler
       Deprecated interface; call remove instead."""
    tmp = "def tmpHandler(e):\n%s" % handlerStr
    comp = bb.utils.better_compile(tmp, "tmpHandler(e)", "bb.event._removeCode")
    _handlers.remove(comp)

def getName(e):
    """Returns the name of a class or class instance"""
    if getattr(e, "__name__", None) == None:
        return e.__class__.__name__
    else:
        return e.__name__

class ConfigParsed(Event):
    """Configuration Parsing Complete"""

class PkgBase(Event):
    """Base class for package events"""

    def __init__(self, t, d):
        self._pkg = t
        Event.__init__(self, d)
        self._message = "package %s: %s" % (bb.data.getVar("P", d, 1), getName(self)[3:])

    def getPkg(self):
        return self._pkg

    def setPkg(self, pkg):
        self._pkg = pkg

    pkg = property(getPkg, setPkg, None, "pkg property")


class BuildBase(Event):
    """Base class for bbmake run events"""

    def __init__(self, n, p, c, failures = 0):
        self._name = n
        self._pkgs = p
        Event.__init__(self, c)
        self._failures = failures

    def getPkgs(self):
        return self._pkgs

    def setPkgs(self, pkgs):
        self._pkgs = pkgs

    def getName(self):
        return self._name

    def setName(self, name):
        self._name = name

    def getCfg(self):
        return self.data

    def setCfg(self, cfg):
        self.data = cfg

    def getFailures(self):
        """
        Return the number of failed packages
        """
        return self._failures

    pkgs = property(getPkgs, setPkgs, None, "pkgs property")
    name = property(getName, setName, None, "name property")
    cfg = property(getCfg, setCfg, None, "cfg property")


class DepBase(PkgBase):
    """Base class for dependency events"""

    def __init__(self, t, data, d):
        self._dep = d
        PkgBase.__init__(self, t, data)

    def getDep(self):
        return self._dep

    def setDep(self, dep):
        self._dep = dep

    dep = property(getDep, setDep, None, "dep property")


class PkgStarted(PkgBase):
    """Package build started"""


class PkgFailed(PkgBase):
    """Package build failed"""


class PkgSucceeded(PkgBase):
    """Package build completed"""


class BuildStarted(BuildBase):
    """bbmake build run started"""


class BuildCompleted(BuildBase):
    """bbmake build run completed"""


class UnsatisfiedDep(DepBase):
    """Unsatisfied Dependency"""


class RecursiveDep(DepBase):
    """Recursive Dependency"""

class NoProvider(Event):
    """No Provider for an Event"""

    def __init__(self, item, data, runtime=False):
        Event.__init__(self, data)
        self._item = item
        self._runtime = runtime

    def getItem(self):
        return self._item

    def isRuntime(self):
        return self._runtime

class MultipleProviders(Event):
    """Multiple Providers"""

    def  __init__(self, item, candidates, data, runtime = False):
        Event.__init__(self, data)
        self._item = item
        self._candidates = candidates
        self._is_runtime = runtime

    def isRuntime(self):
        """
        Is this a runtime issue?
        """
        return self._is_runtime

    def getItem(self):
        """
        The name for the to be build item
        """
        return self._item

    def getCandidates(self):
        """
        Get the possible Candidates for a PROVIDER.
        """
        return self._candidates

class ParseProgress(Event):
    """
    Parsing Progress Event
    """

    def __init__(self, d, cached, parsed, skipped, masked, errors, total):
        Event.__init__(self, d)
        self.cached = cached
        self.parsed = parsed
        self.skipped = skipped
        self.masked = masked
        self.errors = errors
        self.sofar = cached + parsed + skipped
        self.total = total
