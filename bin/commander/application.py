#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from commander.mainwindow import MainWindow
from qt import qApp, QTimer, QApplication, SIGNAL, SLOT

class CommanderApplication( QApplication ):
    
    def __init__( self, argv ):
        QApplication.__init__( self, argv )

    def initialize( self ):
        self.mw = MainWindow()
        self.mw.show()
        self.setMainWidget( self.mw )
    
        QTimer.singleShot( 0, self.mw.buildRescanPackages )

    def run( self ):
        self.connect( self, SIGNAL( "lastWindowClosed()" ), self, SLOT( "quit()" ) )
        print "--> exec_loop()"
        self.exec_loop()
        print "<-- exec_loop()"
        
#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

if __name__ == "__main__":
    import sys
    from qt import *
    app = CommanderApplication( sys.argv )
    app.exec_loop()
