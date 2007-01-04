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

import os, re
import bb
from   bb import data
from   bb.fetch import Fetch
from   bb.fetch import FetchError
from   bb.fetch import uri_replace

class Wget(Fetch):
    """Class to fetch urls via 'wget'"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with cvs.
        """
        return ud.type in ['http','https','ftp']

    def localpath(self, url, ud, d):

        url = bb.encodeurl([ud.type, ud.host, ud.path, ud.user, ud.pswd, {}])
        ud.basename = os.path.basename(ud.path)
        ud.localfile = data.expand(os.path.basename(url), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def go(self, uri, ud, d):
        """Fetch urls"""

        def fetch_uri(uri, ud, d):
            if os.path.exists(ud.localpath):
                # file exists, but we didnt complete it.. trying again..
                fetchcmd = data.getVar("RESUMECOMMAND", d, 1)
            else:
                fetchcmd = data.getVar("FETCHCOMMAND", d, 1)

            bb.msg.note(1, bb.msg.domain.Fetcher, "fetch " + uri)
            fetchcmd = fetchcmd.replace("${URI}", uri)
            fetchcmd = fetchcmd.replace("${FILE}", ud.basename)
            bb.msg.debug(2, bb.msg.domain.Fetcher, "executing " + fetchcmd)
            ret = os.system(fetchcmd)
            if ret != 0:
                return False

            # check if sourceforge did send us to the mirror page
            if not os.path.exists(ud.localpath):
                os.system("rm %s*" % ud.localpath) # FIXME shell quote it
                bb.msg.debug(2, bb.msg.domain.Fetcher, "sourceforge.net send us to the mirror on %s" % ud.basename)
                return False

            return True

        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', "wget:" + data.getVar('OVERRIDES', localdata), localdata)
        data.update_data(localdata)

        premirrors = [ i.split() for i in (data.getVar('PREMIRRORS', localdata, 1) or "").split('\n') if i ]
        for (find, replace) in premirrors:
            newuri = uri_replace(uri, find, replace, d)
            if newuri != uri:
                if fetch_uri(newuri, ud, localdata):
                    return

        if fetch_uri(uri, ud, localdata):
            return

        # try mirrors
        mirrors = [ i.split() for i in (data.getVar('MIRRORS', localdata, 1) or "").split('\n') if i ]
        for (find, replace) in mirrors:
            newuri = uri_replace(uri, find, replace, d)
            if newuri != uri:
                if fetch_uri(newuri, ud, localdata):
                    return

        raise FetchError(uri)
