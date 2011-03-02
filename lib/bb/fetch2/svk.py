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

import os
import logging
import bb
from   bb import data
from   bb.fetch2 import FetchMethod
from   bb.fetch2 import FetchError
from   bb.fetch2 import MissingParameterError
from   bb.fetch2 import logger
from   bb.fetch2 import runfetchcmd

class Svk(FetchMethod):
    """Class to fetch a module or modules from svk repositories"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with svk.
        """
        return ud.type in ['svk']

    def urldata_init(self, ud, d):

        if not "module" in ud.parm:
            raise MissingParameterError('module', ud.url)
        else:
            ud.module = ud.parm["module"]

        ud.revision = ud.parm.get('rev', "")

        ud.localfile = data.expand('%s_%s_%s_%s_%s.tar.gz' % (ud.module.replace('/', '.'), ud.host, ud.path.replace('/', '.'), ud.revision, ud.date), d)

    def need_update(self, url, ud, d):
        if ud.date == "now":
            return True
        if not os.path.exists(ud.localpath):
            return True
        return False

    def download(self, loc, ud, d):
        """Fetch urls"""

        svkroot = ud.host + ud.path

        svkcmd = "svk co -r {%s} %s/%s" % (ud.date, svkroot, ud.module)

        if ud.revision:
            svkcmd = "svk co -r %s %s/%s" % (ud.revision, svkroot, ud.module)

        # create temp directory
        localdata = data.createCopy(d)
        data.update_data(localdata)
        logger.debug(2, "Fetch: creating temporary directory")
        bb.utils.mkdirhier(data.expand('${WORKDIR}', localdata))
        data.setVar('TMPBASE', data.expand('${WORKDIR}/oesvk.XXXXXX', localdata), localdata)
        tmppipe = os.popen(data.getVar('MKTEMPDIRCMD', localdata, True) or "false")
        tmpfile = tmppipe.readline().strip()
        if not tmpfile:
            logger.error()
            raise FetchError("Fetch: unable to create temporary directory.. make sure 'mktemp' is in the PATH.", loc)

        # check out sources there
        os.chdir(tmpfile)
        logger.info("Fetch " + loc)
        logger.debug(1, "Running %s", svkcmd)
        runfetchcmd(svkcmd, d, cleanup = [tmpfile])

        os.chdir(os.path.join(tmpfile, os.path.dirname(ud.module)))
        # tar them up to a defined filename
        runfetchcmd("tar -czf %s %s" % (ud.localpath, os.path.basename(ud.module)), d, cleanup = [ud.localpath])

        # cleanup
        bb.utils.prunedir(tmpfile)
