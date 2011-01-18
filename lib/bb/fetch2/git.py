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
from   bb.fetch2 import Fetch
from   bb.fetch2 import runfetchcmd
from   bb.fetch2 import logger

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

        ud.branch = ud.parm.get("branch", "master")

        gitsrcname = '%s%s' % (ud.host, ud.path.replace('/', '.'))
        ud.mirrortarball = 'git_%s.tar.gz' % (gitsrcname)
        ud.clonedir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

        ud.basecmd = data.getVar("FETCHCMD_git", d, True) or "git"

    def localpath(self, url, ud, d):
        ud.tag = ud.revision
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

        if 'noclone' in ud.parm:
            ud.localfile = None
            return None

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def forcefetch(self, url, ud, d):
        if 'fullclone' in ud.parm:
            return True
        if 'noclone' in ud.parm:
            return False
        if os.path.exists(ud.localpath):
            return False
        if not self._contains_ref(ud.tag, d):
            return True
        return False

    def try_premirror(self, u, ud, d):
        if 'noclone' in ud.parm:
            return False
        if os.path.exists(ud.clonedir):
            return False
        if os.path.exists(ud.localpath):
            return False

        return True

    def download(self, loc, ud, d):
        """Fetch url"""

        if ud.user:
            username = ud.user + '@'
        else:
            username = ""

        repofile = os.path.join(data.getVar("DL_DIR", d, 1), ud.mirrortarball)

        # If we have no existing clone and no mirror tarball, try and obtain one
        if not os.path.exists(ud.clonedir) and not os.path.exists(repofile):
            try:
                Fetch.try_mirrors(ud.mirrortarball)
            except:
                pass

        # If the checkout doesn't exist and the mirror tarball does, extract it
        if not os.path.exists(ud.clonedir) and os.path.exists(repofile):
            bb.mkdirhier(ud.clonedir)
            os.chdir(ud.clonedir)
            runfetchcmd("tar -xzf %s" % (repofile), d)

        # If the repo still doesn't exist, fallback to cloning it
        if not os.path.exists(ud.clonedir):
            runfetchcmd("%s clone -n %s://%s%s%s %s" % (ud.basecmd, ud.proto, username, ud.host, ud.path, ud.clonedir), d)

        os.chdir(ud.clonedir)
        # Update the checkout if needed
        if not self._contains_ref(ud.tag, d) or 'fullclone' in ud.parm:
            # Remove all but the .git directory
            runfetchcmd("rm * -Rf", d)
            if 'fullclone' in ud.parm:
                runfetchcmd("%s fetch --all" % (ud.basecmd), d)
            else:
                runfetchcmd("%s fetch %s://%s%s%s %s" % (ud.basecmd, ud.proto, username, ud.host, ud.path, ud.branch), d)
            runfetchcmd("%s fetch --tags %s://%s%s%s" % (ud.basecmd, ud.proto, username, ud.host, ud.path), d)
            runfetchcmd("%s prune-packed" % ud.basecmd, d)
            runfetchcmd("%s pack-redundant --all | xargs -r rm" % ud.basecmd, d)

    def build_mirror_data(self, url, ud, d):
        # Generate a mirror tarball if needed
        coname = '%s' % (ud.tag)
        codir = os.path.join(ud.clonedir, coname)
        repofile = os.path.join(data.getVar("DL_DIR", d, 1), ud.mirrortarball)

        os.chdir(ud.clonedir)
        mirror_tarballs = data.getVar("BB_GENERATE_MIRROR_TARBALLS", d, True)
        if mirror_tarballs != "0" or 'fullclone' in ud.parm:
            logger.info("Creating tarball of git repository")
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

        scmdata = ud.parm.get("scmdata", "")
        if scmdata == "keep":
            runfetchcmd("%s clone -n %s %s" % (ud.basecmd, ud.clonedir, coprefix), d)
            os.chdir(coprefix)
            runfetchcmd("%s checkout -q -f %s%s" % (ud.basecmd, ud.tag, readpathspec), d)
        else:
            bb.mkdirhier(codir)
            os.chdir(ud.clonedir)
            runfetchcmd("%s read-tree %s%s" % (ud.basecmd, ud.tag, readpathspec), d)
            runfetchcmd("%s checkout-index -q -f --prefix=%s -a" % (ud.basecmd, coprefix), d)

        os.chdir(codir)
        logger.info("Creating tarball of git checkout")
        runfetchcmd("tar -czf %s %s" % (ud.localpath, os.path.join(".", "*") ), d)

        os.chdir(ud.clonedir)
        bb.utils.prunedir(codir)

    def supports_srcrev(self):
        return True

    def _contains_ref(self, tag, d):
        basecmd = data.getVar("FETCHCMD_git", d, True) or "git"
        output = runfetchcmd("%s log --pretty=oneline -n 1 %s -- 2> /dev/null | wc -l" % (basecmd, tag), d, quiet=True)
        return output.split()[0] != "0"

    def _revision_key(self, url, ud, d):
        """
        Return a unique key for the url
        """
        return "git:" + ud.host + ud.path.replace('/', '.') + ud.branch

    def _latest_revision(self, url, ud, d):
        """
        Compute the HEAD revision for the url
        """
        if ud.user:
            username = ud.user + '@'
        else:
            username = ""

        basecmd = data.getVar("FETCHCMD_git", d, True) or "git"
        cmd = "%s ls-remote %s://%s%s%s %s" % (basecmd, ud.proto, username, ud.host, ud.path, ud.branch)
        output = runfetchcmd(cmd, d, True)
        if not output:
            raise bb.fetch2.FetchError("Fetch command %s gave empty output\n" % (cmd))
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
