#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from appinfo import *
from mainwindowbase import *
from aboutdialog import *

class MainWindow( MainWindowBase ):

    def __init__( self, parent = None, name = None, fl = 0 ):
        MainWindowBase.__init__(self, parent, name, fl )

    def fileNew(self):
        print "MainWindowBase.fileNew(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def fileOpen(self):
        print "MainWindowBase.fileOpen(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def fileSave(self):
        print "MainWindowBase.fileSave(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def fileSaveAs(self):
        print "MainWindowBase.fileSaveAs(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def filePrint(self):
        print "MainWindowBase.filePrint(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def fileExit(self):
        print "MainWindowBase.fileExit(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def editUndo(self):
        print "MainWindowBase.editUndo(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def editRedo(self):
        print "MainWindowBase.editRedo(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def editCut(self):
        print "MainWindowBase.editCut(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def editCopy(self):
        print "MainWindowBase.editCopy(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def editPaste(self):
        print "MainWindowBase.editPaste(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def editFind(self):
        print "MainWindowBase.editFind(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def helpIndex(self):
        print "MainWindowBase.helpIndex(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def helpContents(self):
        print "MainWindowBase.helpContents(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def helpAbout(self):
        d = AboutDialog()
        d.exec_loop()

#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

if __name__ == "__main__":
    import sys
    from qt import *
    app = QApplication( sys.argv )
    mw = MainWindow()
    mw.show()
    app.setMainWidget( mw )
    app.exec_loop()

