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
    * pipe output of commands into a shell command (i.e grep or sort)?
    * job control, i.e. bring commands into background with '&', fg, bg, etc.?
    * start parsing in background right after startup?
    * use ; to supply more than one commnd per line
    * command aliases / shortcuts?
    * capture bb exceptions occuring during task execution
"""

##########################################################################
# Import and setup global variables
##########################################################################

try:
    set
except NameError:
    from sets import Set as set
import sys, os, imp, readline, socket, httplib, urllib
imp.load_source( "bitbake", os.path.dirname( sys.argv[0] )+"/bitbake" )
from bb import data, parse, build, make, fatal

__version__ = "0.4.0"
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
# Commands
##########################################################################

def bufferCommand( params ):
    """Dump output buffer #i"""
    index = params[0]
    print processCommand.memoryOutput.buffer( int( index ) )

def buffersCommand( params ):
    """Show the available output buffers"""
    commands = processCommand.memoryOutput.bufferedCommands()
    if not commands:
        print "SHELL: No buffered commands available yet. Start doing something."
    else:
        print "="*35, "Available Output Buffers", "="*27
        for index, cmd in enumerate( commands ):
            print "| %s %s" % ( str( index ).ljust( 3 ), cmd )
        print "="*88

def buildCommand( params, cmd = "build" ):
    """Build a providee"""
    name = params[0]

    oldcmd = make.options.cmd
    make.options.cmd = cmd
    cooker.build_cache = []
    cooker.build_cache_fail = []

    if not parsed:
        print "SHELL: D'oh! The .bb files haven't been parsed yet. Next time call 'parse' before building stuff. This time I'll do it for 'ya."
        parseCommand( None )
    try:
        cooker.buildProvider( name )
    except build.EventException, e:
        print "ERROR: Couldn't build '%s'" % name
        global last_exception
        last_exception = e

    make.options.cmd = oldcmd

def cleanCommand( params ):
    """Clean a providee"""
    buildCommand( params, "clean" )

def editCommand( params ):
    """Call $EDITOR on a .bb file"""
    name = params[0]
    os.system( "%s %s" % ( os.environ.get( "EDITOR" ), completeFilePath( name ) ) )

def environmentCommand( params ):
    """Dump out the outer BitBake environment (see bbread)"""
    data.emit_env(sys.__stdout__, make.cfg, True)

def execCommand( params ):
    """Execute one line of python code"""
    exec " ".join( params ) in locals(), globals()

def exitShell( params ):
    """Leave the BitBake Shell"""
    if debug: print "(setting leave_mainloop to true)"
    global leave_mainloop
    leave_mainloop = True

def fileBuildCommand( params, cmd = "build" ):
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
    except IOError:
        print "SHELL: ERROR: Unable to open %s" % bf
    else:
        item = data.getVar('PN', bbfile_data, 1)
        data.setVar( "_task_cache", [], bbfile_data ) # force
        cooker.tryBuildPackage( os.path.abspath( bf ), item, bbfile_data )

    make.options.cmd = oldcmd

def fileCleanCommand( params ):
    """Clean a .bb file"""
    fileBuildCommand( params, "clean" )

def fileRebuildCommand( params ):
    """Rebuild (clean & build) a .bb file"""
    fileCleanCommand( params )
    fileBuildCommand( params )

def lastErrorCommand( params ):
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

def newCommand( params ):
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

SRC_URI = ""

inherit base

#do_compile() {
#
#}

#do_configure() {
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

def pasteBinCommand( params ):
    """Send a command + output buffer to http://pastebin.com"""
    index = params[0]
    contents = processCommand.memoryOutput.buffer( int( index ) )
    status, error, location = sendToPastebin( contents )
    if status == 302:
        print "SHELL: Pasted to %s" % location
    else:
        print "ERROR: %s %s" % ( response.status, response.reason )

def pasteLogCommand( params ):
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

def parseCommand( params ):
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

def printCommand( params ):
    """Print the contents of an outer BitBake environment variable"""
    var = params[0]
    value = data.getVar( var, make.cfg, 1 )
    print value

def pythonCommand( params ):
    """Enter the expert mode - an interactive BitBake Python Interpreter"""
    sys.ps1 = "EXPERT BB>>> "
    sys.ps2 = "EXPERT BB... "
    import code
    python = code.InteractiveConsole( dict( globals() ) )
    python.interact( "SHELL: Expert Mode - BitBake Python %s\nType 'help' for more information, press CTRL-D to switch back to BBSHELL." % sys.version )

def setVarCommand( params ):
    """Set an outer BitBake environment variable"""
    var, value = params
    data.setVar( var, value, make.cfg )
    print "OK"

def rebuildCommand( params ):
    """Clean and rebuild a .bb file or a providee"""
    buildCommand( params, "clean" )
    buildCommand( params, "build" )

def statusCommand( params ):
    print "-" * 78
    print "build cache = '%s'" % cooker.build_cache
    print "build cache fail = '%s'" % cooker.build_cache_fail
    print "building list = '%s'" % cooker.building_list
    print "build path = '%s'" % cooker.build_path
    print "consider_msgs_cache = '%s'" % cooker.consider_msgs_cache
    print "build stats = '%s'" % cooker.stats
    if last_exception is not None: print "last_exception = '%s'" % repr( last_exception.args )
    print "memory output contents = '%s'" % processCommand.memoryOutput._buffer

