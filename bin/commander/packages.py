#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from oe import data, event, parse, debug, build, make
import copy, glob, os, sys

class Packages:
    """Provide a higher level API to the OE package data"""
    __instance = None

    def __init__( self, cfg = {} ):
        print "Packages.__init__()"
        make.cfg = cfg
        make.pkgdata = {}
        make.pkgs = {}
        self.valid = False

        try:
            make.cfg = parse.handle("conf/oe.conf", make.cfg )
        except IOError:
            fatal("Unable to open oe.conf")

    def instance():
        if Packages.__instance is None:
            Packages.__instance = Packages()
        return Packages.__instance

    instance = staticmethod( instance )

    def numPackages( self ):
        return len( make.pkgdata )

    def names( self ):
        return make.pkgdata.keys()

    def isVirtual( self, package ):
        return "virtual" in data.getVar( "PROVIDES", make.pkgdata[package], 1 ) # Python 2.3 only

    def data( self, package, key ):
        if package in make.pkgdata and key in make.pkgdata[package]:
            return data.getVar( key, make.pkgdata[package], 1 )
        else:
            return "N/A"

    def getVar( self, key ):
        return data.getVar( key, make.cfg )

    def scan( self, progressCallback ):
        make.collect_oefiles( progressCallback )


#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

if __name__ == "__main__":
    def function( *args, **kwargs ):
        print args, kwargs

    p = Packages( cfg )
    p.scan( function )