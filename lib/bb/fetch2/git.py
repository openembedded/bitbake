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
from   bb.fetch2 import FetchMethod
from   bb.fetch2 import runfetchcmd
from   bb.fetch2 import logger

class Git(FetchMethod):
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

    def urldata_init(self, ud, d):
        """
        init git specific variable within url data
        so that the git method like latest_revision() can work
        """
        if 'protocol' in ud.parm:
            ud.proto = ud.parm['protocol']
        elif not ud.host:
            ud.proto = 'file'
        else:
            ud.proto = "rsync"

        ud.nocheckout = False
        if 'nocheckout' in ud.parm:
            ud.nocheckout = True

        branches = ud.parm.get("branch", "master").split(',')
        if len(branches) != len(ud.names):
            raise bb.fetch2.ParameterError("The number of name and branch parameters is not balanced", ud.url)
        ud.branches = {}
        for name in ud.names:
            branch = branches[ud.names.index(name)]
            ud.branches[name] = branch

        gitsrcname = '%s%s' % (ud.host, ud.path.replace('/', '.'))
        ud.mirrortarball = 'git2_%s.tar.gz' % (gitsrcname)
        ud.clonedir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

        ud.basecmd = data.getVar("FETCHCMD_git", d, True) or "git"

        for name in ud.names:
            # Ensure anything that doesn't look like a sha256 checksum/revision is translated into one
            if not ud.revisions[name] or len(ud.revisions[name]) != 40  or (False in [c in "abcdef0123456789" for c in ud.revisions[name]]):
                ud.revisions[name] = self.latest_revision(ud.url, ud, d, name)

        ud.localfile = ud.clonedir

    def localpath(self, url, ud, d):
        return ud.clonedir

    def need_update(self, u, ud, d):
        if not os.path.exists(ud.clonedir):
            return True
        os.chdir(ud.clonedir)
        for name in ud.names:
            if not self._contains_ref(ud.revisions[name], d):
                return True
        return False

    def try_premirror(self, u, ud, d):
        # If we don't do this, updating an existing checkout with only premirrors
        # is not possible
        if bb.data.getVar("BB_FETCH_PREMIRRORONLY", d, True) is not None:
            return True
        if os.path.exists(ud.clonedir):
            return False
        return True

    def download(self, loc, ud, d):
        """Fetch url"""

        if ud.user:
            username = ud.user + '@'
        else:
            username = ""

        repofile = os.path.join(data.getVar("DL_DIR", d, True), ud.mirrortarball)

        ud.repochanged = not os.path.exists(repofile)

        # If the checkout doesn't exist and the mirror tarball does, extract it
        if not os.path.exists(ud.clonedir) and os.path.exists(repofile):
            bb.mkdirhier(ud.clonedir)
            os.chdir(ud.clonedir)
            runfetchcmd("tar -xzf %s" % (repofile), d)

        # If the repo still doesn't exist, fallback to cloning it
        if not os.path.exists(ud.clonedir):
            bb.fetch2.check_network_access(d, "git clone --bare %s%s" % (ud.host, ud.path))
            runfetchcmd("%s clone --bare %s://%s%s%s %s" % (ud.basecmd, ud.proto, username, ud.host, ud.path, ud.clonedir), d)

        os.chdir(ud.clonedir)
        # Update the checkout if needed
        needupdate = False
        for name in ud.names:
            if not self._contains_ref(ud.revisions[name], d):
                needupdate = True
        if needupdate:
            bb.fetch2.check_network_access(d, "git fetch %s%s" % (ud.host, ud.path))
            try: 
                runfetchcmd("%s remote prune origin" % ud.basecmd, d) 
                runfetchcmd("%s remote rm origin" % ud.basecmd, d) 
            except bb.fetch2.FetchError:
                logger.debug(1, "No Origin")
            
            runfetchcmd("%s remote add origin %s://%s%s%s" % (ud.basecmd, ud.proto, username, ud.host, ud.path), d)
            runfetchcmd("%s fetch --all -t" % ud.basecmd, d)
            runfetchcmd("%s prune-packed" % ud.basecmd, d)
            runfetchcmd("%s pack-redundant --all | xargs -r rm" % ud.basecmd, d)
            ud.repochanged = True

    def build_mirror_data(self, url, ud, d):
        # Generate a mirror tarball if needed
        repofile = os.path.join(data.getVar("DL_DIR", d, True), ud.mirrortarball)

        os.chdir(ud.clonedir)
        mirror_tarballs = data.getVar("BB_GENERATE_MIRROR_TARBALLS", d, True)
        if mirror_tarballs != "0" and ud.repochanged:
            logger.info("Creating tarball of git repository")
            runfetchcmd("tar -czf %s %s" % (repofile, os.path.join(".") ), d)

    def unpack(self, ud, destdir, d):
        """ unpack the downloaded src to destdir"""

        subdir = ud.parm.get("subpath", "")
        if subdir != "":
            readpathspec = ":%s" % (subdir)
        else:
            readpathspec = ""

        destdir = os.path.join(destdir, "git/")
        if os.path.exists(destdir):
            bb.utils.prunedir(destdir)

        runfetchcmd("git clone -s -n %s %s" % (ud.clonedir, destdir), d)
        if not ud.nocheckout:
            os.chdir(destdir)
            runfetchcmd("%s read-tree %s%s" % (ud.basecmd, ud.revisions[ud.names[0]], readpathspec), d)
            runfetchcmd("%s checkout-index -q -f -a" % ud.basecmd, d)
        return True

    def supports_srcrev(self):
        return True

    def _contains_ref(self, tag, d):
        basecmd = data.getVar("FETCHCMD_git", d, True) or "git"
        output = runfetchcmd("%s log --pretty=oneline -n 1 %s -- 2> /dev/null | wc -l" % (basecmd, tag), d, quiet=True)
        return output.split()[0] != "0"

    def _revision_key(self, url, ud, d, name):
        """
        Return a unique key for the url
        """
        return "git:" + ud.host + ud.path.replace('/', '.') + ud.branches[name]

    def _latest_revision(self, url, ud, d, name):
        """
        Compute the HEAD revision for the url
        """
        if ud.user:
            username = ud.user + '@'
        else:
            username = ""

        bb.fetch2.check_network_access(d, "git ls-remote %s%s %s" % (ud.host, ud.path, ud.branches[name]))
        basecmd = data.getVar("FETCHCMD_git", d, True) or "git"
        cmd = "%s ls-remote %s://%s%s%s %s" % (basecmd, ud.proto, username, ud.host, ud.path, ud.branches[name])
        output = runfetchcmd(cmd, d, True)
        if not output:
            raise bb.fetch2.FetchError("The command %s gave empty output unexpectedly" % cmd, url)
        return output.split()[0]

    def _build_revision(self, url, ud, d, name):
        return ud.revisions[name]

    def _sortable_buildindex_disabled(self, url, ud, d, rev):
        """
        Return a suitable buildindex for the revision specified. This is done by counting revisions
        using "git rev-list" which may or may not work in different circumstances.
        """

        cwd = os.getcwd()

        # Check if we have the rev already

        if not os.path.exists(ud.clonedir):
            print("no repo")
            self.download(None, ud, d)
            if not os.path.exists(ud.clonedir):
                logger.error("GIT repository for %s doesn't exist in %s, cannot get sortable buildnumber, using old value", url, ud.clonedir)
                return None


        os.chdir(ud.clonedir)
        if not self._contains_ref(rev, d):
            self.download(None, ud, d)

        output = runfetchcmd("%s rev-list %s -- 2> /dev/null | wc -l" % (ud.basecmd, rev), d, quiet=True)
        os.chdir(cwd)

        buildindex = "%s" % output.split()[0]
        logger.debug(1, "GIT repository for %s in %s is returning %s revisions in rev-list before %s", url, ud.clonedir, buildindex, rev)
        return buildindex
