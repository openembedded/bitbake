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
Commands are either synchronous or asynchronous.
Async commands return data to the client in the form of events.
Sync commands must only return data through the function return value
and must not trigger events, directly or indirectly.
Commands are queued in a CommandQueue
"""

import bb

async_cmds = {}
sync_cmds = {}

class Command:
    """
    A queue of asynchronous commands for bitbake
    """
    def __init__(self, cooker):

        self.cooker = cooker
        self.cmds_sync = CommandsSync()
        self.cmds_async = CommandsAsync()

        # FIXME Add lock for this
        self.currentAsyncCommand = None

        for attr in CommandsSync.__dict__:
            command = attr[:].lower()
            method = getattr(CommandsSync, attr)
            sync_cmds[command] = (method)

        for attr in CommandsAsync.__dict__:
            command = attr[:].lower()
            method = getattr(CommandsAsync, attr)
            async_cmds[command] = (method)

    def runCommand(self, commandline):
        try:
            command = commandline.pop(0)
            if command in CommandsSync.__dict__:
                # Can run online commands straight away            
                return getattr(CommandsSync, command)(self.cmds_sync, self, commandline)
            if self.currentAsyncCommand is not None:
                return "Busy (%s in progress)" % self.currentAsyncCommand[0]
            if command not in CommandsAsync.__dict__:
                return "No such command"
            self.currentAsyncCommand = (command, commandline)
            return True
        except:
            import traceback
            return traceback.format_exc()

    def runAsyncCommand(self):
        try:
            if self.currentAsyncCommand is not None:
                (command, options) = self.currentAsyncCommand
                getattr(CommandsAsync, command)(self.cmds_async, self, options)
        except:
            import traceback
            self.finishAsyncCommand(traceback.format_exc())

    def finishAsyncCommand(self, error = None):
        if error:
            bb.event.fire(bb.command.CookerCommandFailed(self.cooker.configuration.event_data, error))
        else:
            bb.event.fire(bb.command.CookerCommandCompleted(self.cooker.configuration.event_data))
        self.currentAsyncCommand = None


class CommandsSync:
    """
    A class of synchronous commands
    These should run quickly so as not to hurt interactive performance.
    These must not influence any running synchronous command.
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

    def getVariable(self, command, params):
        """
        Read the value of a variable from configuration.data
        """
        varname = params[0]
        expand = True
        if len(params) > 1:
            expand = params[1]

        return bb.data.getVar(varname, command.cooker.configuration.data, expand)

    def setVariable(self, command, params):
        """
        Set the value of variable in configuration.data
        """
        varname = params[0]
        value = params[1]
        bb.data.setVar(varname, value, command.cooker.configuration.data)


class CommandsAsync:
    """
    A class of asynchronous commands
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

    def buildTargets(self, command, params):
        """
        Build a set of targets
        """
        pkgs_to_build = params[0]
        task = params[1]

        command.cooker.buildTargets(pkgs_to_build, task)

    def generateDepTreeEvent(self, command, params):
        """
        Generate an event containing the dependency information
        """
        pkgs_to_build = params[0]
        task = params[1]

        command.cooker.generateDepTreeEvent(pkgs_to_build, task)
        command.finishAsyncCommand()

    def generateDotGraph(self, command, params):
        """
        Dump dependency information to disk as .dot files
        """
        pkgs_to_build = params[0]
        task = params[1]

        command.cooker.generateDotGraphFiles(pkgs_to_build, task)
        command.finishAsyncCommand()

    def showVersions(self, command, params):
        """
        Show the currently selected versions
        """
        command.cooker.showVersions()
        command.finishAsyncCommand()

    def showEnvironment(self, command, params):
        """
        Print the environment
        """
        bfile = params[0]
        pkg = params[1]

        command.cooker.showEnvironment(bfile, pkg)
        command.finishAsyncCommand()

    def parseFiles(self, command, params):
        """
        Parse the .bb files
        """
        command.cooker.updateCache()
        command.finishAsyncCommand()

#
# Events
#
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
