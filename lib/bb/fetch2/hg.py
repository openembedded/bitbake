# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementation for mercurial DRCS (hg).

"""

# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2004        Marcin Juszkiewicz
# Copyright (C) 2007        Robert Schuster
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
from bb import data
from bb.fetch2 import FetchMethod
from bb.fetch2 import FetchError
from bb.fetch2 import MissingParameterError
from bb.fetch2 import runfetchcmd
from bb.fetch2 import logger

class Hg(FetchMethod):
    """Class to fetch from mercurial repositories"""
    def supports(self, ud, d):
        """
        Check to see if a given url can be fetched with mercurial.
        """
        return ud.type in ['hg']

    def urldata_init(self, ud, d):
        """
        init hg specific variable within url data
        """
        if not "module" in ud.parm:
            raise MissingParameterError('module', ud.url)

        ud.module = ud.parm["module"]

        # Create paths to mercurial checkouts
        relpath = self._strip_leading_slashes(ud.path)
        ud.pkgdir = os.path.join(data.expand('${HGDIR}', d), ud.host, relpath)
        ud.moddir = os.path.join(ud.pkgdir, ud.module)

        ud.setup_revisons(d)

        if 'rev' in ud.parm:
            ud.revision = ud.parm['rev']
        elif not ud.revision:
            ud.revision = self.latest_revision(ud, d)

        ud.localfile = data.expand('%s_%s_%s_%s.tar.gz' % (ud.module.replace('/', '.'), ud.host, ud.path.replace('/', '.'), ud.revision), d)

    def need_update(self, ud, d):
        revTag = ud.parm.get('rev', 'tip')
        if revTag == "tip":
            return True
        if not os.path.exists(ud.localpath):
            return True
        return False

    def _buildhgcommand(self, ud, d, command):
        """
        Build up an hg commandline based on ud
        command is "fetch", "update", "info"
        """

        basecmd = data.expand('${FETCHCMD_hg}', d)

        proto = ud.parm.get('protocol', 'http')

        host = ud.host
        if proto == "file":
            host = "/"
            ud.host = "localhost"

        if not ud.user:
            hgroot = host + ud.path
        else:
            if ud.pswd:
                hgroot = ud.user + ":" + ud.pswd + "@" + host + ud.path
            else:
                hgroot = ud.user + "@" + host + ud.path

        if command == "info":
            return "%s identify -i %s://%s/%s" % (basecmd, proto, hgroot, ud.module)

        options = [];

        # Don't specify revision for the fetch; clone the entire repo.
        # This avoids an issue if the specified revision is a tag, because
        # the tag actually exists in the specified revision + 1, so it won't
        # be available when used in any successive commands.
        if ud.revision and command != "fetch":
            options.append("-r %s" % ud.revision)

        if command == "fetch":
            if ud.user and ud.pswd:
                cmd = "%s --config auth.default.prefix=* --config auth.default.username=%s --config auth.default.password=%s --config \"auth.default.schemes=%s\" clone %s %s://%s/%s %s" % (basecmd, ud.user, ud.pswd, proto, " ".join(options), proto, hgroot, ud.module, ud.module)
            else:
                cmd = "%s clone %s %s://%s/%s %s" % (basecmd, " ".join(options), proto, hgroot, ud.module, ud.module)	      
        elif command == "pull":
            # do not pass options list; limiting pull to rev causes the local
            # repo not to contain it and immediately following "update" command
            # will crash
            if ud.user and ud.pswd:
                cmd = "%s --config auth.default.prefix=* --config auth.default.username=%s --config auth.default.password=%s --config \"auth.default.schemes=%s\" pull" % (basecmd, ud.user, ud.pswd, proto)
            else:
                cmd = "%s pull" % (basecmd)
        elif command == "update":
            if ud.user and ud.pswd:
                cmd = "%s --config auth.default.prefix=* --config auth.default.username=%s --config auth.default.password=%s --config \"auth.default.schemes=%s\" update -C %s" % (basecmd, ud.user, ud.pswd, proto, " ".join(options))
            else:
                cmd = "%s update -C %s" % (basecmd, " ".join(options))
        else:
            raise FetchError("Invalid hg command %s" % command, ud.url)

        return cmd

    def download(self, ud, d):
        """Fetch url"""

        logger.debug(2, "Fetch: checking for module directory '" + ud.moddir + "'")

        if os.access(os.path.join(ud.moddir, '.hg'), os.R_OK):
            updatecmd = self._buildhgcommand(ud, d, "pull")
            logger.info("Update " + ud.url)
            # update sources there
            os.chdir(ud.moddir)
            logger.debug(1, "Running %s", updatecmd)
            bb.fetch2.check_network_access(d, updatecmd, ud.url)
            runfetchcmd(updatecmd, d)

        else:
            fetchcmd = self._buildhgcommand(ud, d, "fetch")
            logger.info("Fetch " + ud.url)
            # check out sources there
            bb.utils.mkdirhier(ud.pkgdir)
            os.chdir(ud.pkgdir)
            logger.debug(1, "Running %s", fetchcmd)
            bb.fetch2.check_network_access(d, fetchcmd, ud.url)
            runfetchcmd(fetchcmd, d)

        # Even when we clone (fetch), we still need to update as hg's clone
        # won't checkout the specified revision if its on a branch
        updatecmd = self._buildhgcommand(ud, d, "update")
        os.chdir(ud.moddir)
        logger.debug(1, "Running %s", updatecmd)
        runfetchcmd(updatecmd, d)

        scmdata = ud.parm.get("scmdata", "")
        if scmdata == "keep":
            tar_flags = ""
        else:
            tar_flags = "--exclude '.hg' --exclude '.hgrags'"

        os.chdir(ud.pkgdir)
        runfetchcmd("tar %s -czf %s %s" % (tar_flags, ud.localpath, ud.module), d, cleanup = [ud.localpath])

    def supports_srcrev(self):
        return True

    def _latest_revision(self, ud, d, name):
        """
        Compute tip revision for the url
        """
        bb.fetch2.check_network_access(d, self._buildhgcommand(ud, d, "info"))
        output = runfetchcmd(self._buildhgcommand(ud, d, "info"), d)
        return output.strip()

    def _build_revision(self, ud, d, name):
        return ud.revision

    def _revision_key(self, ud, d, name):
        """
        Return a unique key for the url
        """
        return "hg:" + ud.moddir