def testCommand( params ):
    """Just for testing..."""
    print "testCommand called with '%s'" % params

def whichCommand( params ):
    """Computes the providers for a given providee"""
    item = params[0]

    if not parsed:
        print "SHELL: D'oh! The .bb files haven't been parsed yet. Next time call 'parse' before building stuff. This time I'll do it for 'ya."
        parseCommand( None )

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

##########################################################################
# Common helper functions
##########################################################################

def completeFilePath( bbfile ):
    if not make.pkgdata: return bbfile
    for key in make.pkgdata.keys():
        if key.endswith( bbfile ):
            return key
    return bbfile

def sendToPastebin( content ):
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

##########################################################################
# File-like output class buffering the output of the last 10 commands
##########################################################################

class MemoryOutput:
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
# Startup / Shutdown
##########################################################################

def init():
    """Register commands and set up readline"""
    registerCommand( "help", showHelp )
    registerCommand( "exit", exitShell )

    registerCommand( "buffer", bufferCommand, 1, "buffer <#>" )
    registerCommand( "buffers", buffersCommand, 0 )
    registerCommand( "build", buildCommand, 1, "build <providee>" )
    registerCommand( "clean", cleanCommand, 1, "clean <providee>" )
    registerCommand( "edit", editCommand, 1, "edit <bbfile>" )
    registerCommand( "environment", environmentCommand )
    registerCommand( "exec", execCommand, 1, "exec <one line of pythoncode>" )
    registerCommand( "filebuild", fileBuildCommand, 1, "filebuild <bbfile>" )
    registerCommand( "fileclean", fileCleanCommand, 1, "fileclean <bbfile>" )
    registerCommand( "filerebuild", fileRebuildCommand, 1, "filerebuild <bbfile>" )
    registerCommand( "lastlog", lastErrorCommand, 0 )
    registerCommand( "new", newCommand, 2, "new <directory> <bbfile>" )
    registerCommand( "pastebin", pasteBinCommand, 1, "pastebin <#>" )
    registerCommand( "pastelog", pasteLogCommand, 0 )
    registerCommand( "parse", parseCommand )
    registerCommand( "print", printCommand, 1, "print <variable>" )
    registerCommand( "python", pythonCommand )
    registerCommand( "rebuild", rebuildCommand, 1, "rebuild <providee>" )
    registerCommand( "set", setVarCommand, 2, "set <variable> <value>" )
    registerCommand( "status", statusCommand )
    registerCommand( "test", testCommand )
    registerCommand( "which", whichCommand, 1, "which <providee>" )

    readline.set_completer( completer )
    readline.set_completer_delims( " " )
    readline.parse_and_bind("tab: complete")

    try:
        global history_file
        readline.read_history_file( history_file )
    except IOError:
        pass  # It doesn't exist yet.

def cleanup():
    """Write readline history and clean up resources"""
    if debug: print "(writing command history)"
    try:
        global history_file
        readline.write_history_file( history_file )
    except:
        print "SHELL: Unable to save command history"

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

def showCredits():
    """Show credits (sic!)"""
    print __credits__

def showHelp( *args ):
    """Show a comprehensive list of commands and their purpose"""
    print "="*35, "Available Commands", "="*35
    allcmds = cmds.keys()
    allcmds.sort()
    for cmd in allcmds:
        function,numparams,usage,helptext = cmds[cmd]
        print "| %s | %s" % (usage.ljust(35), helptext)
    print "="*88

def registerCommand( command, function, numparams = 0, usage = "", helptext = "" ):
    """Register a command"""
    if usage == "": usage = command
    if helptext == "": helptext = function.__doc__ or "<not yet documented>"
    cmds[command] = ( function, numparams, usage, helptext )

def processCommand( command, params ):
    """Process a command. Check number of params and print a usage string, if appropriate"""
    if debug: print "(processing command '%s'...)" % command
    try:
        function, numparams, usage, helptext = cmds[command]
    except KeyError:
        print "SHELL: ERROR: '%s' command is not a valid command." % command
        processCommand.memoryOutput.removeLast()
    else:
        if not len( params ) == numparams:
            print "Usage: '%s'" % usage
            return

        result = function( params )
        if debug: print "(result was '%s')" % result

def main():
    """The main command loop"""
    processCommand.memoryOutput = MemoryOutput( sys.stdout )
    sys.stdout = processCommand.memoryOutput
    while not leave_mainloop:
        try:
            cmdline = raw_input( "BB>> " )
            if cmdline:
                commands = cmdline.split( ';' )
                for command in commands:
                    processCommand.memoryOutput.startCommand( command )
                    if ' ' in command:
                        processCommand( command.split()[0], command.split()[1:] )
                    else:
                        processCommand( command, "" )
                    processCommand.memoryOutput.endCommand()
        except EOFError:
            print
            return
        except KeyboardInterrupt:
            print

def start( aCooker ):
    global cooker
    cooker = aCooker
    showCredits()
    init()
    main()
    cleanup()

if __name__ == "__main__":
    print "SHELL: Sorry, this program should only be called by BitBake."
