#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

Classes for obtaining upstream sources for the
BitBake build tools.

Copyright (C) 2003, 2004  Chris Larson

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc., 59 Temple
Place, Suite 330, Boston, MA 02111-1307 USA. 

Based on functions from the base bb module, Copyright 2003 Holger Schurig
"""

import os, re
import sys
import bb
from   bb import data
from   bb.fetch import Fetch
from   bb.fetch import FetchError
from   bb.fetch import MissingParameterError

class Svn(Fetch):
    """Class to fetch a module or modules from svn repositories"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with svn.
        """
        return ud.type in ['svn']

    def localpath(self, url, ud, d):
        if not "module" in ud.parm:
            raise MissingParameterError("svn method needs a 'module' parameter")
        else:
            module = ud.parm["module"]

        ud.revision = ""
        if 'rev' in parm:
            ud.revision = ud.parm['rev']

        ud.localfile = data.expand('%s_%s_%s_%s_%s.tar.gz' % (module.replace('/', '.'), ud.host, ud.path.replace('/', '.'), ud.revision, ud.date), d)

        return os.path.join(data.getVar("DL_DIR", d, 1), )

    def go(self, loc, ud, d):
        """Fetch url"""

        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', "svn:%s" % data.getVar('OVERRIDES', localdata), localdata)
        data.update_data(localdata)

        if not "module" in ud.parm:
            raise MissingParameterError("svn method needs a 'module' parameter")
        else:
            module = ud.parm["module"]

        dlfile = self.localpath(loc, localdata)
        dldir = data.getVar('DL_DIR', localdata, 1)

        # setup svn options
        options = []

        if "proto" in ud.parm:
            proto = ud.parm["proto"]
        else:
            proto = "svn"

        svn_rsh = None
        if proto == "svn+ssh" and "rsh" in ud.parm:
            svn_rsh = ud.parm["rsh"]

        tarfn = ud.localfile

        # try to use the tarball stash
        if Fetch.check_for_tarball(d, tarfn, dldir, ud.date):
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists or was mirrored, skipping svn checkout." % tarfn)
            return

        olddir = os.path.abspath(os.getcwd())
        os.chdir(data.expand(dldir, localdata))

        svnroot = ud.host + ud.path

        # either use the revision, or SRCDATE in braces, or nothing for SRCDATE = "now"
        if ud.revision:
            options.append("-r %s" % ud.revision)
        elif ud.date != "now":
            options.append("-r {%s}" % ud.date)

        data.setVar('SVNROOT', "%s://%s/%s" % (proto, svnroot, module), localdata)
        data.setVar('SVNCOOPTS', " ".join(options), localdata)
        data.setVar('SVNMODULE', module, localdata)
        svncmd = data.getVar('FETCHCOMMAND', localdata, 1)
        svnupcmd = data.getVar('UPDATECOMMAND', localdata, 1)

        if svn_rsh:
            svncmd = "svn_RSH=\"%s\" %s" % (svn_rsh, svncmd)
            svnupcmd = "svn_RSH=\"%s\" %s" % (svn_rsh, svnupcmd)

        pkg=data.expand('${PN}', d)
        pkgdir=os.path.join(data.expand('${SVNDIR}', localdata), pkg)
        moddir=os.path.join(pkgdir, module)
        bb.msg.debug(2, bb.msg.domain.Fetcher, "Fetch: checking for module directory '" + moddir + "'")

        if os.access(os.path.join(moddir,'.svn'), os.R_OK):
            bb.msg.note(1, bb.msg.domain.Fetcher, "Update " + loc)
            # update sources there
            os.chdir(moddir)
            bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % svnupcmd)
            myret = os.system(svnupcmd)
        else:
            bb.msg.note(1, bb.msg.domain.Fetcher, "Fetch " + loc)
            # check out sources there
            bb.mkdirhier(pkgdir)
            os.chdir(pkgdir)
            bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % svncmd)
            myret = os.system(svncmd)

        if myret != 0:
            raise FetchError(module)

        os.chdir(pkgdir)
        # tar them up to a defined filename
        myret = os.system("tar -czf %s %s" % (os.path.join(dldir,tarfn), os.path.basename(module)))
        if myret != 0:
            try:
                os.unlink(tarfn)
            except OSError:
                pass
        os.chdir(olddir)
