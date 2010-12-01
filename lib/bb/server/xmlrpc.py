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
import xmlrpclib, sys
from bb import daemonize
from bb.ui import uievent

DEBUG = False

from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import inspect, select

if sys.hexversion < 0x020600F0:
    print("Sorry, python 2.6 or later is required for bitbake's XMLRPC mode")
    sys.exit(1)

##
# The xmlrpclib.Transport class has undergone various changes in Python 2.7
# which break BitBake's XMLRPC implementation.
# To work around this we subclass Transport and have a copy/paste of method
# implementations from Python 2.6.6's xmlrpclib.
#
# Upstream Python bug is #8194 (http://bugs.python.org/issue8194)
##

class BBTransport(xmlrpclib.Transport):
    def request(self, host, handler, request_body, verbose=0):
        h = self.make_connection(host)
        if verbose:
            h.set_debuglevel(1)

        self.send_request(h, handler, request_body)
        self.send_host(h, host)
        self.send_user_agent(h)
        self.send_content(h, request_body)

        errcode, errmsg, headers = h.getreply()

        if errcode != 200:
            raise ProtocolError(
                host + handler,
                errcode, errmsg,
                headers
                )

        self.verbose = verbose

        try:
            sock = h._conn.sock
        except AttributeError:
            sock = None

        return self._parse_response(h.getfile(), sock)

    def make_connection(self, host):
        import httplib
        host, extra_headers, x509 = self.get_host_info(host)
        return httplib.HTTP(host)

    def _parse_response(self, file, sock):
        p, u = self.getparser()

        while 1:
            if sock:
                response = sock.recv(1024)
            else:
                response = file.read(1024)
            if not response:
                break
            if self.verbose:
                print "body:", repr(response)
            p.feed(response)

        file.close()
        p.close()

        return u.close()

class BitBakeServerCommands():
    def __init__(self, server, cooker):
        self.cooker = cooker
        self.server = server

    def registerEventHandler(self, host, port):
        """
        Register a remote UI Event Handler
        """
        t = BBTransport()
        s = xmlrpclib.Server("http://%s:%d/" % (host, port), transport=t, allow_none=True)
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
        print("Server (cooker) exitting")
        return

    def ping(self):
        """
        Dummy method which can be used to check the server is still alive
        """
        return True

class BitBakeServer(SimpleXMLRPCServer):
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
        assert hasattr(function, '__call__')
        self._idlefuns[function] = data

    def serve_forever(self):
        """
        Serve Requests. Overloaded to honor a quit command
        """
        self.quit = False
        self.timeout = 0 # Run Idle calls for our first callback
        while not self.quit:
            #print "Idle queue length %s" % len(self._idlefuns)
            self.handle_request()
            #print "Idle timeout, running idle functions"
            nextsleep = None
            for function, data in self._idlefuns.items():
                try:
                    retval = function(self, data, False)
                    if retval is False:
                        del self._idlefuns[function]
                    elif retval is True:
                        nextsleep = 0
                    elif nextsleep is 0:
                        continue
                    elif nextsleep is None:
                        nextsleep = retval
                    elif retval < nextsleep:
                        nextsleep = retval
                except SystemExit:
                    raise
                except:
                    import traceback
                    traceback.print_exc()
                    pass
            if nextsleep is None and len(self._idlefuns) > 0:
                nextsleep = 0
            self.timeout = nextsleep
        # Tell idle functions we're exiting
        for function, data in self._idlefuns.items():
            try:
                retval = function(self, data, True)
            except:
                pass

        self.server_close()
        return

class BitbakeServerInfo():
    def __init__(self, server):
        self.host = server.host
        self.port = server.port

class BitBakeServerFork():
    def __init__(self, serverinfo, command, logfile):
        daemonize.createDaemon(command, logfile)

class BitBakeServerConnection():
    def __init__(self, serverinfo):
        t = BBTransport()
        self.connection = xmlrpclib.Server("http://%s:%s" % (serverinfo.host, serverinfo.port), transport=t, allow_none=True)
        self.events = uievent.BBUIEventQueue(self.connection)
        for event in bb.event.ui_queue:
            self.events.queue_event(event)

    def terminate(self):
        # Don't wait for server indefinitely
        import socket
        socket.setdefaulttimeout(2)
        try:
            self.events.system_quit()
        except:
            pass
        try:
            self.connection.terminateServer()
        except:
            pass
