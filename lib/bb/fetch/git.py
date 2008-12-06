# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' git implementation

"""

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

import os, re
import bb
from   bb    import data
from   bb.fetch import Fetch
from   bb.fetch import FetchError
from   bb.fetch import runfetchcmd

class Git(Fetch):
    """Class to fetch a module or modules from git repositories"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with git.
        """
        return ud.type in ['git']

    def localpath(self, url, ud, d):

        ud.proto = "rsync"
        if 'protocol' in ud.parm:
            ud.proto = ud.parm['protocol']

        ud.branch = ud.parm.get("branch", "master")

        tag = Fetch.srcrev_internal_helper(ud, d)
        if tag is True:
            ud.tag = self.latest_revision(url, ud, d)	
        elif tag:
            ud.tag = tag

        if not ud.tag:
            ud.tag = self.latest_revision(url, ud, d)	

        if ud.tag == "master":
            ud.tag = self.latest_revision(url, ud, d)

        ud.localfile = data.expand('git_%s%s_%s.tar.gz' % (ud.host, ud.path.replace('/', '.'), ud.tag), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def go(self, loc, ud, d):
        """Fetch url"""

        if os.access(os.path.join(data.getVar("DL_DIR", d, True), ud.localfile), os.R_OK):
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists (or was stashed). Skipping git checkout." % ud.localpath)
            return

        if ud.user:
            username = ud.user + '@'
        else:
            username = ""

        gitsrcname = '%s%s' % (ud.host, ud.path.replace('/', '.'))

        repofilename = 'git_%s.tar.gz' % (gitsrcname)
        repofile = os.path.join(data.getVar("DL_DIR", d, 1), repofilename)
        repodir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

        coname = '%s' % (ud.tag)
        codir = os.path.join(repodir, coname)

        if not os.path.exists(repodir):
            if Fetch.try_mirror(d, repofilename):    
                bb.mkdirhier(repodir)
                os.chdir(repodir)
                runfetchcmd("tar -xzf %s" % (repofile), d)
            else:
                runfetchcmd("git clone -n %s://%s%s%s %s" % (ud.proto, username, ud.host, ud.path, repodir), d)

        os.chdir(repodir)
        # Remove all but the .git directory
        if not self._contains_ref(ud.tag, d):
            runfetchcmd("rm * -Rf", d)
            runfetchcmd("git fetch %s://%s%s%s %s" % (ud.proto, username, ud.host, ud.path, ud.branch), d)
            runfetchcmd("git fetch --tags %s://%s%s%s" % (ud.proto, username, ud.host, ud.path), d)
            runfetchcmd("git prune-packed", d)
            runfetchcmd("git pack-redundant --all | xargs -r rm", d)

        os.chdir(repodir)
        mirror_tarballs = data.getVar("BB_GENERATE_MIRROR_TARBALLS", d, True)
        if mirror_tarballs != "0": 
            bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git repository")
            runfetchcmd("tar -czf %s %s" % (repofile, os.path.join(".", ".git", "*") ), d)

        if os.path.exists(codir):
            bb.utils.prunedir(codir)

        bb.mkdirhier(codir)
        os.chdir(repodir)
        runfetchcmd("git read-tree %s" % (ud.tag), d)
        runfetchcmd("git checkout-index -q -f --prefix=%s -a" % (os.path.join(codir, "git", "")), d)

        os.chdir(codir)
        bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git checkout")
        runfetchcmd("tar -czf %s %s" % (ud.localpath, os.path.join(".", "*") ), d)

        os.chdir(repodir)
        bb.utils.prunedir(codir)

    def suppports_srcrev(self):
        return True

    def _contains_ref(self, tag, d):
        output = runfetchcmd("git log --pretty=oneline -n 1 %s -- 2> /dev/null | wc -l" % tag, d, quiet=True)
        return output.split()[0] != "0"

    def _revision_key(self, url, ud, d):
        """
        Return a unique key for the url
        """
        return "git:" + ud.host + ud.path.replace('/', '.')

    def _latest_revision(self, url, ud, d):
        """
        Compute the HEAD revision for the url
        """
        output = runfetchcmd("git ls-remote %s://%s%s %s" % (ud.proto, ud.host, ud.path, ud.branch), d, True)
        return output.split()[0]

    def _build_revision(self, url, ud, d):
        return ud.tag

    def _want_sortable_revision(self, url, ud, d):
        return bb.data.getVar("BB_GIT_CLONE_FOR_SRCREV", d, True) or False

    def _sortable_revision(self, url, ud, d):
        """
        This is only called when _want_sortable_revision called true

        We will have to get the updated revision.
        """
        gitsrcname = '%s%s' % (ud.host, ud.path.replace('/', '.'))
        repodir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

        key = "GIT_CACHED_REVISION-%s-%s"  % (gitsrcname, ud.tag)
        if bb.data.getVar(key, d):
            return bb.data.getVar(key, d)


        # Runtime warning on wrongly configured sources
        if ud.tag == "1":
            bb.msg.error(1, bb.msg.domain.Fetcher, "SRCREV is '1'. This indicates a configuration error of %s" % url)
            return "0+1"

        cwd = os.getcwd()

        # Check if we have the rev already
        if not os.path.exists(repodir):
            print "no repo"
            self.go(None, ud, d)

        os.chdir(repodir)
        if not self._contains_ref(ud.tag, d):
            self.go(None, ud, d)

        output = runfetchcmd("git rev-list %s -- 2> /dev/null | wc -l" % ud.tag, d, quiet=True)
        os.chdir(cwd)

        sortable_revision = "%s+%s" % (output.split()[0], ud.tag)
        bb.data.setVar(key, sortable_revision, d)
        return sortable_revision
        

