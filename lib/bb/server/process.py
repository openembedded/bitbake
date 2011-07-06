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
import itertools
import logging
import multiprocessing
import os
import signal
import sys
import time
from Queue import Empty
from multiprocessing import Event, Process, util, Queue, Pipe, queues

logger = logging.getLogger('BitBake')

class ServerCommunicator():
    def __init__(self, connection):
        self.connection = connection

    def runCommand(self, command):
        # @todo try/except
        self.connection.send(command)

        while True:
            # don't let the user ctrl-c while we're waiting for a response
            try:
                if self.connection.poll(.5):
                    return self.connection.recv()
                else:
                    return None
            except KeyboardInterrupt:
                pass


class EventAdapter():
    """
    Adapter to wrap our event queue since the caller (bb.event) expects to
    call a send() method, but our actual queue only has put()
    """
    def __init__(self, queue):
        self.queue = queue

    def send(self, event):
        try:
            self.queue.put(event)
        except Exception as err:
            print("EventAdapter puked: %s" % str(err))


class ProcessServer(Process):
    profile_filename = "profile.log"
    profile_processed_filename = "profile.log.processed"

    def __init__(self, command_channel, event_queue):
        Process.__init__(self)
        self.command_channel = command_channel
        self.event_queue = event_queue
        self.event = EventAdapter(event_queue)
        self._idlefunctions = {}
        self.quit = False

        self.keep_running = Event()
        self.keep_running.set()

    def register_idle_function(self, function, data):
        """Register a function to be called while the server is idle"""
        assert hasattr(function, '__call__')
        self._idlefunctions[function] = data

    def run(self):
        for event in bb.event.ui_queue:
            self.event_queue.put(event)
        self.event_handle = bb.event.register_UIHhandler(self)
        bb.cooker.server_main(self.cooker, self.main)

    def main(self):
        # Ignore SIGINT within the server, as all SIGINT handling is done by
        # the UI and communicated to us
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        while self.keep_running.is_set():
            try:
                if self.command_channel.poll():
                    command = self.command_channel.recv()
                    self.runCommand(command)

                self.idle_commands(.1)
            except Exception:
                logger.exception('Running command %s', command)

        self.event_queue.cancel_join_thread()
        bb.event.unregister_UIHhandler(self.event_handle)
        self.command_channel.close()
        self.cooker.stop()
        self.idle_commands(.1)

    def idle_commands(self, delay):
        nextsleep = delay

        for function, data in self._idlefunctions.items():
            try:
                retval = function(self, data, False)
                if retval is False:
                    del self._idlefunctions[function]
                elif retval is True:
                    nextsleep = None
                elif nextsleep is None:
                    continue
                elif retval < nextsleep:
                    nextsleep = retval
            except SystemExit:
                raise
            except Exception:
                logger.exception('Running idle function')

        if nextsleep is not None:
            time.sleep(nextsleep)

    def runCommand(self, command):
        """
        Run a cooker command on the server
        """
        self.command_channel.send(self.cooker.command.runCommand(command))

    def stop(self):
        self.keep_running.clear()

    def bootstrap_2_6_6(self):
        """Pulled from python 2.6.6. Needed to ensure we have the fix from
        http://bugs.python.org/issue5313 when running on python version 2.6.2
        or lower."""

        try:
            self._children = set()
            self._counter = itertools.count(1)
            try:
                sys.stdin.close()
                sys.stdin = open(os.devnull)
            except (OSError, ValueError):
                pass
            multiprocessing._current_process = self
            util._finalizer_registry.clear()
            util._run_after_forkers()
            util.info('child process calling self.run()')
            try:
                self.run()
                exitcode = 0
            finally:
                util._exit_function()
        except SystemExit as e:
            if not e.args:
                exitcode = 1
            elif type(e.args[0]) is int:
                exitcode = e.args[0]
            else:
                sys.stderr.write(e.args[0] + '\n')
                sys.stderr.flush()
                exitcode = 1
        except:
            exitcode = 1
            import traceback
            sys.stderr.write('Process %s:\n' % self.name)
            sys.stderr.flush()
            traceback.print_exc()

        util.info('process exiting with exitcode %d' % exitcode)
        return exitcode

    # Python versions 2.6.0 through 2.6.2 suffer from a multiprocessing bug
    # which can result in a bitbake server hang during the parsing process
    if (2, 6, 0) <= sys.version_info < (2, 6, 3):
        _bootstrap = bootstrap_2_6_6

class BitBakeServerConnection():
    def __init__(self, server):
        self.server = server
        self.procserver = server.server
        self.connection = ServerCommunicator(server.ui_channel)
        self.events = server.event_queue

    def terminate(self, force = False):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.procserver.stop()
        if force:
            self.procserver.join(0.5)
            if self.procserver.is_alive():
                self.procserver.terminate()
                self.procserver.join()
        else:
            self.procserver.join()
        while True:
            try:
                event = self.server.event_queue.get(block=False)
            except (Empty, IOError):
                break
            if isinstance(event, logging.LogRecord):
                logger.handle(event)
        self.server.ui_channel.close()
        self.server.event_queue.close()
        if force:
            sys.exit(1)

# Wrap Queue to provide API which isn't server implementation specific
class ProcessEventQueue(multiprocessing.queues.Queue):
    def waitEvent(self, timeout):
        try:
            return self.get(True, timeout)
        except Empty:
            return None

    def getEvent(self):
        try:
            return self.get(False)
        except Empty:
            return None


class BitBakeServer(object):
    def initServer(self):
        # establish communication channels.  We use bidirectional pipes for
        # ui <--> server command/response pairs
        # and a queue for server -> ui event notifications
        #
        self.ui_channel, self.server_channel = Pipe()
        self.event_queue = ProcessEventQueue(0)

        self.server = ProcessServer(self.server_channel, self.event_queue)

    def addcooker(self, cooker):
        self.cooker = cooker
        self.server.cooker = cooker

    def getServerIdleCB(self):
        return self.server.register_idle_function

    def saveConnectionDetails(self):
        return

    def detach(self, cooker_logfile):
        self.server.start() 
        return

    def establishConnection(self):
        self.connection = BitBakeServerConnection(self)
        signal.signal(signal.SIGTERM, lambda i, s: self.connection.terminate(force=True))
        return self.connection

    def launchUI(self, uifunc, *args):
        return bb.cooker.server_main(self.cooker, uifunc, *args)

