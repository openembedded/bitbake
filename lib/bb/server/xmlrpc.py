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
import hashlib, time
import socket
import os, signal
import threading
try:
    import cPickle as pickle
except ImportError:
    import pickle

DEBUG = False

from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import inspect, select

from . import BitBakeBaseServer, BitBakeBaseServerConnection, BaseImplServer

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
# This bug is relevant for Python 2.7.0 and 2.7.1 but was fixed for
# Python > 2.7.2
#
# To implement a simple form of client control, we use a special transport
# that adds a HTTP header field ("Bitbake-token") to ensure that a server
# can communicate with only a client at a given time (the client must use
# the same token).
##
if (2, 7, 0) <= sys.version_info < (2, 7, 2):
    class BBTransport(xmlrpclib.Transport):
        def __init__(self):
            self.connection_token = None
            xmlrpclib.Transport.__init__(self)

        def request(self, host, handler, request_body, verbose=0):
            h = self.make_connection(host)
            if verbose:
                h.set_debuglevel(1)

            self.send_request(h, handler, request_body)
            self.send_host(h, host)
            self.send_user_agent(h)
            if self.connection_token:
                h.putheader("Bitbake-token", self.connection_token)
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
                    print("body:", repr(response))
                p.feed(response)

            file.close()
            p.close()

            return u.close()

        def set_connection_token(self, token):
            self.connection_token = token
else:
    class BBTransport(xmlrpclib.Transport):
        def __init__(self):
            self.connection_token = None
            xmlrpclib.Transport.__init__(self)

        def set_connection_token(self, token):
            self.connection_token = token

        def send_content(self, h, body):
            if self.connection_token:
                h.putheader("Bitbake-token", self.connection_token)
            xmlrpclib.Transport.send_content(self, h, body)

def _create_server(host, port):
    t = BBTransport()
    s = xmlrpclib.Server("http://%s:%d/" % (host, port), transport=t, allow_none=True)
    return s, t

class BitBakeServerCommands():

    def __init__(self, server):
        self.server = server
        self.has_client = False

    def registerEventHandler(self, host, port):
        """
        Register a remote UI Event Handler
        """
        s, t = _create_server(host, port)

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
        print("Server (cooker) exiting")
        return

    def addClient(self):
        if self.has_client:
            return None
        token = hashlib.md5(str(time.time())).hexdigest()
        self.server.set_connection_token(token)
        self.has_client = True
        return token

    def removeClient(self):
        if self.has_client:
            self.server.set_connection_token(None)
            self.has_client = False

