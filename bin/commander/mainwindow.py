#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from appinfo import *
from mainwindowbase import *
from aboutdialog import *
from packages import Packages
from pythonshell import EPythonShell
from oe import *

class MainWindow( MainWindowBase ):

    def __init__( self, parent = None, name = None, fl = 0 ):
        MainWindowBase.__init__(self, parent, name, fl )
        
        self.createStatusBar()
        
    def createStatusBar( self ):
        self.numPackages = QLabel( "No Packages available.", self.statusBar() )
        self.statusBar().addWidget( self.numPackages )
    
    #
    # slots
    #

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
        self.close()

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
   
    def editPreferences(self):
        print "MainWindowBase.editPreferences(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )
    
    def helpIndex(self):
        print "MainWindowBase.helpIndex(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def helpContents(self):
        print "MainWindowBase.helpContents(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def buildAllPackages(self):
        print "MainWindowBase.buildAllPackages(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )
    
    def buildSelectedPackages(self):
        print "MainWindowBase.buildSelected(): Not implemented yet"
        QMessageBox.information( self, "%s V%s" % ( appname, appversion ), "Not implemented yet" )

    def buildRescanPackages(self):
        d = QProgressDialog( "<p>Rescanning Packages...<br>Please wait...</p>", "Cancel", 100, None, "dlgrescan", False )
        d.setCaption( appcaption )
        d.show()
        p = Packages.instance()
        self.statusBar().message( "Rescanning Packages - please wait..." )
        p.scan( lambda current, last, name: d.setProgress( current, last ) or
                                            qApp.processEvents() or
                                            d.setLabelText( "<p>Rescanning Packages...<br>%s</p>" % name.split( "/" )[-1] ) )
        d.hide()
        self.statusBar().message( "Done. Scanned %d Packages." % p.numPackages(), 2000 )
        self.numPackages.setText( "%s Packages available." % p.numPackages() )
        
        self.packageView.clear()
        for package in p.names():
            shortname = package.split( "/" )[-1]
            item = QListViewItem( self.packageView,
                           p.data(package, "PROVIDES" ).split()[0],
                           p.data(package, "CATEGORY"),
                           p.data(package, "SECTION"),
                           p.data(package, "PRIORITY"),
                           p.data(package, "MAINTAINER"),
                           p.data(package, "SRC_URI"),
                           p.data(package, "HOMEPAGE") )
            item.setText( 7, p.data(package, "DEPENDS") )
            item.setText( 8, p.data(package, "RDEPENDS") )
            item.setText( 9, shortname )
        
    def debugConsole(self):
        shell = EPythonShell( None, { 'p':Packages.instance(), 'data':data, 'exit':lambda:shell.close() } )
        shell.show()
        shell.resize( QSize( 500, 300 ) )
    
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

