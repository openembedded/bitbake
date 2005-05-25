#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
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

"""
BitBake Shell

General Question to be decided: Make it a full-fledged Python Shell or
retain the simple command line interface like it is at the moment?

TODO:
    * readline completion (file and provider?)
    * specify tasks
    * specify force
    * command to clean stamps
    * command to reparse one bbfile
    * automatic check if reparsing is necessary (inotify?)
    * bb file wizard
    * call editor on bb file
    * clean-and-rebuild bbfile
"""

import sys, os, imp, readline
imp.load_source( "bitbake", os.path.dirname( sys.argv[0] )+"/bitbake" )
from bb import make, data

__version__ = 0.1
__credits__ = """BitBake Shell Version %2.1f (C) 2005 Michael 'Mickey' Lauer <mickey@Vanille.de>
Type 'help' for more information, press CTRL-D to exit.""" % __version__

cmds = {}
cooker = None
parsed = False
debug = False

def rebuildCommand( params ):
    """Clean and rebuild a .bb file or a provider"""
    print "BBSHELL: sorry, not yet implemented :/"

def buildCommand( params ):
    """Build a .bb file or a provider"""
    try:
        name = params[0]
    except IndexError:
        print "Usage: build <bbfile|provider>"
    else:
        if name.endswith( ".bb" ):
            cooker.executeOneBB( os.path.abspath( name ) )
        else:
            if not parsed:
                print "BBSHELL: D'oh! The .bb files haven't been parsed yet. Next time call 'parse' before building stuff. This time I'll do it for 'ya."
                parseCommand( None )
            cooker.buildPackage( name )

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

def environmentCommand( params ):
    """Dump out the outer BitBake environment (see bbread)"""
    data.emit_env(sys.__stdout__, make.cfg, True)

def printCommand( params ):
    """Print the contents of an outer BitBake environment variable"""
    try:
        var = params[0]
    except IndexError:
        print "Usage: print <variable>"
    else:
        value = data.getVar( var, make.cfg, 1 )
        print value

def setVarCommand( params ):
    """Set an outer BitBake environment variable"""
    try:
        var, value = params
    except ValueError, IndexError:
        print "Usage: set <variable> <value>"
    else:
        data.setVar( var, value, make.cfg )
        print "OK"

def init():
    """Register commands and set up readline"""
    registerCommand( "help", showHelp )
    registerCommand( "exit", exitShell )
    
    registerCommand( "build", buildCommand )
    registerCommand( "environment", environmentCommand )
    registerCommand( "rebuild", rebuildCommand )
    registerCommand( "parse", parseCommand )
    registerCommand( "print", printCommand )
    registerCommand( "set", setVarCommand )
    
    readline.set_completer( completer )
    readline.parse_and_bind("tab: complete")

def exitShell( params ):
    """Leave the BitBake Shell"""
    sys.exit(0)

def completer( *args, **kwargs ):
    print "completer called", args, kwargs
    return None

def showCredits():
    print __credits__

def showHelp( *args ):
    """Show a comprehensive list of commands and their purpose"""
    print "="*35, "Available Commands", "="*35
    for cmd, func in cmds.items():
        print "| %s | %s" % (cmd.ljust(max([len(x) for x in cmds.keys()])), func.__doc__)
    print "="*88

def registerCommand( command, function ):
    cmds[command] = function

def processCommand( command, params ):
    if debug: print "(processing command '%s'...)" % command
    if command in cmds:
        result = cmds[command]( params )
    else:
        print "Error: '%s' command is not a valid command." % command
        return
    if debug: print "(result was '%s')" % result

def main():
    while True:
        try:
            cmdline = raw_input( "BB>> " )
            if cmdline:
                if ' ' in cmdline:
                    processCommand( cmdline.split()[0], cmdline.split()[1:] )
                else:
                    processCommand( cmdline, "" )
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

if __name__ == "__main__":
    print "BBSHELL: Sorry, this program should only be called by BitBake."
