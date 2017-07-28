#
# BitBake Process based server.
#
# Copyright (C) 2010 Bob Foerster <robert@erafx.com>
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
    This module implements a multiprocessing.Process based server for bitbake.
"""

import bb
import bb.event
import logging
import multiprocessing
import threading
import array
import os
import sys
import time
import select
import socket
import subprocess
import errno
import bb.server.xmlrpcserver
from bb import daemonize
from multiprocessing import queues

logger = logging.getLogger('BitBake')

class ProcessTimeout(SystemExit):
    pass

class ProcessServer(multiprocessing.Process):
    profile_filename = "profile.log"
    profile_processed_filename = "profile.log.processed"

    def __init__(self, lock, sock, sockname):
        multiprocessing.Process.__init__(self)
        self.command_channel = False
        self.command_channel_reply = False
        self.quit = False
        self.heartbeat_seconds = 1 # default, BB_HEARTBEAT_EVENT will be checked once we have a datastore.
        self.next_heartbeat = time.time()

        self.event_handle = None
        self.haveui = False
        self.lastui = False
        self.xmlrpc = False

        self._idlefuns = {}

        self.bitbake_lock = lock
        self.sock = sock
        self.sockname = sockname

    def register_idle_function(self, function, data):
        """Register a function to be called while the server is idle"""
        assert hasattr(function, '__call__')
        self._idlefuns[function] = data

    def run(self):

        if self.xmlrpcinterface[0]:
            self.xmlrpc = bb.server.xmlrpcserver.BitBakeXMLRPCServer(self.xmlrpcinterface, self.cooker, self)

            print("Bitbake XMLRPC server address: %s, server port: %s" % (self.xmlrpc.host, self.xmlrpc.port))

        heartbeat_event = self.cooker.data.getVar('BB_HEARTBEAT_EVENT')
        if heartbeat_event:
            try:
                self.heartbeat_seconds = float(heartbeat_event)
            except:
                bb.warn('Ignoring invalid BB_HEARTBEAT_EVENT=%s, must be a float specifying seconds.' % heartbeat_event)

        self.timeout = self.server_timeout or self.cooker.data.getVar('BB_SERVER_TIMEOUT')
        try:
            if self.timeout:
                self.timeout = float(self.timeout)
        except:
            bb.warn('Ignoring invalid BB_SERVER_TIMEOUT=%s, must be a float specifying seconds.' % self.timeout)


        try:
            self.bitbake_lock.seek(0)
            self.bitbake_lock.truncate()
            if self.xmlrpc:
                self.bitbake_lock.write("%s %s:%s\n" % (os.getpid(), self.xmlrpc.host, self.xmlrpc.port))
            else:
                self.bitbake_lock.write("%s\n" % (os.getpid()))
            self.bitbake_lock.flush()
        except:
            pass

        if self.cooker.configuration.profile:
            try:
                import cProfile as profile
            except:
                import profile
            prof = profile.Profile()

            ret = profile.Profile.runcall(prof, self.main)

            prof.dump_stats("profile.log")
            bb.utils.process_profilelog("profile.log")
            print("Raw profiling information saved to profile.log and processed statistics to profile.log.processed")

        else:
            ret = self.main()

        return ret

    def main(self):
        self.cooker.pre_serve()

        bb.utils.set_process_name("Cooker")

        ready = []

        self.controllersock = False
        fds = [self.sock]
        if self.xmlrpc:
            fds.append(self.xmlrpc)
        while not self.quit:
            if self.command_channel in ready:
                command = self.command_channel.get()
                if command[0] == "terminateServer":
                    self.quit = True
                    continue
                try:
                    print("Running command %s" % command)
                    self.command_channel_reply.send(self.cooker.command.runCommand(command))
                except Exception as e:
                   logger.exception('Exception in server main event loop running command %s (%s)' % (command, str(e)))

            if self.xmlrpc in ready:
                self.xmlrpc.handle_requests()
            if self.sock in ready:
                self.controllersock, address = self.sock.accept()
                if self.haveui:
                    print("Dropping connection attempt as we have a UI %s" % (str(ready)))
                    self.controllersock.close()
                else:
                    print("Accepting %s" % (str(ready)))
                    fds.append(self.controllersock)
            if self.controllersock in ready:
                try:
                    print("Connecting Client")
                    ui_fds = recvfds(self.controllersock, 3)

                    # Where to write events to
                    writer = ConnectionWriter(ui_fds[0])
                    self.event_handle = bb.event.register_UIHhandler(writer, True)
                    self.event_writer = writer

                    # Where to read commands from
                    reader = ConnectionReader(ui_fds[1])
                    fds.append(reader)
                    self.command_channel = reader

                    # Where to send command return values to
                    writer = ConnectionWriter(ui_fds[2])
                    self.command_channel_reply = writer

                    self.haveui = True

                except EOFError:
                    print("Disconnecting Client")
                    fds.remove(self.controllersock)
                    fds.remove(self.command_channel)
                    bb.event.unregister_UIHhandler(self.event_handle, True)
                    self.command_channel_reply.writer.close()
                    self.event_writer.writer.close()
                    del self.event_writer
                    self.controllersock.close()
                    self.haveui = False
                    self.lastui = time.time()
                    self.cooker.clientComplete()
                    if self.timeout is None:
                        print("No timeout, exiting.")
                        self.quit = True
            if not self.haveui and self.lastui and self.timeout and (self.lastui + self.timeout) < time.time():
                print("Server timeout, exiting.")
                self.quit = True

            ready = self.idle_commands(.1, fds)

        print("Exiting")
        try: 
            self.cooker.shutdown(True)
        except:
            pass

        self.cooker.post_serve()

        # Remove the socket file so we don't get any more connections to avoid races
        os.unlink(self.sockname)
        self.sock.close()

        # Finally release the lockfile but warn about other processes holding it open
        lock = self.bitbake_lock
        lockfile = lock.name
        lock.close()
        lock = None

        while not lock:
            with bb.utils.timeout(3):
                lock = bb.utils.lockfile(lockfile, shared=False, retry=False, block=True)
                if not lock:
                    # Some systems may not have lsof available
                    procs = None
                    try:
                        procs = subprocess.check_output(["lsof", '-w', lockfile], stderr=subprocess.STDOUT)
                    except OSError as e:
                        if e.errno != errno.ENOENT:
                            raise
                    if procs is None:
                        # Fall back to fuser if lsof is unavailable
                        try:
                            procs = subprocess.check_output(["fuser", '-v', lockfile], stderr=subprocess.STDOUT)
                        except OSError as e:
                            if e.errno != errno.ENOENT:
                                raise

                    msg = "Delaying shutdown due to active processes which appear to be holding bitbake.lock"
                    if procs:
                        msg += ":\n%s" % str(procs)
                    print(msg)
                    return
        # We hold the lock so we can remove the file (hide stale pid data)
        bb.utils.remove(lockfile)
        bb.utils.unlockfile(lock)

    def idle_commands(self, delay, fds=None):
        nextsleep = delay
        if not fds:
            fds = []

        for function, data in list(self._idlefuns.items()):
            try:
                retval = function(self, data, False)
                if retval is False:
                    del self._idlefuns[function]
                    nextsleep = None
                elif retval is True:
                    nextsleep = None
                elif isinstance(retval, float) and nextsleep:
                    if (retval < nextsleep):
                        nextsleep = retval
                elif nextsleep is None:
                    continue
                else:
                    fds = fds + retval
            except SystemExit:
                raise
            except Exception as exc:
                if not isinstance(exc, bb.BBHandledException):
                    logger.exception('Running idle function')
                del self._idlefuns[function]
                self.quit = True

        # Create new heartbeat event?
        now = time.time()
        if now >= self.next_heartbeat:
            # We might have missed heartbeats. Just trigger once in
            # that case and continue after the usual delay.
            self.next_heartbeat += self.heartbeat_seconds
            if self.next_heartbeat <= now:
                self.next_heartbeat = now + self.heartbeat_seconds
            heartbeat = bb.event.HeartbeatEvent(now)
            bb.event.fire(heartbeat, self.cooker.data)
        if nextsleep and now + nextsleep > self.next_heartbeat:
            # Shorten timeout so that we we wake up in time for
            # the heartbeat.
            nextsleep = self.next_heartbeat - now

        if nextsleep is not None:
            if self.xmlrpc:
                nextsleep = self.xmlrpc.get_timeout(nextsleep)
            try:
                return select.select(fds,[],[],nextsleep)[0]
            except InterruptedError:
                # Ignore EINTR
                return []
        else:
            return []


class ServerCommunicator():
    def __init__(self, connection, recv):
        self.connection = connection
        self.recv = recv

    def runCommand(self, command):

        self.connection.send(command)
        while True:
            # don't let the user ctrl-c while we're waiting for a response
            try:
                for idx in range(0,4): # 0, 1, 2, 3
                    if self.recv.poll(1):
                        return self.recv.get()
                    else:
                        bb.note("Timeout while attempting to communicate with bitbake server, retrying...")
                raise ProcessTimeout("Gave up; Too many tries: timeout while attempting to communicate with bitbake server")
            except KeyboardInterrupt:
                pass

    def updateFeatureSet(self, featureset):
        _, error = self.runCommand(["setFeatures", featureset])
        if error:
            logger.error("Unable to set the cooker to the correct featureset: %s" % error)
            raise BaseException(error)

    def getEventHandle(self):
        handle, error = self.runCommand(["getUIHandlerNum"])
        if error:
            logger.error("Unable to get UI Handler Number: %s" % error)
            raise BaseException(error)

        return handle

    def terminateServer(self):
        self.connection.send(['terminateServer'])
        return

class BitBakeProcessServerConnection(object):
    def __init__(self, ui_channel, recv, eq, sock):
        self.connection = ServerCommunicator(ui_channel, recv)
        self.events = eq
        # Save sock so it doesn't get gc'd for the life of our connection
        self.socket_connection = sock

    def terminate(self):
        self.socket_connection.close()
        self.connection.connection.close()
        self.connection.recv.close()
        return

class BitBakeServer(object):
    def __init__(self, lock, sockname, configuration, featureset):

        self.configuration = configuration
        self.featureset = featureset
        self.sockname = sockname
        self.bitbake_lock = lock

        # Create server control socket
        if os.path.exists(sockname):
            os.unlink(sockname)

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # AF_UNIX has path length issues so chdir here to workaround
        cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(sockname))
            self.sock.bind(os.path.basename(sockname))
        finally:
            os.chdir(cwd)
        self.sock.listen(1)

        os.set_inheritable(self.sock.fileno(), True)
        bb.daemonize.createDaemon(self._startServer, "bitbake-cookerdaemon.log")
        self.sock.close()
        self.bitbake_lock.close()

    def _startServer(self):
        server = ProcessServer(self.bitbake_lock, self.sock, self.sockname)
        self.configuration.setServerRegIdleCallback(server.register_idle_function)

        # Copy prefile and postfile to _server variants
        for param in ('prefile', 'postfile'):
            value = getattr(self.configuration, param)
            if value:
                setattr(self.configuration, "%s_server" % param, value)

        self.cooker = bb.cooker.BBCooker(self.configuration, self.featureset)
        server.cooker = self.cooker
        server.server_timeout = self.configuration.server_timeout
        server.xmlrpcinterface = self.configuration.xmlrpcinterface
        print("Started bitbake server pid %d" % os.getpid())
        server.start()

def connectProcessServer(sockname, featureset):
    # Connect to socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # AF_UNIX has path length issues so chdir here to workaround
    cwd = os.getcwd()

    try:
        os.chdir(os.path.dirname(sockname))
        sock.connect(os.path.basename(sockname))
    finally:
        os.chdir(cwd)

    try:
        # Send an fd for the remote to write events to
        readfd, writefd = os.pipe()
        eq = BBUIEventQueue(readfd)
        # Send an fd for the remote to recieve commands from
        readfd1, writefd1 = os.pipe()
        command_chan = ConnectionWriter(writefd1)
        # Send an fd for the remote to write commands results to
        readfd2, writefd2 = os.pipe()
        command_chan_recv = ConnectionReader(readfd2)

        sendfds(sock, [writefd, readfd1, writefd2])

        server_connection = BitBakeProcessServerConnection(command_chan, command_chan_recv, eq, sock)

        server_connection.connection.updateFeatureSet(featureset)

    except:
        sock.close()
        raise

    return server_connection

def sendfds(sock, fds):
        '''Send an array of fds over an AF_UNIX socket.'''
        fds = array.array('i', fds)
        msg = bytes([len(fds) % 256])
        sock.sendmsg([msg], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds)])

def recvfds(sock, size):
        '''Receive an array of fds over an AF_UNIX socket.'''
        a = array.array('i')
        bytes_size = a.itemsize * size
        msg, ancdata, flags, addr = sock.recvmsg(1, socket.CMSG_LEN(bytes_size))
        if not msg and not ancdata:
            raise EOFError
        try:
            if len(ancdata) != 1:
                raise RuntimeError('received %d items of ancdata' %
                                   len(ancdata))
            cmsg_level, cmsg_type, cmsg_data = ancdata[0]
            if (cmsg_level == socket.SOL_SOCKET and
                cmsg_type == socket.SCM_RIGHTS):
                if len(cmsg_data) % a.itemsize != 0:
                    raise ValueError
                a.frombytes(cmsg_data)
                assert len(a) % 256 == msg[0]
                return list(a)
        except (ValueError, IndexError):
            pass
        raise RuntimeError('Invalid data received')

class BBUIEventQueue:
    def __init__(self, readfd):

        self.eventQueue = []
        self.eventQueueLock = threading.Lock()
        self.eventQueueNotify = threading.Event()

        self.reader = ConnectionReader(readfd)

        self.t = threading.Thread()
        self.t.setDaemon(True)
        self.t.run = self.startCallbackHandler
        self.t.start()

    def getEvent(self):
        self.eventQueueLock.acquire()

        if len(self.eventQueue) == 0:
            self.eventQueueLock.release()
            return None

        item = self.eventQueue.pop(0)

        if len(self.eventQueue) == 0:
            self.eventQueueNotify.clear()

        self.eventQueueLock.release()
        return item

    def waitEvent(self, delay):
        self.eventQueueNotify.wait(delay)
        return self.getEvent()

    def queue_event(self, event):
        self.eventQueueLock.acquire()
        self.eventQueue.append(event)
        self.eventQueueNotify.set()
        self.eventQueueLock.release()

    def send_event(self, event):
        self.queue_event(pickle.loads(event))

    def startCallbackHandler(self):
        bb.utils.set_process_name("UIEventQueue")
        while True:
            try:
                self.reader.wait()
                event = self.reader.get()
                self.queue_event(event)
            except EOFError:
                # Easiest way to exit is to close the file descriptor to cause an exit
                break
        self.reader.close()

class ConnectionReader(object):

    def __init__(self, fd):
        self.reader = multiprocessing.connection.Connection(fd, writable=False)
        self.rlock = multiprocessing.Lock()

    def wait(self, timeout=None):
        return multiprocessing.connection.wait([self.reader], timeout)

    def poll(self, timeout=None):
        return self.reader.poll(timeout)

    def get(self):
        with self.rlock:
            res = self.reader.recv_bytes()
        return multiprocessing.reduction.ForkingPickler.loads(res)

    def fileno(self):
        return self.reader.fileno()

    def close(self):
        return self.reader.close()


class ConnectionWriter(object):

    def __init__(self, fd):
        self.writer = multiprocessing.connection.Connection(fd, readable=False)
        self.wlock = multiprocessing.Lock()
        # Why bb.event needs this I have no idea
        self.event = self

    def send(self, obj):
        obj = multiprocessing.reduction.ForkingPickler.dumps(obj)
        with self.wlock:
            self.writer.send_bytes(obj)

    def fileno(self):
        return self.writer.fileno()

    def close(self):
        return self.writer.close()
