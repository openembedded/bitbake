#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

import os
from qt import *
from appinfo import *
from packages import Packages

class ProviderItem( QListViewItem ): #QCheckListItem

    columns = { "PROVIDES":     0,
                "CHECK":        1,
                "unpack":2, "patch":3, "configure":4, "compile":5, "stage":6, "install":7,
                "STATUS":       8,
                "CATEGORY":     9,
                "SECTION":      10,
                "PRIORITY":     11,
                "MAINTAINER":   12,
                "SRC_URI":      13,
                "HOMEPAGE":     14,
                "DEPENDS":      15,
                "RDEPENDS":     16,
                "SHORTNAME":    17 }

    icons = {}
    
    def __init__( self, parent, provider, virtual = False ):
        
        if not ProviderItem.icons:
            ProviderItem.icons =  { "unpack"    : QPixmap( imageDir + "do_unpack.png" ),
               "patch"     : QPixmap( imageDir + "do_patch.png" ),
               "configure" : QPixmap( imageDir + "do_configure.png" ),
               "compile"   : QPixmap( imageDir + "do_compile.png" ),
               "stage"     : QPixmap( imageDir + "do_stage.png" ),
               "install"   : QPixmap( imageDir + "do_install.png" ) }

        self.parent = parent
        self.virtual = virtual
        self.p = Packages.instance()
        self.fullname = provider
        self.shortname = provider.split( "/" )[-1]
        # <HACK>
        # Caution! I have absolutely no idea if it is correct to assume, that
        # the last provider is the most unspecific one... for now this seems to work :)
        # </HACK>
        self.mup = self.mupValue()
        self.virtualp = self.virtualValue()
        
        print "ProviderItemInit: FN='%s' SN='%s', VP='%s', MUP='%s'" % ( self.fullname, self.shortname, self.virtualp, self.mup )
        
        if self.mup == "N/A":
            print "Warning: MUP of '%s' seems to be not available." % provider
            
        if virtual:
            QListViewItem.__init__( self, parent, provider )
            return
    
        if self.virtualp:
            #
            # check if a corresponding virtual parent element already has been added
            #
            vparent = parent.findItem( self.virtualp, 0 )
            if not vparent:
                vparent = ProviderItem( parent, self.virtualp, True )
                vparent.setPixmap( 0, QPixmap( imageDir + "virtual.png" ) )

            QListViewItem.__init__( self, vparent, provider )
            #QCheckListItem.__init__( self, vparent, provider, QCheckListItem.CheckBox )           
            
        else:
            #
            # check if a corresponding mup parent element already has been added
            #
            vparent = parent.findItem( self.mup, 0 )
            if not vparent:
                vparent = ProviderItem( parent, self.mup, True )
                vparent.setPixmap( 0, QPixmap( imageDir + "virtual.png" ) )          
            QListViewItem.__init__( self, vparent, provider )

        self.decorate()
        self.syncStatus()
        self.setPixmap( 0, QPixmap( imageDir + "package.png" ) )       
        self.setCheckStatus( False )
        
    def getVar( self, value ):
        return self.p.data( self.fullname, value )
    
    def virtualValue( self ):
        #print self.p.data(self.fullname, "PROVIDES" )
        providers = self.p.data(self.fullname, "PROVIDES" ).split()
        for p in providers:
            if p.split( '/' )[0] == "virtual": return p

    def mupValue( self ):
        providers = self.p.data( self.fullname, "PROVIDES" ).split()
        return providers[-1]
            
    def setCheckStatus( self, checked ):
        self.checked = checked
        if self.checked:
            self.setPixmap( 1, QPixmap( imageDir + "checked.png" ) )
        else:
            self.setPixmap( 1, QPixmap( imageDir + "unchecked.png" ) )
            
    def setBuildStatus( self, *args, **kwargs ):
        for el in kwargs:
            if el in ProviderItem.columns:
                self.setPixmap( ProviderItem.columns[el], ( QPixmap(), ProviderItem.icons[el] )[ kwargs[el] ] )
        if "status" in kwargs:
            self.setText( ProviderItem.columns["STATUS"], kwargs["status"] )
        
    def decorate( self ):
        if self.fullname.startswith( "virtual" ):
            return
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
        
    def syncStatus( self ):
        if self.virtual:
            return    
        
        status = {}
        for el in "unpack patch configure compile stage install".split():
            statname = "%s/stamps/%s-%s-%s.do_%s" % ( self.p.getVar( "TMPDIR" ),
                                                      self.getVar( "PN" ),
                                                      self.getVar( "PV" ),
                                                      self.getVar( "PR" ),
                                                      el )
            #print "stat'ing", statname,
            try:
                os.stat( statname )
            except OSError:
                status[el] = False
                #print "not found."
            else:
                status[el] = True
                #print "found."
                
        print "status for package", self.shortname, "=", status
        apply( self.setBuildStatus, (), status )

    def st( self, column, value ):
        self.setText( ProviderItem.columns[column], value )
        
    def toggleCheck( self ):
        self.setCheckStatus( not self.checked )

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

