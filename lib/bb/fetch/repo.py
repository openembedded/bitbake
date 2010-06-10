# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake "Fetch" repo (git) implementation

"""

# Copyright (C) 2009 Tom Rini <trini@embeddedalley.com>
#
# Based on git.py which is:
#Copyright (C) 2005 Richard Purdie
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
import bb
from   bb    import data
from   bb.fetch import Fetch
from   bb.fetch import runfetchcmd

class Repo(Fetch):
    """Class to fetch a module or modules from repo (git) repositories"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with repo.
        """
        return ud.type in ["repo"]

    def localpath(self, url, ud, d):
        """
        We don"t care about the git rev of the manifests repository, but
        we do care about the manifest to use.  The default is "default".
        We also care about the branch or tag to be used.  The default is
        "master".
        """

        if "protocol" in ud.parm:
            ud.proto = ud.parm["protocol"]
        else:
            ud.proto = "git"

        if "branch" in ud.parm:
            ud.branch = ud.parm["branch"]
        else:
            ud.branch = "master"

        if "manifest" in ud.parm:
            manifest = ud.parm["manifest"]
            if manifest.endswith(".xml"):
                ud.manifest = manifest
            else:
                ud.manifest = manifest + ".xml"
        else:
            ud.manifest = "default.xml"

        ud.localfile = data.expand("repo_%s%s_%s_%s.tar.gz" % (ud.host, ud.path.replace("/", "."), ud.manifest, ud.branch), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def go(self, loc, ud, d):
        """Fetch url"""

        if os.access(os.path.join(data.getVar("DL_DIR", d, True), ud.localfile), os.R_OK):
            logger.debug(1, "%s already exists (or was stashed). Skipping repo init / sync.", ud.localpath)
            return

        gitsrcname = "%s%s" % (ud.host, ud.path.replace("/", "."))
        repodir = data.getVar("REPODIR", d, True) or os.path.join(data.getVar("DL_DIR", d, True), "repo")
        codir = os.path.join(repodir, gitsrcname, ud.manifest)

        if ud.user:
            username = ud.user + "@"
        else:
            username = ""

        bb.mkdirhier(os.path.join(codir, "repo"))
        os.chdir(os.path.join(codir, "repo"))
        if not os.path.exists(os.path.join(codir, "repo", ".repo")):
            runfetchcmd("repo init -m %s -b %s -u %s://%s%s%s" % (ud.manifest, ud.branch, ud.proto, username, ud.host, ud.path), d)

        runfetchcmd("repo sync", d)
        os.chdir(codir)

        # Create a cache
        runfetchcmd("tar --exclude=.repo --exclude=.git -czf %s %s" % (ud.localpath, os.path.join(".", "*") ), d)

    def suppports_srcrev(self):
        return False

    def _build_revision(self, url, ud, d):
        return ud.manifest

    def _want_sortable_revision(self, url, ud, d):
        return False
