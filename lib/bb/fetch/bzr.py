"""
BitBake 'Fetch' implementation for bzr.

"""

# Copyright (C) 2007 Ross Burton
# Copyright (C) 2007 Richard Purdie
#
#   Classes for obtaining upstream sources for the
#   BitBake build tools.
#   Copyright (C) 2003, 2004  Chris Larson
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

import os
import sys
import bb
from bb import data
from bb.fetch import Fetch
from bb.fetch import FetchError
from bb.fetch import MissingParameterError
from bb.fetch import runfetchcmd

class Bzr(Fetch):
    def supports(self, url, ud, d):
        return ud.type in ['bzr']

    def localpath (self, url, ud, d):

        # Create paths to bzr checkouts
        relpath = ud.path
        if relpath.startswith('/'):
            # Remove leading slash as os.path.join can't cope
            relpath = relpath[1:]
        ud.pkgdir = os.path.join(data.expand('${BZRDIR}', d), ud.host, relpath)

        if 'rev' in ud.parm:
            ud.revision = ud.parm['rev']
        else:
            # ***Nasty hack***
            rev = data.getVar("SRCREV", d, 0)
            if rev and "get_srcrev" in rev:
                ud.revision = self.latest_revision(url, ud, d)
            elif rev:
                ud.revision = rev
            else:
                ud.revision = ""

        
        ud.localfile = data.expand('bzr_%s_%s_%s.tar.gz' % (ud.host, ud.path.replace('/', '.'), ud.revision), d)
        
        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def _buildbzrcommand(self, ud, d, command):
        """
        Build up an bzr commandline based on ud
        command is "fetch", "update", "revno"
        """

        basecmd = data.expand('${FETCHCMD_bzr}', d)

        proto = "http"
        if "proto" in ud.parm:
            proto = ud.parm["proto"]

        bzrroot = ud.host + ud.path

        options = []

        if command is "revno":
            bzrcmd = "%s revno %s %s://%s" % (basecmd, " ".join(options), proto, bzrroot)
        else:
            if ud.revision:
                options.append("-r %s" % ud.revision)

            if command is "fetch":
                bzrcmd = "%s co %s %s://%s" % (basecmd, " ".join(options), proto, bzrroot)
            elif command is "update":
                bzrcmd = "%s update %s" % (basecmd, " ".join(options))
            else:
                raise FetchError("Invalid bzr command %s" % command)

        return bzrcmd

    def go(self, loc, ud, d):
        """Fetch url"""

        # try to use the tarball stash
        if Fetch.try_mirror(d, ud.localfile):
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists or was mirrored, skipping bzr checkout." % ud.localpath)
            return

        # Updating is disabled until bzr supports the syntax "bzr update -r X" to specify a revision
        if 0 and os.access(os.path.join(ud.pkgdir, os.path.basename(ud.pkgdir), '.bzr'), os.R_OK):
            bzrcmd = self._buildbzrcommand(ud, d, "update")
            bb.msg.debug(1, bb.msg.domain.Fetcher, "BZR Update %s" % loc)
            os.chdir(os.path.join (ud.pkgdir, os.path.basename(ud.path)))
            runfetchcmd(bzrcmd, d)
        else:
            os.system("rm -rf %s" % os.path.join(ud.pkgdir, os.path.basename(ud.pkgdir)))
            bzrcmd = self._buildbzrcommand(ud, d, "fetch")
            bb.msg.debug(1, bb.msg.domain.Fetcher, "BZR Checkout %s" % loc)
            bb.mkdirhier(ud.pkgdir)
            os.chdir(ud.pkgdir)
            bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % bzrcmd)
            runfetchcmd(bzrcmd, d)

        os.chdir(ud.pkgdir)
        # tar them up to a defined filename
        try:
            runfetchcmd("tar -czf %s %s" % (ud.localpath, os.path.basename(ud.pkgdir)), d)
        except:
            t, v, tb = sys.exc_info()
            try:
                os.unlink(ud.localpath)
            except OSError:
                pass
            raise t, v, tb

    def suppports_srcrev(self):
        return True

    def _revision_key(self, url, ud, d):
        """
        Return a unique key for the url
        """
        return "bzr:" + ud.pkgdir

    def _latest_revision(self, url, ud, d):
        """
        Return the latest upstream revision number
        """
        bb.msg.debug(2, bb.msg.domain.Fetcher, "BZR fetcher hitting network for %s" % url)

        output = runfetchcmd(self._buildbzrcommand(ud, d, "revno"), d, True)

        for line in output.splitlines():
            revision = line

        return revision

    def _sortable_revision(self, url, ud, d):
        """
        Return a sortable revision number which in our case is the revision number
        (use the cached version to avoid network access)
        """

        return self.latest_revision(url, ud, d)
