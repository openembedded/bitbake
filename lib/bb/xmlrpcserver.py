#
# BitBake XMLRPC Server
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

import bb
import xmlrpclib

DEBUG = False

from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import os, sys, inspect, select

class BitBakeServerCommands():
    def __init__(self, server, cooker):
        self.cooker = cooker
        self.server = server

    def registerEventHandler(self, host, port):
        """
        Register a remote UI Event Handler
        """
        s = xmlrpclib.Server("http://%s:%d" % (host, port), allow_none=True)
        return bb.event.register_UIHhandler(s)

    def unregisterEventHandler(self, handlerNum):
        """
        Unregister a remote UI Event Handler
        """
        return bb.event.unregister_UIHhandler(handlerNum)

    def runCommand(self, command):
        """
        Run a cooker command on the server
        """
        return self.cooker.command.runCommand(command)

    def terminateServer(self):
        """
        Trigger the server to quit
        """
        self.server.quit = True
        print "Server (cooker) exitting"
        return

    def ping(self):
        """
        Dummy method which can be used to check the server is still alive
        """
        return True

class BitBakeXMLRPCServer(SimpleXMLRPCServer):
    # remove this when you're done with debugging
    # allow_reuse_address = True

    def __init__(self, cooker, interface = ("localhost", 0)):
        """
	Constructor
	"""
        SimpleXMLRPCServer.__init__(self, interface,
                                    requestHandler=SimpleXMLRPCRequestHandler,
                                    logRequests=False, allow_none=True)
        self._idlefuns = {}
        self.host, self.port = self.socket.getsockname()
        #self.register_introspection_functions()
        commands = BitBakeServerCommands(self, cooker)
        self.autoregister_all_functions(commands, "")

    def autoregister_all_functions(self, context, prefix):
        """
        Convenience method for registering all functions in the scope
        of this class that start with a common prefix
        """
        methodlist = inspect.getmembers(context, inspect.ismethod)
        for name, method in methodlist:
            if name.startswith(prefix):
                self.register_function(method, name[len(prefix):])

    def register_idle_function(self, function, data):
        """Register a function to be called while the server is idle"""
        assert callable(function)
        self._idlefuns[function] = data

    def serve_forever(self):
        """
        Serve Requests. Overloaded to honor a quit command
        """
        self.quit = False
        while not self.quit:
            self.handle_request()

        # Tell idle functions we're exiting
        for function, data in self._idlefuns.items():
            try:
                retval = function(self, data, True)
            except:
                pass

        self.server_close()
        return

    def get_request(self):
        """
        Get next request. Behaves like the parent class unless a waitpid callback
        has been set. In that case, we regularly check waitpid when the server is idle
        """
        while True:
            # wait 500 ms for an xmlrpc request
            if DEBUG: 
                print "DEBUG: select'ing 500ms waiting for an xmlrpc request..."
            ifds, ofds, xfds = select.select([self.socket.fileno()], [], [], 0.5)
            if ifds:
                return self.socket.accept()
            # call idle functions only if we're not shutting down atm to prevent a recursion
            if not self.quit:
                if DEBUG: 
                    print "DEBUG: server is idle -- calling idle functions..."
                for function, data in self._idlefuns.items():
                    try:
                        retval = function(self, data, False)
                        if not retval:
                            del self._idlefuns[function]
                    except SystemExit:
                        raise
                    except:
                        import traceback
                        traceback.print_exc()
                        pass

