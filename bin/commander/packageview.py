#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from qt import *
from packages import Packages

class PackageView( QListView ):

    columns = "PROVIDES CHECK STATUS CATEGORY SECTION PRIORITY MAINTAINER SRC_URI HOMEPAGE DEPENDS RDEPENDS SHORTNAME".split()
    coldict = {}
    for i in range( 0, len( columns ) ):
        coldict[ columns[i] ] = i

    def __init__( self, *args ):
        QListView.__init__( self, *args )

        for c in PackageView.columns:
            self.addColumn( c.title() )

        self.setRootIsDecorated( True )

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

