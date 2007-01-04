# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

This implementation is for svk. It is based on the svn implementation

"""

# Copyright (C) 2006 Holger Hans Peter Freyther
# Copyright (C) 2003, 2004  Chris Larson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Based on functions from the base bb module, Copyright 2003 Holger Schurig

import os, re
import bb
from   bb import data
from   bb.fetch import Fetch
from   bb.fetch import FetchError
from   bb.fetch import MissingParameterError

class Svk(Fetch):
    """Class to fetch a module or modules from svk repositories"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with cvs.
        """
        return ud.type in ['svk']

    def localpath(self, url, ud, d):
        if not "module" in ud.parm:
            raise MissingParameterError("svk method needs a 'module' parameter")
        else:
            ud.module = ud.parm["module"]

        ud.revision = ""
        if 'rev' in ud.parm:
            ud.revision = ud.parm['rev']

        ud.localfile = data.expand('%s_%s_%s_%s_%s.tar.gz' % (ud.module.replace('/', '.'), ud.host, ud.path.replace('/', '.'), ud.revision, ud.date), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def forcefetch(self, url, ud, d):
        if (ud.date == "now"):
            return True
        return False

    def go(self, loc, ud, d):
        """Fetch urls"""

        if not self.forcefetch(loc, ud, d) and Fetch.try_mirror(d, ud.localfile):
            return

        svkroot = ud.host + ud.path

        svkcmd = "svk co -r {%s} %s/%s" % (date, svkroot, ud.module)

        if ud.revision:
            svkcmd = "svk co -r %s/%s" % (ud.revision, svkroot, ud.module)

        # create temp directory
        localdata = data.createCopy(d)
        data.update_data(localdata)
        bb.msg.debug(2, bb.msg.domain.Fetcher, "Fetch: creating temporary directory")
        bb.mkdirhier(data.expand('${WORKDIR}', localdata))
        data.setVar('TMPBASE', data.expand('${WORKDIR}/oesvk.XXXXXX', localdata), localdata)
        tmppipe = os.popen(data.getVar('MKTEMPDIRCMD', localdata, 1) or "false")
        tmpfile = tmppipe.readline().strip()
        if not tmpfile:
            bb.msg.error(bb.msg.domain.Fetcher, "Fetch: unable to create temporary directory.. make sure 'mktemp' is in the PATH.")
            raise FetchError(ud.module)

        # check out sources there
        os.chdir(tmpfile)
        bb.msg.note(1, bb.msg.domain.Fetcher, "Fetch " + loc)
        bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % svkcmd)
        myret = os.system(svkcmd)
        if myret != 0:
            try:
                os.rmdir(tmpfile)
            except OSError:
                pass
            raise FetchError(ud.module)

        os.chdir(os.path.join(tmpfile, os.path.dirname(ud.module)))
        # tar them up to a defined filename
        myret = os.system("tar -czf %s %s" % (ud.localpath, os.path.basename(ud.module)))
        if myret != 0:
            try:
                os.unlink(ud.localpath)
            except OSError:
                pass
            raise FetchError(ud.module)
        # cleanup
        os.system('rm -rf %s' % tmpfile)
