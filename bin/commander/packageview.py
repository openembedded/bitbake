#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from qt import *
from packages import Packages
from appinfo import *
connect = QObject.connect

class PackageView( QListView ):

    columns = "PROVIDES CHECK A B C D E F STATUS CATEGORY SECTION PRIORITY MAINTAINER SRC_URI HOMEPAGE DEPENDS RDEPENDS SHORTNAME".split()
    coldict = {}
    for i in range( 0, len( columns ) ):
        coldict[ columns[i] ] = i

    def __init__( self, *args ):
        QListView.__init__( self, *args )

        for c in PackageView.columns:
            if len( c ) > 1: self.addColumn( c.title() )
            else: self.addColumn( "  " )

        self.setColumnWidthMode( 2, QListView.Manual )
        self.setColumnWidthMode( 3, QListView.Manual )
        self.setColumnWidthMode( 4, QListView.Manual )
        self.setColumnWidthMode( 5, QListView.Manual )
        self.setColumnWidthMode( 6, QListView.Manual )
        self.setColumnWidthMode( 7, QListView.Manual )
        
        header = self.header()
                
        header.setLabel( 0, QIconSet( QPixmap( imageDir + "package.png" ) ), "Provider" )
        
        header.setLabel( 2, QIconSet( QPixmap( imageDir + "do_unpack.png" ) ), "" )
        header.setLabel( 3, QIconSet( QPixmap( imageDir + "do_patch.png" ) ), "" )
        header.setLabel( 4, QIconSet( QPixmap( imageDir + "do_configure.png" ) ), "" )
        header.setLabel( 5, QIconSet( QPixmap( imageDir + "do_compile.png" ) ), "" )
        header.setLabel( 6, QIconSet( QPixmap( imageDir + "do_stage.png" ) ), "" )
        header.setLabel( 7, QIconSet( QPixmap( imageDir + "do_install.png" ) ), "" )


        self.setRootIsDecorated( True )
        self.setAllColumnsShowFocus( True )
        self.setShowSortIndicator( True )
        self.setShowToolTips( True )
        self.setColumnAlignment( PackageView.coldict["CHECK"], Qt.AlignCenter )
        
        connect( self, SIGNAL( "mouseButtonClicked( int, QListViewItem*, const QPoint&, int )" ),
                 self.handleMouseButtonClicked )
                 
    def handleMouseButtonClicked( self, button, item, pos, col ):
        if item and col == self.coldict["CHECK"]: item.toggleCheck()
        
    def expandAll( self, expand = True ):
        it = QListViewItemIterator( self )
        while it.current():
            it.current().setOpen( expand )
            it += 1
            
#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

if __name__ == "__main__":
    import sys
    from qt import *
    app = QApplication( sys.argv )
    mw = PackageView()
    app.setMainWidget( mw )
    app.exec_loop()

