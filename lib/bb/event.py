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

import os, sys
import warnings
try:
    import cPickle as pickle
except ImportError:
    import pickle
import logging
import atexit
import bb.utils

# This is the pid for which we should generate the event. This is set when
# the runqueue forks off.
worker_pid = 0
worker_pipe = None

class Event(object):
    """Base class for events"""

    def __init__(self):
        self.pid = worker_pid

NotHandled = 0
Handled    = 1

Registered        = 10
AlreadyRegistered = 14

# Internal
_handlers = {}
_ui_handlers = {}
_ui_handler_seq = 0

# For compatibility
bb.utils._context["NotHandled"] = NotHandled
bb.utils._context["Handled"] = Handled

def fire_class_handlers(event, d):
    if isinstance(event, logging.LogRecord):
        return

    for handler in _handlers:
        h = _handlers[handler]
        event.data = d
        if type(h).__name__ == "code":
            locals = {"e": event}
            bb.utils.simple_exec(h, locals)
            ret = bb.utils.better_eval("tmpHandler(e)", locals)
            if ret is not None:
                warnings.warn("Using Handled/NotHandled in event handlers is deprecated",
                              DeprecationWarning, stacklevel = 2)
        else:
            h(event)
        del event.data

ui_queue = []
@atexit.register
def print_ui_queue():
    """If we're exiting before a UI has been spawned, display any queued
    LogRecords to the console."""
    logger = logging.getLogger("BitBake")
    if not _ui_handlers:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.handlers = [console]
        while ui_queue:
            event = ui_queue.pop()
            if isinstance(event, logging.LogRecord):
                logger.handle(event)

def fire_ui_handlers(event, d):
    if not _ui_handlers:
        # No UI handlers registered yet, queue up the messages
        ui_queue.append(event)
        return

    errors = []
    for h in _ui_handlers:
        #print "Sending event %s" % event
        try:
             # We use pickle here since it better handles object instances
             # which xmlrpc's marshaller does not. Events *must* be serializable
             # by pickle.
            _ui_handlers[h].event.send((pickle.dumps(event)))
        except:
            errors.append(h)
    for h in errors:
        del _ui_handlers[h]

def fire(event, d):
    """Fire off an Event"""

    # We can fire class handlers in the worker process context and this is
    # desired so they get the task based datastore.
    # UI handlers need to be fired in the server context so we defer this. They
    # don't have a datastore so the datastore context isn't a problem.

    fire_class_handlers(event, d)
    if worker_pid != 0:
        worker_fire(event, d)
    else:
        fire_ui_handlers(event, d)

def worker_fire(event, d):
    data = "<event>" + pickle.dumps(event) + "</event>"
    try:
        if os.write(worker_pipe, data) != len (data):
            print("Error sending event to server (short write)")
    except OSError:
        sys.exit(1)

def fire_from_worker(event, d):
    if not event.startswith("<event>") or not event.endswith("</event>"):
        print("Error, not an event")
        return
    event = pickle.loads(event[7:-8])
    fire_ui_handlers(event, d)

def register(name, handler):
    """Register an Event handler"""

    # already registered
    if name in _handlers:
        return AlreadyRegistered

    if handler is not None:
        # handle string containing python code
        if type(handler).__name__ == "str":
            tmp = "def tmpHandler(e):\n%s" % handler
            comp = bb.utils.better_compile(tmp, "tmpHandler(e)", "bb.event._registerCode")
            _handlers[name] = comp
        else:
            _handlers[name] = handler

        return Registered

def remove(name, handler):
    """Remove an Event handler"""
    _handlers.pop(name)

def register_UIHhandler(handler):
    bb.event._ui_handler_seq = bb.event._ui_handler_seq + 1
    _ui_handlers[_ui_handler_seq] = handler
    return _ui_handler_seq

def unregister_UIHhandler(handlerNum):
    if handlerNum in _ui_handlers:
        del _ui_handlers[handlerNum]
    return

def getName(e):
    """Returns the name of a class or class instance"""
    if getattr(e, "__name__", None) == None:
        return e.__class__.__name__
    else:
        return e.__name__

class ConfigParsed(Event):
    """Configuration Parsing Complete"""

class RecipeParsed(Event):
    """ Recipe Parsing Complete """

    def __init__(self, fn):
        self.fn = fn
        Event.__init__(self)

class StampUpdate(Event):
    """Trigger for any adjustment of the stamp files to happen"""

    def __init__(self, targets, stampfns):
        self._targets = targets
        self._stampfns = stampfns
        Event.__init__(self)

    def getStampPrefix(self):
        return self._stampfns

    def getTargets(self):
        return self._targets

    stampPrefix = property(getStampPrefix)
    targets = property(getTargets)

class BuildBase(Event):
    """Base class for bbmake run events"""

    def __init__(self, n, p, failures = 0):
        self._name = n
        self._pkgs = p
        Event.__init__(self)
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





class BuildStarted(BuildBase):
    """bbmake build run started"""


class BuildCompleted(BuildBase):
    """bbmake build run completed"""




class NoProvider(Event):
    """No Provider for an Event"""

    def __init__(self, item, runtime=False, dependees=None):
        Event.__init__(self)
        self._item = item
        self._runtime = runtime
        self._dependees = dependees

    def getItem(self):
        return self._item

    def isRuntime(self):
        return self._runtime

class MultipleProviders(Event):
    """Multiple Providers"""

    def  __init__(self, item, candidates, runtime = False):
        Event.__init__(self)
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

class ParseStarted(Event):
    """Recipe parsing for the runqueue has begun"""
    def __init__(self, total):
        Event.__init__(self)
        self.total = total

class ParseCompleted(Event):
    """Recipe parsing for the runqueue has completed"""

    def __init__(self, cached, parsed, skipped, masked, virtuals, errors, total):
        Event.__init__(self)
        self.cached = cached
        self.parsed = parsed
        self.skipped = skipped
        self.virtuals = virtuals
        self.masked = masked
        self.errors = errors
        self.sofar = cached + parsed
        self.total = total

class ParseProgress(Event):
    """Recipe parsing progress"""

    def __init__(self, current):
        self.current = current

class DepTreeGenerated(Event):
    """
    Event when a dependency tree has been generated
    """

    def __init__(self, depgraph):
        Event.__init__(self)
        self._depgraph = depgraph

class MsgBase(Event):
    """Base class for messages"""

    def __init__(self, msg):
        self._message = msg
        Event.__init__(self)

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

class LogHandler(logging.Handler):
    """Dispatch logging messages as bitbake events"""

    def emit(self, record):
        fire(record, None)
