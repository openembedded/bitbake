#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
##########################################################################
#
# Copyright (C) 2005 Michael 'Mickey' Lauer <mickey@Vanille.de>, Vanille Media
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA 02111-1307 USA.
#
##########################################################################

"""
BitBake Shell

TODO:
    * specify tasks
    * specify force
    * command to reparse just one (or more) bbfile(s)
    * automatic check if reparsing is necessary (inotify?)
    * frontend for bb file manipulation?
    * pipe output of commands into shell commands (i.e grep or sort)?
    * job control, i.e. bring commands into background with '&', fg, bg, etc.?
    * start parsing in background right after startup?
    * print variable from package data
    * command aliases / shortcuts?
"""

##########################################################################
# Import and setup global variables
##########################################################################

try:
    set
except NameError:
    from sets import Set as set
import sys, os, imp, readline, socket, httplib, urllib, commands
imp.load_source( "bitbake", os.path.dirname( sys.argv[0] )+"/bitbake" )
from bb import data, parse, build, make, fatal

__version__ = "0.5.0"
__credits__ = """BitBake Shell Version %s (C) 2005 Michael 'Mickey' Lauer <mickey@Vanille.de>
Type 'help' for more information, press CTRL-D to exit.""" % __version__

cmds = {}
leave_mainloop = False
last_exception = None
cooker = None
parsed = False
debug = os.environ.get( "BBSHELL_DEBUG", "" ) != ""
history_file = "%s/.bbsh_history" % os.environ.get( "HOME" )

##########################################################################
# Class BitBakeShellCommands
##########################################################################

