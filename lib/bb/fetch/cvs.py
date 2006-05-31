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
import bb
from   bb import data
from   bb.fetch import Fetch
from   bb.fetch import FetchError
from   bb.fetch import MissingParameterError

class Cvs(Fetch):
    """Class to fetch a module or modules from cvs repositories"""
    def supports(url, d):
        """Check to see if a given url can be fetched with cvs.
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))
        return type in ['cvs', 'pserver']
    supports = staticmethod(supports)

    def localpath(url, d):
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]

        if not "module" in parm:
            raise MissingParameterError("cvs method needs a 'module' parameter")
        else:
            module = parm["module"]
        if 'tag' in parm:
            tag = parm['tag']
        else:
            tag = ""
        if 'date' in parm:
            date = parm['date']
        else:
            if not tag:
                date = Fetch.getSRCDate(d)
            else:
                date = ""

        return os.path.join(data.getVar("DL_DIR", d, 1),data.expand('%s_%s_%s_%s.tar.gz' % ( module.replace('/', '.'), host, tag, date), d))
    localpath = staticmethod(localpath)

    def go(self, d, urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', "cvs:%s" % data.getVar('OVERRIDES', localdata), localdata)
        data.update_data(localdata)

        for loc in urls:
            (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(loc, localdata))
            if not "module" in parm:
                raise MissingParameterError("cvs method needs a 'module' parameter")
            else:
                module = parm["module"]

            dlfile = self.localpath(loc, localdata)
            dldir = data.getVar('DL_DIR', localdata, 1)
#           if local path contains the cvs
#           module, consider the dir above it to be the
#           download directory
#           pos = dlfile.find(module)
#           if pos:
#               dldir = dlfile[:pos]
#           else:
#               dldir = os.path.dirname(dlfile)

#           setup cvs options
            options = []
            if 'tag' in parm:
                tag = parm['tag']
            else:
                tag = ""

            if 'date' in parm:
                date = parm['date']
            else:
                if not tag:
                    date = Fetch.getSRCDate(d)
                else:
                    date = ""

            if "method" in parm:
                method = parm["method"]
            else:
                method = "pserver"

            if "localdir" in parm:
                localdir = parm["localdir"]
            else:
                localdir = module

            cvs_rsh = None
            if method == "ext":
                if "rsh" in parm:
                    cvs_rsh = parm["rsh"]

            tarfn = data.expand('%s_%s_%s_%s.tar.gz' % (module.replace('/', '.'), host, tag, date), localdata)
            data.setVar('TARFILES', dlfile, localdata)
            data.setVar('TARFN', tarfn, localdata)

            if Fetch.check_for_tarball(d, tarfn, dldir, date):
                continue

            if date:
                options.append("-D %s" % date)
            if tag:
                options.append("-r %s" % tag)

            olddir = os.path.abspath(os.getcwd())
            os.chdir(data.expand(dldir, localdata))

#           setup cvsroot
            if method == "dir":
                cvsroot = path
            else:
                cvsroot = ":" + method + ":" + user
                if pswd:
                    cvsroot += ":" + pswd
                cvsroot += "@" + host + ":" + path

            data.setVar('CVSROOT', cvsroot, localdata)
            data.setVar('CVSCOOPTS', " ".join(options), localdata)
            data.setVar('CVSMODULE', module, localdata)
            cvscmd = data.getVar('FETCHCOMMAND', localdata, 1)
            cvsupdatecmd = data.getVar('UPDATECOMMAND', localdata, 1)

            if cvs_rsh:
                cvscmd = "CVS_RSH=\"%s\" %s" % (cvs_rsh, cvscmd)
                cvsupdatecmd = "CVS_RSH=\"%s\" %s" % (cvs_rsh, cvsupdatecmd)

#           create module directory
            bb.debug(2, "Fetch: checking for module directory")
            pkg=data.expand('${PN}', d)
            pkgdir=os.path.join(data.expand('${CVSDIR}', localdata), pkg)
            moddir=os.path.join(pkgdir,localdir)
            if os.access(os.path.join(moddir,'CVS'), os.R_OK):
                bb.note("Update " + loc)
#               update sources there
                os.chdir(moddir)
                myret = os.system(cvsupdatecmd)
            else:
                bb.note("Fetch " + loc)
#               check out sources there
                bb.mkdirhier(pkgdir)
                os.chdir(pkgdir)
                bb.debug(1, "Running %s" % cvscmd)
                myret = os.system(cvscmd)

            if myret != 0 or not os.access(moddir, os.R_OK):
                try:
                    os.rmdir(moddir)
                except OSError:
                    pass
                raise FetchError(module)

            os.chdir(moddir)
            os.chdir('..')
#           tar them up to a defined filename
            myret = os.system("tar -czf %s %s" % (os.path.join(dldir,tarfn), os.path.basename(moddir)))
            if myret != 0:
                try:
                    os.unlink(tarfn)
                except OSError:
                    pass
            os.chdir(olddir)
        del localdata
