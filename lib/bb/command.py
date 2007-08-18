"""
BitBake 'Command' module

Provide an interface to interact with the bitbake server through 'commands'
"""

# Copyright (C) 2006-2007  Richard Purdie
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
The bitbake server takes 'commands' from its UI/commandline. 
Commands are either 'online' of 'offline' in nature. 
Offline commands return data to the client in the form of events.
Online commands must only return data through the function return value
and must not trigger events, directly or indirectly.
Commands are queued in a CommandQueue
"""

import bb

offline_cmds = {}
online_cmds = {}

class Command:
    """
    A queue of 'offline' commands for bitbake
    """
    def __init__(self, cooker):

        self.cooker = cooker
        self.cmds_online = CommandsOnline()
        self.cmds_offline = CommandsOffline()

        # FIXME Add lock for this
        self.currentOfflineCommand = None

        for attr in CommandsOnline.__dict__:
            command = attr[:].lower()
            method = getattr(CommandsOnline, attr)
            online_cmds[command] = (method)

        for attr in CommandsOffline.__dict__:
            command = attr[:].lower()
            method = getattr(CommandsOffline, attr)
            offline_cmds[command] = (method)

    def runCommand(self, commandline):
        try:
            command = commandline.pop(0)
            if command in CommandsOnline.__dict__:
                # Can run online commands straight away            
                return getattr(CommandsOnline, command)(self.cmds_online, self, commandline)
            if self.currentOfflineCommand is not None:
                return "Busy (%s in progress)" % self.currentOfflineCommand[0]
            if command not in CommandsOffline.__dict__:
                return "No such command"
            self.currentOfflineCommand = (command, commandline)
            return True
        except:
            import traceback
            return traceback.format_exc()

    def runOfflineCommand(self):
        try:
            if self.currentOfflineCommand is not None:
                (command, options) = self.currentOfflineCommand
                getattr(CommandsOffline, command)(self.cmds_offline, self, options)
        except:
            import traceback
            self.finishOfflineCommand(traceback.format_exc())

    def finishOfflineCommand(self, error = None):
        if error:
            bb.event.fire(bb.command.CookerCommandFailed(self.cooker.configuration.event_data, error))
        else:
            bb.event.fire(bb.command.CookerCommandCompleted(self.cooker.configuration.event_data))
        self.currentOfflineCommand = None


class CommandsOnline:
    """
    A class of online commands
    These should run quickly so as not to hurt interactive performance.
    These must not influence any running offline command.
    """

    def stateShutdown(self, command, params):
        """
        Trigger cooker 'shutdown' mode
        """
        command.cooker.cookerAction = bb.cooker.cookerShutdown

    def stateStop(self, command, params):
        """
        Stop the cooker
        """
        command.cooker.cookerAction = bb.cooker.cookerStop

    def getCmdLineAction(self, command, params):
        """
        Get any command parsed from the commandline
        """
        return command.cooker.commandlineAction

class CommandsOffline:
    """
    A class of offline commands
    These functions communicate via generated events.
    Any function that requires metadata parsing should be here.
    """

    def buildFile(self, command, params):
        """
        Build a single specified .bb file
        """
        bfile = params[0]
        task = params[1]

        command.cooker.buildFile(bfile, task)
        command.finishOfflineCommand()

    def buildTargets(self, command, params):
        """
        Build a set of targets
        """
        pkgs_to_build = params[0]

        command.cooker.buildTargets(pkgs_to_build)

    def generateDotGraph(self, command, params):
        """
        Dump dependency information to disk as .dot files
        """
        pkgs_to_build = params[0]

        command.cooker.generateDotGraph(pkgs_to_build)
        command.finishOfflineCommand()

    def showVersions(self, command, params):
        """
        Show the currently selected versions
        """
        command.cooker.showVersions()
        command.finishOfflineCommand()

    def showEnvironment(self, command, params):
        """
        Print the environment
        """
        bfile = params[0]

        command.cooker.showEnvironment(bfile)
        command.finishOfflineCommand()

class CookerCommandCompleted(bb.event.Event):
    """
    Cooker command completed
    """
    def  __init__(self, data):
        bb.event.Event.__init__(self, data)


class CookerCommandFailed(bb.event.Event):
    """
    Cooker command completed
    """
    def  __init__(self, data, error):
        bb.event.Event.__init__(self, data)
        self.error = error
