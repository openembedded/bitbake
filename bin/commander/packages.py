#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from oe import data, event, parse, debug, build
import copy, glob, os, sys

class Packages:
    """Provide a higher level API to the OE package data"""
    __instance = None

    def __init__( self, cfg = {} ):
        print "Packages.__init__()" 
        self.cfg = cfg
        self.pkgdata = {}
        self.pkgs = {}
        self.valid = False

        try:
            self.cfg = parse.handle("conf/oe.conf", self.cfg )
        except IOError:
            fatal("Unable to open oe.conf")  
               
    def instance():
        if Packages.__instance is None:
            Packages.__instance = Packages()
        return Packages.__instance
        
    instance = staticmethod( instance )

    def numPackages( self ):
        return len( self.pkgdata )
        
    def names( self ):
        return self.pkgdata.keys()
        
    def data( self, package, key ):
        if package in self.pkgdata and key in self.pkgdata[package]:
            return data.getVar( key, self.pkgdata[package], 1 )
        else:
            return "N/A"
    
    def load( self, oefile ):
        """Load and parse one .oe build file"""
        oepath = data.getVar('OEPATH', self.cfg)
        topdir = data.getVar('TOPDIR', self.cfg)
        if not topdir:
                topdir = os.path.abspath(os.getcwd())
                # set topdir to here
                data.setVar('TOPDIR', topdir, self.cfg)
        oefile = os.path.abspath(oefile)
        oefile_loc = os.path.abspath(os.path.dirname(oefile))
        # expand tmpdir to include this topdir
        data.setVar('TMPDIR', data.getVar('TMPDIR', self.cfg, 1) or "", self.cfg)
        # add topdir to oepath
        oepath += ":%s" % topdir
        # set topdir to location of .oe file
        topdir = oefile_loc
        #data.setVar('TOPDIR', topdir, cfg)
        # add that topdir to oepath
        oepath += ":%s" % topdir
        # go there
        oldpath = os.path.abspath(os.getcwd())
        os.chdir(topdir)
        data.setVar('OEPATH', oepath, self.cfg)
        newcfg = copy.deepcopy(self.cfg)
        try:
                parse.handle(oefile, newcfg) # read .oe data
                os.chdir(oldpath)
                return newcfg
        except IOError, OSError:
                print "error!"
                os.chdir(oldpath)
                return None
              
    def scan( self, progressCallback = None ):
        """Read and parse all available .oe files"""
        files = (data.getVar( "OEFILES", self.cfg, 1 ) or "").split()
        data.setVar("OEFILES", " ".join(files), self.cfg)
        
        l = len( files )
        for i in range( l ):
            f = files[i]
            progressCallback( i, l, f )
                        
            globbed = glob.glob(f) or [ f ]
            if globbed:
                    if [ f ] != globbed:
                            files += globbed
                            continue
            
            # read a file's metadata
            try:
                self.pkgdata[f] = self.load(f)
                deps = None
                if self.pkgdata[f] is not None:
                    # allow metadata files to add items to OEFILES
                    #data.update_data(pkgdata[f])
                    addoefiles = data.getVar('OEFILES', self.pkgdata[f]) or None
                    if addoefiles:
                        for aof in addoefiles.split():
                            if not files.count(aof):
                                if not os.path.isabs(aof):
                                    aof = os.path.join(os.path.dirname(f),aof)
                                files.append(aof)
                    for var in self.pkgdata[f].keys():
                        if data.getVarFlag(var, "handler", self.pkgdata[f]) and data.getVar(var, self.pkgdata[f]):
                            event.register(data.getVar(var, self.pkgdata[f]))
                    depstr = data.getVar("DEPENDS", self.pkgdata[f], 1)
                    if depstr is not None:
                        deps = depstr.split()
                    pkg = []
                    pkg.append(data.getVar('CATEGORY', self.pkgdata[f], 1))
                    pkg.append(data.getVar('PN', self.pkgdata[f], 1))
                    pkg.append(data.getVar('PV', self.pkgdata[f], 1))
                    pkg.append(data.getVar('PR', self.pkgdata[f], 1))
                    root = "%s/%s-%s-%s" % (pkg[0], pkg[1], pkg[2], pkg[3])
                    provides = []
                    providestr = data.getVar("PROVIDES", self.pkgdata[f], 1)
                    if providestr is not None:
                            provides += providestr.split()
                    for provide in provides:
                            self.pkgs[provide] = [[root], None]
                    self.pkgs[root] = [deps, f]
            
            except IOError:
                print "error opening %s" % f
                
#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

if __name__ == "__main__":
    def function( *args, **kwargs ):
        print args, kwargs

    p = Packages( cfg )
    p.scan( function )