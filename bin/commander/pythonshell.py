#!/usr/bin/env python
# -*- coding: iso8859-15 -*-
#------------------------------------------------------------------------#
# This file is part of the ELAN environment - http://elan.wox.org
# (C) 2002-2004 Michael 'Mickey' Lauer <mickey@tm.informatik.uni-frankfurt.de>
#
# Licensed under GPL
#------------------------------------------------------------------------#
# $Id$
# $Source$
#------------------------------------------------------------------------#

"""Implements a Python Interpreter embedded in a QMultiLineEditor"""

__revision__ = "$Revision$"
__version__ = __revision__.replace('$','').replace('Revision:','').strip()
__author__ = "Michael 'Mickey' Lauer <mickey@tm.informatik.uni-frankfurt.de>"

#------------------------------------------------------------------------#
from Queue import Queue
import sys
#------------------------------------------------------------------------#
import qt
import code
import rlcompleter
#------------------------------------------------------------------------#

class EPythonShell( qt.QMultiLineEdit ):
    """An interactive Python interpreter shell embedded in a QMultiLine editor."""

    class Output:
        def __init__( self, writefunc ):
            self.writefunc = writefunc
        def write( self, line ):
            if line != "\n":
                map( self.writefunc, line.split("\n") )

    def __init__( self, parent, localdict={} ):
        qt.QMultiLineEdit.__init__( self, parent )
        qt.QObject.connect( self, qt.SIGNAL( "returnPressed()" ), self.slotReturnPressed )
        self.setFont( qt.QFont( "Fixed", 8 ) )
        
        self.history = []
        self.pointer = 0
        self.cmdFromHistory = False
        self.console = code.InteractiveConsole( localdict )
        self.completer = rlcompleter.Completer()
        self.possibleCompletions = []

        # We're overriding the prompts just in case someone set up prompt coloring
        sys.ps1 = ">>> "
        sys.ps2 = "... "

        cprt = 'Type "copyright", "credits" or "license" for more information.'
        self.append( "Python %s on %s\n%s" % ( sys.version, sys.platform, cprt ) )
        self.append( sys.ps1 )
        self.more, self.prompt = 0, sys.ps1
        self.output = EPythonShell.Output( self.writeResult )
        self.stdout = sys.stdout
        self.stderr = sys.stderr

        self.cursorToEnd()

    def isQt3( self ):
        return qt.qVersion()[0] == '3'
    
    def keyPressEvent( self, e ):
        """Intercept certain key press events and handle them to provide
        command line history and attribute name completion."""

        if ( e.key() == qt.Qt.Key_Up ):
            if not self.pointer > 0:
                return    
            row, col = self.getCursorPosition()
            self.home()
            self.killLine()
            if self.pointer > 0:
                self.pointer -= 1
            self.append( "%s" % self.history[self.pointer] )
            self.end()
            self.cmdFromHistory = True
            return
            
        elif ( e.key() == qt.Qt.Key_Down ):
            if not self.pointer < len( self.history )-1:
                return
            self.pointer += 1
            row, col = self.getCursorPosition()
            self.home()
            self.killLine()
            self.append( "%s" % self.history[self.pointer] )
            self.end()
            self.cmdFromHistory = True
            return
            
        elif e.key() == qt.Qt.Key_Return:
            self.end()
        
        elif e.key() == qt.Qt.Key_Tab:
            row, col = self.getCursorPosition()
            line = str( self.textLine( row ) )[4:]
            
            if len( self.possibleCompletions ) == 1:
                self.home()
                self.killLine()
                self.append( ">>> %s" % self.possibleCompletions[0] )
                self.end()
            else:
                print >>sys.stderr, repr( self.possibleCompletions )
            return
        
        self.cmdFromHistory = False
       
        qt.QMultiLineEdit.keyPressEvent( self, e )

    def keyReleaseEvent( self, e ):
        if e.key() == qt.Qt.Key_Up:
            return
        
        #
        # try command line completion
        #
        
        if str( e.key() )[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.":
            row, col = self.getCursorPosition()
            line = str( self.textLine( row ) )[4:]
            possibleCompletions = []
            state = 0
            if len( line ) > 1:
                while True:
                    try:
                        nextCompletion = self.completer.complete( line, state )
                    except Exception, why:
                        #print >>sys.stderr, why
                        break
                    if not nextCompletion is None:
                        possibleCompletions.append( nextCompletion )
                        state += 1
                    else:
                        break

                #print >> sys.stderr, "'%s': possible completions: %s" % ( line, repr( possibleCompletions ) )
                self.possibleCompletions = possibleCompletions

            qt.QMultiLineEdit.keyReleaseEvent( self, e )

    def cursorToEnd( self ):
        """Move the cursor to the end of the view."""
        
        # In Qt3, the QMultiLineEdit is derived from QTextEdit and deals in terms
        # of paragraphs and no longer lines. QTextEdit.setCursorPosition() doesn't
        # work as expected here, so we're faking a CTRL+END key here to achieve the
        # same effect :-)
        
        if self.isQt3():
            event = qt.QKeyEvent( qt.QKeyEvent.KeyPress, qt.Qt.Key_End, 0, qt.Qt.ControlButton )
            qt.qApp.postEvent( self, event )
        else:
            rows = self.numLines()
            self.setCursorPosition( rows, 4 )
            self.end()

    def removeLastLine( self ):
        self.removeLine( self.numLines()-1 )

    def writeResult( self, result ):
        if result == "":
            return
        #print >> self.stdout, "appending '%s'" % result
        self.append( result )

    def handleInput( self, line ):  
        if len( line ) > 5 and not self.cmdFromHistory:
            self.history.append( line )
            
        self.pointer = len( self.history )
        sys.stdout, sys.stderr = self.output, self.output
        self.more = self.console.push( line[4:] )
        sys.stdout, sys.stderr = self.stdout, self.stderr

    def slotReturnPressed( self ):
        row, col = self.getCursorPosition()
        self.removeLine( row )
        line = str( self.textLine( row-1 ) )
        #print "text sending to interpreter: '%s'" % line
        self.handleInput( line )
        if self.more:
            self.prompt = sys.ps2
        else:
            self.prompt = sys.ps1
        self.append( self.prompt )
        self.cursorToEnd()

#------------------------------------------------------------------------#
if __name__ == "__main__":
    
    a = qt.QApplication( sys.argv )
    w = EPythonShell( None )
    w.resize( qt.QSize( 640, 480 ) )
    w.show()
    a.setMainWidget( w )
    a.exec_loop()