# This request handler checks if the request has a "Bitbake-token" header
# field (this comes from the client side) and compares it with its internal
# "Bitbake-token" field (this comes from the server). If the two are not
# equal, it is assumed that a client is trying to connect to the server
# while another client is connected to the server. In this case, a 503 error
# ("service unavailable") is returned to the client.
class BitBakeXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    def __init__(self, request, client_address, server):
        self.connection_token = server.connection_token
        SimpleXMLRPCRequestHandler.__init__(self, request, client_address, server)

    def do_POST(self):
        try:
            remote_token = self.headers["Bitbake-token"]
        except:
            remote_token = None
        if remote_token != self.connection_token:
            self.report_503()
        else:
            SimpleXMLRPCRequestHandler.do_POST(self)

    def report_503(self):
        self.send_response(503)
        response = 'No more client allowed'
        self.send_header("Content-type", "text/plain")
        self.send_header("Content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

class BitBakeUIEventServer(threading.Thread):
    class EventAdapter():
        """
        Adapter to wrap our event queue since the caller (bb.event) expects to
        call a send() method, but our actual queue only has put()
        """
        def __init__(self, notify):
            self.queue = []
            self.notify = notify
            self.qlock = threading.Lock()

        def send(self, event):
            self.qlock.acquire()
            self.queue.append(event)
            self.qlock.release()
            self.notify.set()

        def get(self):
            self.qlock.acquire()
            if len(self.queue) == 0:
                self.qlock.release()
                return None
            e = self.queue.pop(0)
            if len(self.queue) == 0:
                self.notify.clear()
            self.qlock.release()
            return e

    def __init__(self, connection):
        self.connection = connection
        self.notify = threading.Event()
        self.event = BitBakeUIEventServer.EventAdapter(self.notify)
        self.quit = False
        threading.Thread.__init__(self)

    def terminateServer(self):
        self.quit = True

    def run(self):
        while not self.quit:
            self.notify.wait(0.1)
            evt = self.event.get()
            if evt:
                self.connection.event.sendpickle(pickle.dumps(evt))

class BitBakeXMLRPCEventServerController(SimpleXMLRPCServer, threading.Thread):
    def __init__(self, interface):
        SimpleXMLRPCServer.__init__(self, interface, logRequests=False, allow_none=True)
        threading.Thread.__init__(self)
        self.register_function(self.registerEventHandler, "registerEventHandler")
        self.register_function(self.unregisterEventHandler, "unregisterEventHandler")
        self.register_function(self.terminateServer, "terminateServer")
        #self.register_function(self.runCommand, "runCommand")
        self.quit = False
        self.clients = {}
        self.client_ui_ids = {}
        self.timeout = 1    # timeout for .handle_request()

    def registerEventHandler(self, host, port):
        """
        Register a remote UI Event Handler
        """
        connection = xmlrpclib.ServerProxy("http://%s:%d/" % (host, port), allow_none=True)
        client_hash = "%s:%d" % (host, port)
        if self.clients.has_key(client_hash):
            return None
        client_ui_server = BitBakeUIEventServer(connection)
        self.client_ui_ids[client_hash] = bb.event.register_UIHhandler(client_ui_server)
        client_ui_server.start()
        self.clients[client_hash] = client_ui_server
        return client_hash

    def unregisterEventHandler(self, client_hash):
        """
        Unregister a remote UI Event Handler
        """
        client_thread = self.clients[client_hash]
        if client_thread:
            bb.event.unregister_UIHhandler(self.clients_ui_ids[client_hash])
            client_thread.terminateServer()
            client_thread.join()
            return True
        else:
            return False

    def terminateServer(self):
        self.quit = True

    def runCommand(self, cmd):
        return None

    def run(self):
        self.serve_forever()

    def serve_forever(self):
        while not self.quit:
            self.handle_request()
        self.server_close()

class XMLRPCProxyServer(BaseImplServer):
    """ not a real working server, but a stub for a proxy server connection

    """
    def __init__(self, host, port):
        self.host = host
        self.port = port

class XMLRPCServer(SimpleXMLRPCServer, BaseImplServer):
    # remove this when you're done with debugging
    # allow_reuse_address = True

    def __init__(self, interface):
        """
        Constructor
        """
        BaseImplServer.__init__(self)
        SimpleXMLRPCServer.__init__(self, interface,
                                    requestHandler=BitBakeXMLRPCRequestHandler,
                                    logRequests=False, allow_none=True)
        self.host, self.port = self.socket.getsockname()
        self.connection_token = None
        #self.register_introspection_functions()
        self.commands = BitBakeServerCommands(self)
        self.autoregister_all_functions(self.commands, "")
        self.interface = interface

    def addcooker(self, cooker):
        BaseImplServer.addcooker(self, cooker)
        self.commands.cooker = cooker

    def autoregister_all_functions(self, context, prefix):
        """
        Convenience method for registering all functions in the scope
        of this class that start with a common prefix
        """
        methodlist = inspect.getmembers(context, inspect.ismethod)
        for name, method in methodlist:
            if name.startswith(prefix):
                self.register_function(method, name[len(prefix):])


    def serve_forever(self):
        # Create and run the event server controller in a separate thread
        self.event_controller_thread = BitBakeXMLRPCEventServerController((self.host, self.port + 2))
        self.event_controller_thread.start()
        # Start the actual XMLRPC server
        bb.cooker.server_main(self.cooker, self._serve_forever)

    def _serve_forever(self):
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
        # Terminate the event server
        self.event_controller_thread.terminateServer()
        self.event_controller_thread.join()
        self.server_close()
        return

    def set_connection_token(self, token):
        self.connection_token = token

class BitBakeXMLRPCServerConnection(BitBakeBaseServerConnection):
    def __init__(self, serverImpl, clientinfo=("localhost", 0)):
        self.connection, self.transport = _create_server(serverImpl.host, serverImpl.port)
        self.clientinfo = clientinfo
        self.serverImpl = serverImpl

    def connect(self):
        token = self.connection.addClient()
        if token is None:
            return None
        self.transport.set_connection_token(token)
        self.events = uievent.BBUIEventQueue(self.connection, self.clientinfo)
        for event in bb.event.ui_queue:
            self.events.queue_event(event)
        return self

    def removeClient(self):
        self.connection.removeClient()

    def terminate(self):
        # Don't wait for server indefinitely
        import socket
        socket.setdefaulttimeout(2)
        try:
            self.events.system_quit()
        except:
            pass
        try:
            self.connection.removeClient()
        except:
            pass

class BitBakeServer(BitBakeBaseServer):
    def initServer(self, interface = ("localhost", 0)):
        self.serverImpl = XMLRPCServer(interface)

    def detach(self):
        daemonize.createDaemon(self.serverImpl.serve_forever, "bitbake-cookerdaemon.log")
        del self.cooker

    def establishConnection(self):
        self.connection = BitBakeXMLRPCServerConnection(self.serverImpl)
        return self.connection.connect()

    def set_connection_token(self, token):
        self.connection.transport.set_connection_token(token)

class BitBakeXMLRPCClient(BitBakeBaseServer):

    def __init__(self):
        pass

    def saveConnectionDetails(self, remote):
        self.remote = remote

    def establishConnection(self):
        # The format of "remote" must be "server:port"
        try:
            [host, port] = self.remote.split(":")
            port = int(port)
        except:
            return None
        # We need our IP for the server connection. We get the IP
        # by trying to connect with the server
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((host, port))
            ip = s.getsockname()[0]
            s.close()
        except:
            return None
        self.serverImpl = XMLRPCProxyServer(host, port)
        self.connection = BitBakeXMLRPCServerConnection(self.serverImpl, (ip, 0))
        return self.connection.connect()

    def endSession(self):
        self.connection.removeClient()
