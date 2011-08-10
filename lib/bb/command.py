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

import bb.event
import bb.cooker
import bb.data

async_cmds = {}
sync_cmds = {}


class CommandCompleted(bb.event.Event):
    pass

class CommandExit(bb.event.Event):
    def  __init__(self, exitcode):
        bb.event.Event.__init__(self)
        self.exitcode = int(exitcode)

class CommandFailed(CommandExit):
    def __init__(self, message):
        self.error = message
        CommandExit.__init__(self, 1)

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
                # Can run synchronous commands straight away
                return getattr(CommandsSync, command)(self.cmds_sync, self, commandline)
            if self.currentAsyncCommand is not None:
                return "Busy (%s in progress)" % self.currentAsyncCommand[0]
            if command not in CommandsAsync.__dict__:
                return "No such command"
            self.currentAsyncCommand = (command, commandline)
            self.cooker.server_registration_cb(self.cooker.runCommands, self.cooker)
            return True
        except:
            import traceback
            return traceback.format_exc()

    def runAsyncCommand(self):
        try:
            if self.currentAsyncCommand is not None:
                (command, options) = self.currentAsyncCommand
                commandmethod = getattr(CommandsAsync, command)
                needcache = getattr( commandmethod, "needcache" )
                if (needcache and self.cooker.state in
                    (bb.cooker.state.initial, bb.cooker.state.parsing)):
                    self.cooker.updateCache()
                    return True
                else:
                    commandmethod(self.cmds_async, self, options)
                    return False
            else:
                return False
        except KeyboardInterrupt as exc:
            self.finishAsyncCommand("Interrupted")
            return False
        except SystemExit as exc:
            arg = exc.args[0]
            if isinstance(arg, basestring):
                self.finishAsyncCommand(arg)
            else:
                self.finishAsyncCommand("Exited with %s" % arg)
            return False
        except Exception:
            import traceback
            self.finishAsyncCommand(traceback.format_exc())
            return False

    def finishAsyncCommand(self, msg=None, code=None):
        if msg:
            bb.event.fire(CommandFailed(msg), self.cooker.configuration.event_data)
        elif code:
            bb.event.fire(CommandExit(code), self.cooker.configuration.event_data)
        else:
            bb.event.fire(CommandCompleted(), self.cooker.configuration.event_data)
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
        command.cooker.shutdown()

    def stateStop(self, command, params):
        """
        Stop the cooker
        """
        command.cooker.stop()

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

    def resetCooker(self, command, params):
        """
        Reset the cooker to its initial state, thus forcing a reparse for
        any async command that has the needcache property set to True
        """
        command.cooker.reset()


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
    buildFile.needcache = False

    def buildTargets(self, command, params):
        """
        Build a set of targets
        """
        pkgs_to_build = params[0]
        task = params[1]

        command.cooker.buildTargets(pkgs_to_build, task)
    buildTargets.needcache = True

    def generateDepTreeEvent(self, command, params):
        """
        Generate an event containing the dependency information
        """
        pkgs_to_build = params[0]
        task = params[1]

        command.cooker.generateDepTreeEvent(pkgs_to_build, task)
        command.finishAsyncCommand()
    generateDepTreeEvent.needcache = True

    def generateDotGraph(self, command, params):
        """
        Dump dependency information to disk as .dot files
        """
        pkgs_to_build = params[0]
        task = params[1]

        command.cooker.generateDotGraphFiles(pkgs_to_build, task)
        command.finishAsyncCommand()
    generateDotGraph.needcache = True

    def generateTargetsTree(self, command, params):
        """
        Generate a tree of buildable targets.
        If klass is provided ensure all recipes that inherit the class are
        included in the package list.
        If pkg_list provided use that list (plus any extras brought in by
        klass) rather than generating a tree for all packages.
        """
        klass = params[0]
        if len(params) > 1:
            pkg_list = params[1]
        else:
            pkg_list = []

        command.cooker.generateTargetsTree(klass, pkg_list)
        command.finishAsyncCommand()
    generateTargetsTree.needcache = True

    def findConfigFiles(self, command, params):
        """
        Find config files which provide appropriate values
        for the passed configuration variable. i.e. MACHINE
        """
        varname = params[0]

        command.cooker.findConfigFiles(varname)
        command.finishAsyncCommand()
    findConfigFiles.needcache = True

    def findFilesMatchingInDir(self, command, params):
        """
        Find implementation files matching the specified pattern
        in the requested subdirectory of a BBPATH
        """
        pattern = params[0]
        directory = params[1]

        command.cooker.findFilesMatchingInDir(pattern, directory)
        command.finishAsyncCommand()
    findFilesMatchingInDir.needcache = True

    def findConfigFilePath(self, command, params):
        """
        Find the path of the requested configuration file
        """
        configfile = params[0]

        command.cooker.findConfigFilePath(configfile)
        command.finishAsyncCommand()
    findConfigFilePath.needcache = False

    def showVersions(self, command, params):
        """
        Show the currently selected versions
        """
        command.cooker.showVersions()
        command.finishAsyncCommand()
    showVersions.needcache = True

    def showEnvironmentTarget(self, command, params):
        """
        Print the environment of a target recipe
        (needs the cache to work out which recipe to use)
        """
        pkg = params[0]

        command.cooker.showEnvironment(None, pkg)
        command.finishAsyncCommand()
    showEnvironmentTarget.needcache = True

    def showEnvironment(self, command, params):
        """
        Print the standard environment
        or if specified the environment for a specified recipe
        """
        bfile = params[0]

        command.cooker.showEnvironment(bfile)
        command.finishAsyncCommand()
    showEnvironment.needcache = False

    def parseFiles(self, command, params):
        """
        Parse the .bb files
        """
        command.cooker.updateCache()
        command.finishAsyncCommand()
    parseFiles.needcache = True

    def reparseFiles(self, command, params):
        """
        Reparse .bb files
        """
        command.cooker.reparseFiles()
        command.finishAsyncCommand()
    reparseFiles.needcache = True

    def compareRevisions(self, command, params):
        """
        Parse the .bb files
        """
        if bb.fetch.fetcher_compare_revisions(command.cooker.configuration.data):
            command.finishAsyncCommand(code=1)
        else:
            command.finishAsyncCommand()
    compareRevisions.needcache = True