class BitBakeShellCommands:
    """This class contains the valid commands for the shell"""

    def __init__( self, shell ):
        """Register all the commands"""
        self._shell = shell
        for attr in BitBakeShellCommands.__dict__:
            if not attr.startswith( "__" ):
                if attr.endswith( "_" ):
                    command = attr[:-1].lower()
                else:
                    command = attr[:].lower()
                method = getattr( BitBakeShellCommands, attr )
                if debug: print "registering command '%s'" % command
                # scan number of arguments
                usage = getattr( method, "usage", "" )
                if usage != "<...>":
                    numArgs = len( usage.split() )
                else:
                    numArgs = -1
                shell.registerCommand( command, method, numArgs, "%s %s" % ( command, usage ), method.__doc__ )

    def buffer( self, params ):
        """Dump specified output buffer"""
        index = params[0]
        print self._shell.myout.buffer( int( index ) )
    buffer.usage = "<index>"

    def buffers( self, params ):
        """Show the available output buffers"""
        commands = self._shell.myout.bufferedCommands()
        if not commands:
            print "SHELL: No buffered commands available yet. Start doing something."
        else:
            print "="*35, "Available Output Buffers", "="*27
            for index, cmd in enumerate( commands ):
                print "| %s %s" % ( str( index ).ljust( 3 ), cmd )
            print "="*88

    def build( self, params, cmd = "build" ):
        """Build a providee"""
        name = params[0]

        oldcmd = make.options.cmd
        make.options.cmd = cmd
        cooker.build_cache = []
        cooker.build_cache_fail = []

        if not parsed:
            print "SHELL: D'oh! The .bb files haven't been parsed yet. Next time call 'parse' before building stuff. This time I'll do it for 'ya."
            self.parse( None )
        try:
            cooker.buildProvider( name )
        except build.EventException, e:
            print "ERROR: Couldn't build '%s'" % name
            global last_exception
            last_exception = e

        make.options.cmd = oldcmd
    build.usage = "<providee>"

    def clean( self, params ):
        """Clean a providee"""
        self.build( params, "clean" )
    clean.usage = "<providee>"

    def edit( self, params ):
        """Call $EDITOR on a .bb file"""
        name = params[0]
        os.system( "%s %s" % ( os.environ.get( "EDITOR", "vi" ), completeFilePath( name ) ) )
    edit.usage = "<bbfile>"

    def environment( self, params ):
        """Dump out the outer BitBake environment (see bbread)"""
        data.emit_env(sys.__stdout__, make.cfg, True)

    def exit_( self, params ):
        """Leave the BitBake Shell"""
        if debug: print "(setting leave_mainloop to true)"
        global leave_mainloop
        leave_mainloop = True

    def fileBuild( self, params, cmd = "build" ):
        """Parse and build a .bb file"""
        name = params[0]
        bf = completeFilePath( name )
        print "SHELL: Calling '%s' on '%s'" % ( cmd, bf )

        oldcmd = make.options.cmd
        make.options.cmd = cmd
        cooker.build_cache = []
        cooker.build_cache_fail = []

        try:
            bbfile_data = parse.handle( bf, make.cfg )
        except parse.ParseError:
            print "ERROR: Unable to open or parse '%s'" % bf
        else:
            item = data.getVar('PN', bbfile_data, 1)
            data.setVar( "_task_cache", [], bbfile_data ) # force
            try:
                cooker.tryBuildPackage( os.path.abspath( bf ), item, bbfile_data )
            except build.EventException, e:
                print "ERROR: Couldn't build '%s'" % name
                global last_exception
                last_exception = e

        make.options.cmd = oldcmd
    fileBuild.usage = "<bbfile>"

    def fileClean( self, params ):
        """Clean a .bb file"""
        self.fileBuild( params, "clean" )
    fileClean.usage = "<bbfile>"

    def fileRebuild( self, params ):
        """Rebuild (clean & build) a .bb file"""
        self.fileClean( params )
        self.fileBuild( params )
    fileRebuild.usage = "<bbfile>"

    def help( self, params ):
        """Show a comprehensive list of commands and their purpose"""
        print "="*30, "Available Commands", "="*30
        allcmds = cmds.keys()
        allcmds.sort()
        for cmd in allcmds:
            function,numparams,usage,helptext = cmds[cmd]
            print "| %s | %s" % (usage.ljust(30), helptext)
        print "="*78

    def lastError( self, params ):
        """Show the reason or log that was produced by the last BitBake event exception"""
        if last_exception is None:
            print "SHELL: No Errors yet (Phew)..."
        else:
            reason, event = last_exception.args
            print "SHELL: Reason for the last error: '%s'" % reason
            if ':' in reason:
                msg, filename = reason.split( ':' )
                filename = filename.strip()
                print "SHELL: Dumping log file for last error:"
                try:
                    print open( filename ).read()
                except IOError:
                    print "ERROR: Couldn't open '%s'" % filename

    def new( self, params ):
        """Create a new .bb file and open the editor"""
        dirname, filename = params
        packages = '/'.join( data.getVar( "BBFILES", make.cfg, 1 ).split('/')[:-2] )
        fulldirname = "%s/%s" % ( packages, dirname )

        if not os.path.exists( fulldirname ):
            print "SHELL: Creating '%s'" % fulldirname
            os.mkdir( fulldirname )
        if os.path.exists( fulldirname ) and os.path.isdir( fulldirname ):
            if os.path.exists( "%s/%s" % ( fulldirname, filename ) ):
                print "SHELL: ERROR: %s/%s already exists" % ( fulldirname, filename )
                return False
            print "SHELL: Creating '%s/%s'" % ( fulldirname, filename )
            newpackage = open( "%s/%s" % ( fulldirname, filename ), "w" )
            print >>newpackage,"""DESCRIPTION = ""
SECTION = ""
AUTHOR = ""
HOMEPAGE = ""
MAINTAINER = ""
LICENSE = "GPL"
PR = "r0"

SRC_URI = ""

#inherit base

#do_configure() {
#
#}

#do_compile() {
#
#}

#do_stage() {
#
#}

#do_install() {
#
#}
"""
            newpackage.close()
            os.system( "%s %s/%s" % ( os.environ.get( "EDITOR" ), fulldirname, filename ) )
    new.usage = "<directory> <filename>"

    def pasteBin( self, params ):
        """Send a command + output buffer to http://pastebin.com"""
        index = params[0]
        contents = self._shell.myout.buffer( int( index ) )
        status, error, location = sendToPastebin( contents )
        if status == 302:
            print "SHELL: Pasted to %s" % location
        else:
            print "ERROR: %s %s" % ( response.status, response.reason )
    pasteBin.usage = "<index>"

    def pasteLog( self, params ):
        """Send the last event exception error log (if there is one) to http://pastebin.com"""
        if last_exception is None:
            print "SHELL: No Errors yet (Phew)..."
        else:
            reason, event = last_exception.args
            print "SHELL: Reason for the last error: '%s'" % reason
            if ':' in reason:
                msg, filename = reason.split( ':' )
                filename = filename.strip()
                print "SHELL: Pasting log file to pastebin..."

                status, error, location = sendToPastebin( open( filename ).read() )

                if status == 302:
                    print "SHELL: Pasted to %s" % location
                else:
                    print "ERROR: %s %s" % ( response.status, response.reason )

    def parse( self, params ):
        """(Re-)parse .bb files and calculate the dependency graph"""
        cooker.status = cooker.ParsingStatus()
        ignore = data.getVar("ASSUME_PROVIDED", make.cfg, 1) or ""
        cooker.status.ignored_dependencies = set( ignore.split() )
        cooker.handleCollections( data.getVar("BBFILE_COLLECTIONS", make.cfg, 1) )

        make.collect_bbfiles( cooker.myProgressCallback )
        cooker.buildDepgraph()
        global parsed
        parsed = True
        print

    def print_( self, params ):
        """Print the contents of an outer BitBake environment variable"""
        var = params[0]
        value = data.getVar( var, make.cfg, 1 )
        print value
    print_.usage = "<variable>"

    def python( self, params ):
        """Enter the expert mode - an interactive BitBake Python Interpreter"""
        sys.ps1 = "EXPERT BB>>> "
        sys.ps2 = "EXPERT BB... "
        import code
        interpreter = code.InteractiveConsole( dict( globals() ) )
        interpreter.interact( "SHELL: Expert Mode - BitBake Python %s\nType 'help' for more information, press CTRL-D to switch back to BBSHELL." % sys.version )

    def setVar( self, params ):
        """Set an outer BitBake environment variable"""
        var, value = params
        data.setVar( var, value, make.cfg )
        print "OK"
    setVar.usage = "<variable> <value>"

    def rebuild( self, params ):
        """Clean and rebuild a .bb file or a providee"""
        self.build( params, "clean" )
        self.build( params, "build" )
    rebuild.usage = "<providee>"

    def shell( self, params ):
        """Execute a shell command and dump the output"""
        if params != "":
            print commands.getoutput( " ".join( params ) )
    shell.usage = "<...>"

    def status( self, params ):
        """<just for testing>"""
        print "-" * 78
        print "build cache = '%s'" % cooker.build_cache
        print "build cache fail = '%s'" % cooker.build_cache_fail
        print "building list = '%s'" % cooker.building_list
        print "build path = '%s'" % cooker.build_path
        print "consider_msgs_cache = '%s'" % cooker.consider_msgs_cache
        print "build stats = '%s'" % cooker.stats
        if last_exception is not None: print "last_exception = '%s'" % repr( last_exception.args )
        print "memory output contents = '%s'" % self._shell.myout._buffer

    def test( self, params ):
        """<just for testing>"""
        print "testCommand called with '%s'" % params

    def which( self, params ):
        """Computes the providers for a given providee"""
        item = params[0]

        if not parsed:
            print "SHELL: D'oh! The .bb files haven't been parsed yet. Next time call 'parse' before building stuff. This time I'll do it for 'ya."
            self.parse( None )

        preferred = data.getVar( "PREFERRED_PROVIDER_%s" % item, make.cfg, 1 )
        if not preferred: preferred = item

        try:
            lv, lf, pv, pf = cooker.findBestProvider( preferred )
        except KeyError:
            lv, lf, pv, pf = (None,)*4

        try:
            providers = cooker.status.providers[item]
        except KeyError:
            print "SHELL: ERROR: Nothing provides", preferred
        else:
            for provider in providers:
                if provider == pf: provider = " (***) %s" % provider
                else:              provider = "       %s" % provider
                print provider
    which.usage = "<providee>"

