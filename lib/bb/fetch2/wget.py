# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

Classes for obtaining upstream sources for the
BitBake build tools.

"""

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
import urllib
from   bb import data
from   bb.fetch2 import FetchMethod
from   bb.fetch2 import FetchError
from   bb.fetch2 import logger
from   bb.fetch2 import runfetchcmd

class Wget(FetchMethod):
    """Class to fetch urls via 'wget'"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with wget.
        """
        return ud.type in ['http', 'https', 'ftp']

    def recommends_checksum(self, urldata):
        return True

    def urldata_init(self, ud, d):
        if 'protocol' in ud.parm:
            if ud.parm['protocol'] == 'git':
                raise bb.fetch2.ParameterError("Invalid protocol - if you wish to fetch from a git repository using http, you need to instead use the git:// prefix with protocol=http", ud.url)

        if 'downloadfilename' in ud.parm:
            ud.basename = ud.parm['downloadfilename']
        else:
            ud.basename = os.path.basename(ud.path)

        ud.localfile = data.expand(urllib.unquote(ud.basename), d)

    def download(self, uri, ud, d, checkonly = False):
        """Fetch urls"""

        basecmd = d.getVar("FETCHCMD_wget", True) or "/usr/bin/env wget -t 2 -T 30 -nv --passive-ftp --no-check-certificate"

        if not checkonly and 'downloadfilename' in ud.parm:
            dldir = d.getVar("DL_DIR", True)
            bb.utils.mkdirhier(os.path.dirname(dldir + os.sep + ud.localfile))
            basecmd += " -O " + dldir + os.sep + ud.localfile

        if checkonly:
            fetchcmd = d.getVar("CHECKCOMMAND_wget", True) or d.expand(basecmd + " --spider '${URI}'")
        elif os.path.exists(ud.localpath):
            # file exists, but we didnt complete it.. trying again..
            fetchcmd = d.getVar("RESUMECOMMAND_wget", True) or d.expand(basecmd + " -c -P ${DL_DIR} '${URI}'")
        else:
            fetchcmd = d.getVar("FETCHCOMMAND_wget", True) or d.expand(basecmd + " -P ${DL_DIR} '${URI}'")

        uri = uri.split(";")[0]

        fetchcmd = fetchcmd.replace("${URI}", uri.split(";")[0])
        fetchcmd = fetchcmd.replace("${FILE}", ud.basename)
        if not checkonly:
            logger.info("fetch " + uri)
            logger.debug(2, "executing " + fetchcmd)
        bb.fetch2.check_network_access(d, fetchcmd)
        runfetchcmd(fetchcmd, d, quiet=checkonly)

        # Sanity check since wget can pretend it succeed when it didn't
        # Also, this used to happen if sourceforge sent us to the mirror page
        if not os.path.exists(ud.localpath) and not checkonly:
            raise FetchError("The fetch command returned success for url %s but %s doesn't exist?!" % (uri, ud.localpath), uri)

        return True

    def checkstatus(self, uri, ud, d):
        return self.download(uri, ud, d, True)
