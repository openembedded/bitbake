#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from qt import *
from packages import Packages
import os

imageDir = "%s/bin/commander/images/" % os.environ["OEDIR"]

class ProviderItem( QListViewItem ):

    columns = { "PROVIDES":     0,
                "CATEGORY":     1,
                "SECTION":      2,
                "PRIORITY":     3,
                "MAINTAINER":   4,
                "SRC_URI":      5,
                "HOMEPAGE":     6,
                "DEPENDS":      7,
                "RDEPENDS":     8,
                "SHORTNAME":    9 }

    def __init__( self, parent, provider ):
        self.parent = parent
        self.p = Packages.instance()
        self.fullname = provider
        self.shortname = provider.split( "/" )[-1]
        self.virtual = self.virtualValue()

        if self.virtual:
            #
            # check if a corresponding parent element already has been added
            #
            vparent = parent.findItem( self.virtual, 0 )
            if not vparent:
                vparent = ProviderItem( parent, self.virtual )
                vparent.setPixmap( 0, QPixmap( imageDir + "virtual.png" ) )

            QListViewItem.__init__( self, vparent, provider )
        else:
            QListViewItem.__init__( self, parent, provider )

        self.decorate()
        self.setPixmap( 0, QPixmap( imageDir + "package.png" ) )


    def virtualValue( self ):
        #print self.p.data(self.fullname, "PROVIDES" )
        providers = self.p.data(self.fullname, "PROVIDES" ).split()
        for p in providers:
            if p.split( '/' )[0] == "virtual": return p

    def decorate( self ):
        if not self.fullname.startswith( "virtual" ):
            self.st( "PROVIDES", self.fullname.split('/')[-1] )
        self.st( "CATEGORY", self.p.data(self.fullname, "CATEGORY") )
        self.st( "SECTION", self.p.data(self.fullname, "SECTION") )
        self.st( "PRIORITY", self.p.data(self.fullname, "PRIORITY") )
        self.st( "MAINTAINER", self.p.data(self.fullname, "MAINTAINER") )
        self.st( "SRC_URI", self.p.data(self.fullname, "SRC_URI") )
        self.st( "HOMEPAGE", self.p.data(self.fullname, "HOMEPAGE") )
        self.st( "DEPENDS", self.p.data(self.fullname, "DEPENDS") )
        self.st( "RDEPENDS", self.p.data(self.fullname, "RDEPENDS") )
        self.st( "SHORTNAME", self.shortname )

    def st( self, column, value ):
        self.setText( ProviderItem.columns[column], value )

#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

if __name__ == "__main__":
    import sys
    from qt import *
    app = QApplication( sys.argv )
    mw = QListView()
    app.setMainWidget( mw )
    app.exec_loop()