##########################################################################
# Common helper functions
##########################################################################

def completeFilePath( bbfile ):
    """Get the complete bbfile path"""
    if not make.pkgdata: return bbfile
    for key in make.pkgdata.keys():
        if key.endswith( bbfile ):
            return key
    return bbfile

def sendToPastebin( content ):
    """Send content to http://www.pastebin.com"""
    mydata = {}
    mydata["parent_pid"] = ""
    mydata["format"] = "bash"
    mydata["code2"] = content
    mydata["paste"] = "Send"
    mydata["poster"] = "%s@%s" % ( os.environ.get( "USER", "unknown" ), socket.gethostname() or "unknown" )
    params = urllib.urlencode( mydata )
    headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}

    conn = httplib.HTTPConnection( "pastebin.com:80" )
    conn.request("POST", "/", params, headers )

    response = conn.getresponse()
    conn.close()

    return response.status, response.reason, response.getheader( "location" ) or "unknown"

def completer( text, state ):
    """Return a possible readline completion"""
    if debug: print "(completer called with text='%s', state='%d'" % ( text, state )

    if state == 0:
        line = readline.get_line_buffer()
        if " " in line:
            line = line.split()
            # we are in second (or more) argument
            if line[0] == "print" or line[0] == "set":
                allmatches = make.cfg.keys()
            elif line[0].startswith( "file" ):
                if make.pkgdata is None: allmatches = [ "(No Matches Available. Parsed yet?)" ]
                else: allmatches = [ x.split("/")[-1] for x in make.pkgdata.keys() ]
            elif line[0] == "build" or line[0] == "clean" or line[0] == "which":
                if make.pkgdata is None: allmatches = [ "(No Matches Available. Parsed yet?)" ]
                else: allmatches = cooker.status.providers.iterkeys()
            else: allmatches = [ "(No tab completion available for this command)" ]
        else:
            # we are in first argument
            allmatches = cmds.iterkeys()

        completer.matches = [ x for x in allmatches if x[:len(text)] == text ]
        #print "completer.matches = '%s'" % completer.matches
    if len( completer.matches ) > state:
        return completer.matches[state]
    else:
        return None


