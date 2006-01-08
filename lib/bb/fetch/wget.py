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
from   bb.fetch import MD5SumError
from   bb.fetch import uri_replace

class Wget(Fetch):
    """Class to fetch urls via 'wget'"""
    def supports(url, d):
        """Check to see if a given url can be fetched using wget.
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))
        return type in ['http','https','ftp']
    supports = staticmethod(supports)

    def localpath(url, d):
#       strip off parameters
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]
        url = bb.encodeurl([type, host, path, user, pswd, {}])

        return os.path.join(data.getVar("DL_DIR", d), os.path.basename(url))
    localpath = staticmethod(localpath)

    def go(self, d, urls = []):
        """Fetch urls"""

        def md5_sum(parm, d):
            """
            Return the MD5SUM associated with the to be downloaded
            file.
            It can return None if no md5sum is associated
            """
            try:
                return parm['md5sum']
            except:
                return None

        def verify_md5sum(wanted_sum, got_sum):
            """
            Verify the md5sum we wanted with the one we got
            """
            if not wanted_sum:
                return True

            return wanted_sum == got_sum

        def fetch_uri(uri, basename, dl, md5, parm, d):
            # the MD5 sum we want to verify
            wanted_md5sum = md5_sum(parm, d)
            if os.path.exists(dl):
#               file exists, but we didnt complete it.. trying again..
                fetchcmd = data.getVar("RESUMECOMMAND", d, 1)
            else:
                fetchcmd = data.getVar("FETCHCOMMAND", d, 1)

            bb.note("fetch " + uri)
            fetchcmd = fetchcmd.replace("${URI}", uri)
            fetchcmd = fetchcmd.replace("${FILE}", basename)
            bb.debug(2, "executing " + fetchcmd)
            ret = os.system(fetchcmd)
            if ret != 0:
                return False

            # check if sourceforge did send us to the mirror page
            dl_dir = data.getVar("DL_DIR", d, True)
            if not os.path.exists(dl):
                os.system("rm %s*" % dl) # FIXME shell quote it
                bb.debug(2,"sourceforge.net send us to the mirror on %s" % basename)
                return False

#           supposedly complete.. write out md5sum
            if bb.which(data.getVar('PATH', d), 'md5sum'):
                try:
                    md5pipe = os.popen('md5sum ' + dl)
                    md5data = (md5pipe.readline().split() or [ "" ])[0]
                    md5pipe.close()
                except OSError:
                    md5data = ""

            # verify the md5sum
            if not verify_md5sum(wanted_md5sum, md5data):
                raise MD5SumError(uri)

            md5out = file(md5, 'w')
            md5out.write(md5data)
            md5out.close()
            return True

        if not urls:
            urls = self.urls

        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', "wget:" + data.getVar('OVERRIDES', localdata), localdata)
        data.update_data(localdata)

        for uri in urls:
            completed = 0
            (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(uri, localdata))
            basename = os.path.basename(path)
            dl = self.localpath(uri, d)
            dl = data.expand(dl, localdata)
            md5 = dl + '.md5'

            if os.path.exists(md5):
#               complete, nothing to see here..
                continue

            premirrors = [ i.split() for i in (data.getVar('PREMIRRORS', localdata, 1) or "").split('\n') if i ]
            for (find, replace) in premirrors:
                newuri = uri_replace(uri, find, replace, d)
                if newuri != uri:
                    if fetch_uri(newuri, basename, dl, md5, parm, localdata):
                        completed = 1
                        break

            if completed:
                continue

            if fetch_uri(uri, basename, dl, md5, parm, localdata):
                continue

#           try mirrors
            mirrors = [ i.split() for i in (data.getVar('MIRRORS', localdata, 1) or "").split('\n') if i ]
            for (find, replace) in mirrors:
                newuri = uri_replace(uri, find, replace, d)
                if newuri != uri:
                    if fetch_uri(newuri, basename, dl, md5, parm, localdata):
                        completed = 1
                        break

            if not completed:
                raise FetchError(uri)

        del localdata
