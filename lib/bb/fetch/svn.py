# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementation for svn.

"""

# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2004        Marcin Juszkiewicz
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
import sys
import logging
import bb
from   bb import data
from   bb.fetch import Fetch
from   bb.fetch import FetchError
from   bb.fetch import MissingParameterError
from   bb.fetch import runfetchcmd
from   bb.fetch import logger

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

        ud.module = ud.parm["module"]

        # Create paths to svn checkouts
        relpath = ud.path
        if relpath.startswith('/'):
            # Remove leading slash as os.path.join can't cope
            relpath = relpath[1:]
        ud.pkgdir = os.path.join(data.expand('${SVNDIR}', d), ud.host, relpath)
        ud.moddir = os.path.join(ud.pkgdir, ud.module)

        if 'rev' in ud.parm:
            ud.date = ""
            ud.revision = ud.parm['rev']
        elif 'date' in ud.date:
            ud.date = ud.parm['date']
            ud.revision = ""
        else:
            #
            # ***Nasty hack***
            # If DATE in unexpanded PV, use ud.date (which is set from SRCDATE)
            # Should warn people to switch to SRCREV here
            #
            pv = data.getVar("PV", d, 0)
            if "DATE" in pv:
                ud.revision = ""
            else:
                rev = Fetch.srcrev_internal_helper(ud, d)
                if rev is True:
                    ud.revision = self.latest_revision(url, ud, d)
                    ud.date = ""
                elif rev:
                    ud.revision = rev
                    ud.date = ""
                else:
                    ud.revision = ""

        ud.localfile = data.expand('%s_%s_%s_%s_%s.tar.gz' % (ud.module.replace('/', '.'), ud.host, ud.path.replace('/', '.'), ud.revision, ud.date), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def _buildsvncommand(self, ud, d, command):
        """
        Build up an svn commandline based on ud
        command is "fetch", "update", "info"
        """

        basecmd = data.expand('${FETCHCMD_svn}', d)

        proto = "svn"
        if "proto" in ud.parm:
            proto = ud.parm["proto"]

        svn_rsh = None
        if proto == "svn+ssh" and "rsh" in ud.parm:
            svn_rsh = ud.parm["rsh"]

        svnroot = ud.host + ud.path

        # either use the revision, or SRCDATE in braces,
        options = []

        if ud.user:
            options.append("--username %s" % ud.user)

        if ud.pswd:
            options.append("--password %s" % ud.pswd)

        if command is "info":
            svncmd = "%s info %s %s://%s/%s/" % (basecmd, " ".join(options), proto, svnroot, ud.module)
        else:
            suffix = ""
            if ud.revision:
                options.append("-r %s" % ud.revision)
                suffix = "@%s" % (ud.revision)
            elif ud.date:
                options.append("-r {%s}" % ud.date)

            if command is "fetch":
                svncmd = "%s co %s %s://%s/%s%s %s" % (basecmd, " ".join(options), proto, svnroot, ud.module, suffix, ud.module)
            elif command is "update":
                svncmd = "%s update %s" % (basecmd, " ".join(options))
            else:
                raise FetchError("Invalid svn command %s" % command)

        if svn_rsh:
            svncmd = "svn_RSH=\"%s\" %s" % (svn_rsh, svncmd)

        return svncmd

    def go(self, loc, ud, d):
        """Fetch url"""

        logger.debug(2, "Fetch: checking for module directory '" + ud.moddir + "'")

        if os.access(os.path.join(ud.moddir, '.svn'), os.R_OK):
            svnupdatecmd = self._buildsvncommand(ud, d, "update")
            logger.info("Update " + loc)
            # update sources there
            os.chdir(ud.moddir)
            logger.debug(1, "Running %s", svnupdatecmd)
            runfetchcmd(svnupdatecmd, d)
        else:
            svnfetchcmd = self._buildsvncommand(ud, d, "fetch")
            logger.info("Fetch " + loc)
            # check out sources there
            bb.mkdirhier(ud.pkgdir)
            os.chdir(ud.pkgdir)
            logger.debug(1, "Running %s", svnfetchcmd)
            runfetchcmd(svnfetchcmd, d)

        os.chdir(ud.pkgdir)
        # tar them up to a defined filename
        try:
            runfetchcmd("tar --exclude '.svn' -czf %s %s" % (ud.localpath, ud.module), d)
        except:
            t, v, tb = sys.exc_info()
            try:
                os.unlink(ud.localpath)
            except OSError:
                pass
            raise t, v, tb

    def supports_srcrev(self):
        return True

    def _revision_key(self, url, ud, d):
        """
        Return a unique key for the url
        """
        return "svn:" + ud.moddir

    def _latest_revision(self, url, ud, d):
        """
        Return the latest upstream revision number
        """
        logger.debug(2, "SVN fetcher hitting network for %s", url)

        output = runfetchcmd("LANG=C LC_ALL=C " + self._buildsvncommand(ud, d, "info"), d, True)

        revision = None
        for line in output.splitlines():
            if "Last Changed Rev" in line:
                revision = line.split(":")[1].strip()

        return revision

    def _sortable_revision(self, url, ud, d):
        """
        Return a sortable revision number which in our case is the revision number
        """

        return self._build_revision(url, ud, d)

    def _build_revision(self, url, ud, d):
        return ud.revision