##########################################################################
# Class MemoryOutput
##########################################################################

class MemoryOutput:
    """File-like output class buffering the output of the last 10 commands"""
    def __init__( self, delegate ):
        self.delegate = delegate
        self._buffer = []
        self.text = []
        self._command = None

    def startCommand( self, command ):
        self._command = command
        self.text = []
    def endCommand( self ):
        if self._command is not None:
            if len( self._buffer ) == 10: del self._buffer[0]
            self._buffer.append( ( self._command, self.text ) )
    def removeLast( self ):
        if self._buffer:
            del self._buffer[ len( self._buffer ) - 1 ]
        self.text = []
        self._command = None
    def bufferedCommands( self ):
        return [ cmd for cmd, output in self._buffer ]
    def buffer( self, i ):
        if i < len( self._buffer ):
            return "BB>> %s\n%s" % ( self._buffer[i][0], "".join( self._buffer[i][1] ) )
        else: return "ERROR: Invalid buffer number. Buffer needs to be in (0, %d)" % ( len( self._buffer ) - 1 )
    def write( self, text ):
        if self._command is not None and text != "BB>> ": self.text.append( text )
        self.delegate.write( text )
    def flush( self ):
        return self.delegate.flush()
    def fileno( self ):
        return self.delegate.fileno()
    def isatty( self ):
        return self.delegate.isatty()

##########################################################################
# Class BitBakeShell
##########################################################################

class BitBakeShell:

    def __init__( self ):
        """Register commands and set up readline"""
        self.commands = BitBakeShellCommands( self )
        self.myout = MemoryOutput( sys.stdout )

        readline.set_completer( completer )
        readline.set_completer_delims( " " )
        readline.parse_and_bind("tab: complete")

        try:
            global history_file
            readline.read_history_file( history_file )
        except IOError:
            pass  # It doesn't exist yet.

        print __credits__

    def cleanup( self ):
        """Write readline history and clean up resources"""
        if debug: print "(writing command history)"
        try:
            global history_file
            readline.write_history_file( history_file )
        except:
            print "SHELL: Unable to save command history"

    def registerCommand( self, command, function, numparams = 0, usage = "", helptext = "" ):
        """Register a command"""
        if usage == "": usage = command
        if helptext == "": helptext = function.__doc__ or "<not yet documented>"
        cmds[command] = ( function, numparams, usage, helptext )

    def processCommand( self, command, params ):
        """Process a command. Check number of params and print a usage string, if appropriate"""
        if debug: print "(processing command '%s'...)" % command
        try:
            function, numparams, usage, helptext = cmds[command]
        except KeyError:
            print "SHELL: ERROR: '%s' command is not a valid command." % command
            self.myout.removeLast()
        else:
            if (numparams != -1) and (not len( params ) == numparams):
                print "Usage: '%s'" % usage
                return

            result = function( self.commands, params )
            if debug: print "(result was '%s')" % result

    def main( self ):
        """The main command loop"""
        while not leave_mainloop:
            try:
                sys.stdout = self.myout.delegate
                cmdline = raw_input( "BB>> " )
                sys.stdout = self.myout
                if cmdline:
                    commands = cmdline.split( ';' )
                    for command in commands:
                        self.myout.startCommand( command )
                        if ' ' in command:
                            self.processCommand( command.split()[0], command.split()[1:] )
                        else:
                            self.processCommand( command, "" )
                        self.myout.endCommand()
            except EOFError:
                print
                return
            except KeyboardInterrupt:
                print

##########################################################################
# Start function - called from the BitBake command line utility
##########################################################################

def start( aCooker ):
    global cooker
    cooker = aCooker
    bbshell = BitBakeShell()
    bbshell.main()
    bbshell.cleanup()

if __name__ == "__main__":
    print "SHELL: Sorry, this program should only be called by BitBake."
