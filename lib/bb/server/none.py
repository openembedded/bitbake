#
# BitBake 'dummy' Passthrough Server
#
# Copyright (C) 2006 - 2007  Michael 'Mickey' Lauer
# Copyright (C) 2006 - 2008  Richard Purdie
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

"""
    This module implements an xmlrpc server for BitBake.

    Use this by deriving a class from BitBakeXMLRPCServer and then adding
    methods which you want to "export" via XMLRPC. If the methods have the
    prefix xmlrpc_, then registering those function will happen automatically,
    if not, you need to call register_function.

    Use register_idle_function() to add a function which the xmlrpc server
    calls from within server_forever when no requests are pending. Make sure
    that those functions are non-blocking or else you will introduce latency
    in the server's main loop.
"""

import time
import bb
from bb.ui import uievent
import xmlrpclib
import pickle

DEBUG = False

from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import inspect, select

class BitBakeServerCommands():
    def __init__(self, server, cooker):
        self.cooker = cooker
        self.server = server

    def runCommand(self, command):
        """
        Run a cooker command on the server
        """
        #print "Running Command %s" % command
        return self.cooker.command.runCommand(command)

    def terminateServer(self):
        """
        Trigger the server to quit
        """
        self.server.server_exit()
        #print "Server (cooker) exitting"
        return

    def ping(self):
        """
        Dummy method which can be used to check the server is still alive
        """
        return True

eventQueue = []

class BBUIEventQueue:
    class event:
        def __init__(self, parent):
            self.parent = parent
        @staticmethod
        def send(event):
            bb.server.none.eventQueue.append(pickle.loads(event))
        @staticmethod
        def quit():
            return

    def __init__(self, BBServer):
        self.eventQueue = bb.server.none.eventQueue
        self.BBServer = BBServer
        self.EventHandle = bb.event.register_UIHhandler(self)

    def getEvent(self):
        if len(self.eventQueue) == 0:
            return None

        return self.eventQueue.pop(0)

    def waitEvent(self, delay):
        event = self.getEvent()
        if event:
            return event
        self.BBServer.idle_commands(delay)
        return self.getEvent()

    def queue_event(self, event):
        self.eventQueue.append(event)

    def system_quit( self ):
        bb.event.unregister_UIHhandler(self.EventHandle)

class BitBakeServer():
    # remove this when you're done with debugging
    # allow_reuse_address = True

    def __init__(self, cooker):
        self._idlefuns = {}
        self.commands = BitBakeServerCommands(self, cooker)

    def register_idle_function(self, function, data):
        """Register a function to be called while the server is idle"""
        assert hasattr(function, '__call__')
        self._idlefuns[function] = data

    def idle_commands(self, delay):
        #print "Idle queue length %s" % len(self._idlefuns)
        #print "Idle timeout, running idle functions"
        #if len(self._idlefuns) == 0:
        nextsleep = delay
        for function, data in self._idlefuns.items():
            try:
                retval = function(self, data, False)
                #print "Idle function returned %s" % (retval)
                if retval is False:
                    del self._idlefuns[function]
                elif retval is True:
                    nextsleep = None
                elif nextsleep is None:
                    continue
                elif retval < nextsleep:
                    nextsleep = retval
            except SystemExit:
                raise
            except:
                import traceback
                traceback.print_exc()
                self.commands.runCommand(["stateShutdown"])
                pass
        if nextsleep is not None:
            #print "Sleeping for %s (%s)" % (nextsleep, delay)
            time.sleep(nextsleep)

    def server_exit(self):
        # Tell idle functions we're exiting
        for function, data in self._idlefuns.items():
            try:
                retval = function(self, data, True)
            except:
                pass

class BitbakeServerInfo():
    def __init__(self, server):
        self.server = server
        self.commands = server.commands

class BitBakeServerFork():
    def __init__(self, serverinfo, command, logfile):
        serverinfo.forkCommand = command
        serverinfo.logfile = logfile

class BitBakeServerConnection():
    def __init__(self, serverinfo):
        self.server = serverinfo.server
        self.connection = serverinfo.commands
        self.events = bb.server.none.BBUIEventQueue(self.server)
        for event in bb.event.ui_queue:
            self.events.queue_event(event)

    def terminate(self):
        try:
            self.events.system_quit()
        except:
            pass
        try:
            self.connection.terminateServer()
        except:
            pass
