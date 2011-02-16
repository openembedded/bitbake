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

import logging
import signal
import sys
import time
import bb
import bb.event
from multiprocessing import Process, Event
from bb.cooker import BBCooker

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
        except Exception, err:
            print("EventAdapter puked: %s" % str(err))


class ProcessServer(Process):
    profile_filename = "profile.log"
    profile_processed_filename = "profile.log.processed"

    def __init__(self, command_channel, event_queue, configuration):
        Process.__init__(self)
        self.command_channel = command_channel
        self.event_queue = event_queue
        self.event = EventAdapter(event_queue)
        self.configuration = configuration
        self.cooker = BBCooker(configuration, self.register_idle_function)
        self._idlefunctions = {}
        self.event_handle = bb.event.register_UIHhandler(self)
        self.quit = False

        self.keep_running = Event()
        self.keep_running.set()

        for event in bb.event.ui_queue:
            self.event_queue.put(event)

    def register_idle_function(self, function, data):
        """Register a function to be called while the server is idle"""
        assert hasattr(function, '__call__')
        self._idlefunctions[function] = data

    def run(self):
        if self.configuration.profile:
            return self.profile_main()
        else:
            return self.main()

    def profile_main(self):
        import cProfile
        profiler = cProfile.Profile()
        try:
            return profiler.runcall(self.main)
        finally:
            profiler.dump_stats(self.profile_filename)
            self.write_profile_stats()
            sys.__stderr__.write("Raw profiling information saved to %s and "
                                 "processed statistics to %s\n" %
                                 (self.profile_filename,
                                  self.profile_processed_filename))

    def write_profile_stats(self):
        import pstats
        with open(self.profile_processed_filename, 'w') as outfile:
            stats = pstats.Stats(self.profile_filename, stream=outfile)
            stats.sort_stats('time')
            stats.print_stats()
            stats.print_callers()
            stats.sort_stats('cumulative')
            stats.print_stats()

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
