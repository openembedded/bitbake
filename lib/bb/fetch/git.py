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

import os
import bb
from   bb    import data
from   bb.fetch import Fetch
from   bb.fetch import runfetchcmd

class Git(Fetch):
    """Class to fetch a module or modules from git repositories"""
    def init(self, d):
        #
        # Only enable _sortable revision if the key is set
        #
        if bb.data.getVar("BB_GIT_CLONE_FOR_SRCREV", d, True):
            self._sortable_buildindex = self._sortable_buildindex_disabled
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with git.
        """
        return ud.type in ['git']

    def localpath(self, url, ud, d):

        if 'protocol' in ud.parm:
            ud.proto = ud.parm['protocol']
        elif not ud.host:
            ud.proto = 'file'
        else:
            ud.proto = "rsync"

        ud.branch = ud.parm.get("branch", "master")

        gitsrcname = '%s%s' % (ud.host, ud.path.replace('/', '.'))
        ud.mirrortarball = 'git_%s.tar.gz' % (gitsrcname)
        ud.clonedir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

        tag = Fetch.srcrev_internal_helper(ud, d)
        if tag is True:
            ud.tag = self.latest_revision(url, ud, d)	
        elif tag:
            ud.tag = tag

        if not ud.tag or ud.tag == "master":
            ud.tag = self.latest_revision(url, ud, d)	

        subdir = ud.parm.get("subpath", "")
        if subdir != "":
            if subdir.endswith("/"):
                subdir = subdir[:-1]
            subdirpath = os.path.join(ud.path, subdir);
        else:
            subdirpath = ud.path;

        if 'fullclone' in ud.parm:
            ud.localfile = ud.mirrortarball
        else:
            ud.localfile = data.expand('git_%s%s_%s.tar.gz' % (ud.host, subdirpath.replace('/', '.'), ud.tag), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def go(self, loc, ud, d):
        """Fetch url"""

        if ud.user:
            username = ud.user + '@'
        else:
            username = ""

        repofile = os.path.join(data.getVar("DL_DIR", d, 1), ud.mirrortarball)

        coname = '%s' % (ud.tag)
        codir = os.path.join(ud.clonedir, coname)

        if not os.path.exists(ud.clonedir):
            try:
                Fetch.try_mirrors(ud.mirrortarball)
                bb.mkdirhier(ud.clonedir)
                os.chdir(ud.clonedir)
                runfetchcmd("tar -xzf %s" % (repofile), d)
            except:
                runfetchcmd("git clone -n %s://%s%s%s %s" % (ud.proto, username, ud.host, ud.path, ud.clonedir), d)

        os.chdir(ud.clonedir)
        # Remove all but the .git directory
        if not self._contains_ref(ud.tag, d):
            runfetchcmd("rm * -Rf", d)
            runfetchcmd("git fetch %s://%s%s%s %s" % (ud.proto, username, ud.host, ud.path, ud.branch), d)
            runfetchcmd("git fetch --tags %s://%s%s%s" % (ud.proto, username, ud.host, ud.path), d)
            runfetchcmd("git prune-packed", d)
            runfetchcmd("git pack-redundant --all | xargs -r rm", d)

        os.chdir(ud.clonedir)
        mirror_tarballs = data.getVar("BB_GENERATE_MIRROR_TARBALLS", d, True)
        if mirror_tarballs != "0" or 'fullclone' in ud.parm: 
            bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git repository")
            runfetchcmd("tar -czf %s %s" % (repofile, os.path.join(".", ".git", "*") ), d)

        if 'fullclone' in ud.parm:
            return

        if os.path.exists(codir):
            bb.utils.prunedir(codir)

        subdir = ud.parm.get("subpath", "")
        if subdir != "":
            if subdir.endswith("/"):
                subdirbase = os.path.basename(subdir[:-1])
            else:
                subdirbase = os.path.basename(subdir)
        else:
            subdirbase = ""

        if subdir != "":
            readpathspec = ":%s" % (subdir)
            codir = os.path.join(codir, "git")
            coprefix = os.path.join(codir, subdirbase, "")
        else:
            readpathspec = ""
            coprefix = os.path.join(codir, "git", "")

        bb.mkdirhier(codir)
        os.chdir(ud.clonedir)
        runfetchcmd("git read-tree %s%s" % (ud.tag, readpathspec), d)
        runfetchcmd("git checkout-index -q -f --prefix=%s -a" % (coprefix), d)

        os.chdir(codir)
        bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git checkout")
        runfetchcmd("tar -czf %s %s" % (ud.localpath, os.path.join(".", "*") ), d)

        os.chdir(ud.clonedir)
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
        if ud.user:
            username = ud.user + '@'
        else:
            username = ""

        cmd = "git ls-remote %s://%s%s%s %s" % (ud.proto, username, ud.host, ud.path, ud.branch)
        output = runfetchcmd(cmd, d, True)
        if not output:
            raise bb.fetch.FetchError("Fetch command %s gave empty output\n" % (cmd))
        return output.split()[0]

    def _build_revision(self, url, ud, d):
        return ud.tag

    def _sortable_buildindex_disabled(self, url, ud, d, rev):
        """
        Return a suitable buildindex for the revision specified. This is done by counting revisions 
        using "git rev-list" which may or may not work in different circumstances.
        """

        cwd = os.getcwd()

        # Check if we have the rev already

        if not os.path.exists(ud.clonedir):
            print "no repo"
            self.go(None, ud, d)
            if not os.path.exists(ud.clonedir):
                bb.msg.error(bb.msg.domain.Fetcher, "GIT repository for %s doesn't exist in %s, cannot get sortable buildnumber, using old value" % (url, ud.clonedir))
                return None


        os.chdir(ud.clonedir)
        if not self._contains_ref(rev, d):
            self.go(None, ud, d)

        output = runfetchcmd("git rev-list %s -- 2> /dev/null | wc -l" % rev, d, quiet=True)
        os.chdir(cwd)

        buildindex = "%s" % output.split()[0]
        bb.msg.debug(1, bb.msg.domain.Fetcher, "GIT repository for %s in %s is returning %s revisions in rev-list before %s" % (url, ud.clonedir, buildindex, rev))
        return buildindex        

