#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

This implementation is for svk. It is based on the svn implementation

Copyright (C) 2006 Holger Hans Peter Freyther

GPL and MIT licensed



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

class Svk(Fetch):
    """Class to fetch a module or modules from svk repositories"""
    def supports(url, d):
        """Check to see if a given url can be fetched with svk.
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))
        return type in ['svk']
    supports = staticmethod(supports)

    def localpath(url, d):
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]

        if not "module" in parm:
            raise MissingParameterError("svk method needs a 'module' parameter")
        else:
            module = parm["module"]
        if 'rev' in parm:
            revision = parm['rev']
        else:
            revision = ""

        date = Fetch.getSRCDate(d)

        return os.path.join(data.getVar("DL_DIR", d, 1),data.expand('%s_%s_%s_%s_%s.tar.gz' % ( module.replace('/', '.'), host, path.replace('/', '.'), revision, date), d))
    localpath = staticmethod(localpath)

    def go(self, d, urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', "svk:%s" % data.getVar('OVERRIDES', localdata), localdata)
        data.update_data(localdata)

        for loc in urls:
            (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(loc, localdata))
            if not "module" in parm:
                raise MissingParameterError("svk method needs a 'module' parameter")
            else:
                module = parm["module"]

            dlfile = self.localpath(loc, localdata)
            dldir = data.getVar('DL_DIR', localdata, 1)

#           setup svk options
            options = []
            if 'rev' in parm:
                revision = parm['rev']
            else:
                revision = ""

            date = Fetch.getSRCDate(d)
            tarfn = data.expand('%s_%s_%s_%s_%s.tar.gz' % (module.replace('/', '.'), host, path.replace('/', '.'), revision, date), localdata)
            data.setVar('TARFILES', dlfile, localdata)
            data.setVar('TARFN', tarfn, localdata)

            if Fetch.check_for_tarball(d, tarfn, dldir, date):
                continue

            olddir = os.path.abspath(os.getcwd())
            os.chdir(data.expand(dldir, localdata))

            svkroot = host + path

            data.setVar('SVKROOT', svkroot, localdata)
            data.setVar('SVKCOOPTS', " ".join(options), localdata)
            data.setVar('SVKMODULE', module, localdata)
            svkcmd = "svk co -r {%s} %s/%s" % (date, svkroot, module)

            if revision:
                svkcmd = "svk co -r %s/%s" % (revision, svkroot, module)

#           create temp directory
            bb.debug(2, "Fetch: creating temporary directory")
            bb.mkdirhier(data.expand('${WORKDIR}', localdata))
            data.setVar('TMPBASE', data.expand('${WORKDIR}/oesvk.XXXXXX', localdata), localdata)
            tmppipe = os.popen(data.getVar('MKTEMPDIRCMD', localdata, 1) or "false")
            tmpfile = tmppipe.readline().strip()
            if not tmpfile:
                bb.error("Fetch: unable to create temporary directory.. make sure 'mktemp' is in the PATH.")
                raise FetchError(module)

#           check out sources there
            os.chdir(tmpfile)
            bb.note("Fetch " + loc)
            bb.debug(1, "Running %s" % svkcmd)
            myret = os.system(svkcmd)
            if myret != 0:
                try:
                    os.rmdir(tmpfile)
                except OSError:
                    pass
                raise FetchError(module)

            os.chdir(os.path.join(tmpfile, os.path.dirname(module)))
#           tar them up to a defined filename
            myret = os.system("tar -czf %s %s" % (os.path.join(dldir,tarfn), os.path.basename(module)))
            if myret != 0:
                try:
                    os.unlink(tarfn)
                except OSError:
                    pass
#           cleanup
            os.system('rm -rf %s' % tmpfile)
            os.chdir(olddir)
        del localdata
