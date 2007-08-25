#
# BitBake Curses UI Implementation
#
# Handling output to TTYs or files (no TTY)
#
# Copyright (C) 2006 Michael 'Mickey' Lauer
# Copyright (C) 2006-2007 Richard Purdie
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
    This module implements an ncurses frontend for the BitBake utility.

    We have the following windows:

        1.) Title Window: Shows the title, credits, version, etc.
        2.) Main Window: Shows what we are ultimately building and how far we are.
        3.) Thread Activity Window: Shows one status line for every concurrent bitbake thread.
        4.) Command Line Window: Contains an interactive command line where you can interact w/ Bitbake.

    Basic window layout is like that:

        |---------------------------------------------------------|
        |-                <Title Window>                          |
        |---------------------------------------------------------|
        | <Main Window>               | <Task Activity Window>    |
        |                             | 0: foo do_compile complete|
        | Building Gtk+-2.6.10        | 1: bar do_patch complete  |
        | Status: 60%                 | ...                       |
        |                             | ...                       |
        |                             | ...                       |
        |---------------------------------------------------------|
        |<Command Line Window>                                    |
        |>>> which virtual/kernel                                 |
        |openzaurus-kernel                                        |
        |>>> _                                                    |
        |---------------------------------------------------------|

"""

import os, sys, curses, time, random, threading, itertools, time
from curses.textpad import Textbox
import bb
from bb import ui
from bb.ui import uihelper

parsespin = itertools.cycle( r'|/-\\' )

X = 0
Y = 1
WIDTH = 2
HEIGHT = 3

class NCursesUI:
    """
    NCurses UI Class
    """
    class Window:
        """Base Window Class"""
        def __init__( self, x, y, width, height, fg=curses.COLOR_BLACK, bg=curses.COLOR_WHITE ):
            self.win = curses.newwin( height, width, y, x )
            self.dimensions = ( x, y, width, height )
            """
            if curses.has_colors():
                color = 1
                curses.init_pair( color, fg, bg )
                self.win.bkgdset( ord(' '), curses.color_pair(color) )
            else:
                self.win.bkgdset( ord(' '), curses.A_BOLD )
            """
            self.erase()
            self.setScrolling()
            self.win.refresh()

        def erase( self ):
            self.win.erase()

        def setScrolling( self, b = True ):
            self.win.scrollok( b )
            self.win.idlok( b )

        def setBoxed( self ):
            self.boxed = True
            self.win.box()
            self.win.refresh()

        def setText( self, x, y, text, *args ):
            self.win.addstr( y, x, text, *args )
            self.win.refresh()

        def appendText( self, text, *args ):
            self.win.addstr( text, *args )
            self.win.refresh()

        def drawHline( self, y ):
            self.win.hline( y, 0, curses.ACS_HLINE, self.dimensions[WIDTH] )
            self.win.refresh()

    class DecoratedWindow( Window ):
        """Base class for windows with a box and a title bar"""
        def __init__( self, title, x, y, width, height, fg=curses.COLOR_BLACK, bg=curses.COLOR_WHITE ):
            NCursesUI.Window.__init__( self, x+1, y+3, width-2, height-4, fg, bg )
            self.decoration = NCursesUI.Window( x, y, width, height, fg, bg )
            self.decoration.setBoxed()
            self.decoration.win.hline( 2, 1, curses.ACS_HLINE, width-2 )
            self.setTitle( title )

        def setTitle( self, title ):
            self.decoration.setText( 1, 1, title.center( self.dimensions[WIDTH]-2 ), curses.A_BOLD )

    #-------------------------------------------------------------------------#
    class TitleWindow( Window ):
    #-------------------------------------------------------------------------#
        """Title Window"""
        def __init__( self, x, y, width, height ):
            NCursesUI.Window.__init__( self, x, y, width, height )
            version = "1.8.0" # FIXME compute version
            title = "BitBake %s" % version
            credit = "(C) 2003-2007 Team BitBake"
            #self.win.hline( 2, 1, curses.ACS_HLINE, width-2 )
            self.win.border()
            self.setText( 1, 1, title.center( self.dimensions[WIDTH]-2 ), curses.A_BOLD )
            self.setText( 1, 2, credit.center( self.dimensions[WIDTH]-2 ), curses.A_BOLD )

    #-------------------------------------------------------------------------#
    class ThreadActivityWindow( DecoratedWindow ):
    #-------------------------------------------------------------------------#
        """Thread Activity Window"""
        def __init__( self, x, y, width, height ):
            NCursesUI.DecoratedWindow.__init__( self, "Thread Activity", x, y, width, height )
    
        def setStatus( self, thread, text ):
            line = "%02d: %s" % ( thread, text )
            width = self.dimensions[WIDTH]
            if ( len(line) > width ):
                line = line[:width-3] + "..."
            else:
                line = line.ljust( width )
            self.setText( 0, thread, line )

    #-------------------------------------------------------------------------#
    class MainWindow( DecoratedWindow ):
    #-------------------------------------------------------------------------#
        """Main Window"""
        def __init__( self, x, y, width, height ):
            NCursesUI.DecoratedWindow.__init__( self, "Main Window", x, y, width, height )
            curses.nl()

    #-------------------------------------------------------------------------#
    class ShellOutputWindow( DecoratedWindow ):
    #-------------------------------------------------------------------------#
        """Interactive Command Line Output"""
        def __init__( self, x, y, width, height ):
            NCursesUI.DecoratedWindow.__init__( self, "Command Line Window", x, y, width, height )

    #-------------------------------------------------------------------------#
    class ShellInputWindow( Window ):
    #-------------------------------------------------------------------------#
        """Interactive Command Line Input"""
        def __init__( self, x, y, width, height ):
            NCursesUI.Window.__init__( self, x, y, width, height )

#            self.textbox = Textbox( self.win )
#            t = threading.Thread()
#            t.run = self.textbox.edit
#            t.start()

    #-------------------------------------------------------------------------#
    def main(self, stdscr, frontend, eventHandler):
    #-------------------------------------------------------------------------#
        height, width = stdscr.getmaxyx()

        # for now split it like that:
        # MAIN_y + THREAD_y = 2/3 screen at the top
        # MAIN_x = 2/3 left, THREAD_y = 1/3 right
        # CLI_y = 1/3 of screen at the bottom
        # CLI_x = full

        main_left = 0
        main_top = 4
        main_height = ( height / 3 * 2 )
        main_width = ( width / 3 ) * 2
        clo_left = main_left
        clo_top = main_top + main_height
        clo_height = height - main_height - main_top - 1
        clo_width = width
        cli_left = main_left
        cli_top = clo_top + clo_height
        cli_height = 1
        cli_width = width
        thread_left = main_left + main_width
        thread_top = main_top
        thread_height = main_height
        thread_width = width - main_width

        tw = self.TitleWindow( 0, 0, width, main_top )
        mw = self.MainWindow( main_left, main_top, main_width, main_height )
        taw = self.ThreadActivityWindow( thread_left, thread_top, thread_width, thread_height )
        clo = self.ShellOutputWindow( clo_left, clo_top, clo_width, clo_height )
        cli = self.ShellInputWindow( cli_left, cli_top, cli_width, cli_height )
        cli.setText( 0, 0, "BB>" )

#        mw.drawHline( 2 )

        helper = uihelper.BBUIHelper()
   
        try:
            cmdline = frontend.runCommand(["getCmdLineAction"])
            #print cmdline
            if not cmdline:
                return
            ret = frontend.runCommand(cmdline)
            if ret != True:
                print "Couldn't get default commandlind! %s" % ret
                return
        except xmlrpclib.Fault, x:
            print "XMLRPC Fault getting commandline:\n %s" % x
            return

        exitflag = False
        while not exitflag:
            try:
                event = eventHandler.waitEvent(0.25)
                if not event:
                    continue
                helper.eventHandler(event)
                #mw.appendText("%s\n" % event[0])
                if event[0].startswith('bb.event.Pkg'):
                    mw.appendText("NOTE: %s\n" % event[1]['_message'])
                if event[0].startswith('bb.build.Task'):
                    mw.appendText("NOTE: %s\n" % event[1]['_message'])
                if event[0].startswith('bb.msg.MsgDebug'):
                    mw.appendText('DEBUG: ' + event[1]['_message'] + '\n')
                if event[0].startswith('bb.msg.MsgNote'):
                    mw.appendText('NOTE: ' + event[1]['_message'] + '\n')
                if event[0].startswith('bb.msg.MsgWarn'):
                    mw.appendText('WARNING: ' + event[1]['_message'] + '\n')
                if event[0].startswith('bb.msg.MsgError'):
                    mw.appendText('ERROR: ' + event[1]['_message'] + '\n')
                if event[0].startswith('bb.msg.MsgFatal'):
                    mw.appendText('FATAL: ' + event[1]['_message'] + '\n')
                if event[0].startswith('bb.event.ParseProgress'):
                    x = event[1]['sofar']
                    y = event[1]['total']
                    taw.setText(0, 0, "Parsing: %s (%04d/%04d) [%2d %%]" % ( parsespin.next(), x, y, x*100/y ) )
                    if x == y:
                        mw.appendText("Parsing finished. %d cached, %d parsed, %d skipped, %d masked." 
                                % ( event[1]['cached'], event[1]['parsed'], event[1]['skipped'], event[1]['masked'] ))
#                if event[0].startswith('bb.build.TaskFailed'):
#                    if event[1]['logfile']:
#                        if data.getVar("BBINCLUDELOGS", d):
#                            bb.msg.error(bb.msg.domain.Build, "log data follows (%s)" % logfile)
#                            number_of_lines = data.getVar("BBINCLUDELOGS_LINES", d)
#                            if number_of_lines:
#                                os.system('tail -n%s %s' % (number_of_lines, logfile))
#                            else:
#                                f = open(logfile, "r")
#                                while True:
#                                    l = f.readline()
#                                    if l == '':
#                                        break
#                                    l = l.rstrip()
#                                    print '| %s' % l
#                                f.close()
#                        else:
#                            bb.msg.error(bb.msg.domain.Build, "see log in %s" % logfile)


                if event[0] == 'bb.command.CookerCommandCompleted':
                    exitflag = True
                if event[0] == 'bb.command.CookerCommandFailed':
                    mw.appendText("Command execution failed: %s" % event[1]['error'])
                    time.sleep(2)
                    exitflag = True
                if event[0] == 'bb.cooker.CookerExit':
                    exitflag = True

                tasks = helper.getTasks()
                if tasks:
                    taw.setText(0, 0, "Active Tasks:\n")
                for task in tasks:
                    taw.appendText(task)

                curses.doupdate()
            except KeyboardInterrupt:
                exitflag = True

def init(frontend, eventHandler):
    ui = NCursesUI()
    curses.wrapper(ui.main, frontend, eventHandler)    
