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

def prunedir(topdir):
    # Delete everything reachable from the directory named in 'topdir'.
    # CAUTION:  This is dangerous!
    for root, dirs, files in os.walk(topdir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

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

        tag = data.getVar("SRCREV", d, 0)
        if 'tag' in ud.parm and len(ud.parm['tag']) == 40:
            ud.tag = ud.parm['tag']
        elif tag and "get_srcrev" not in tag and len(tag) == 40:
            ud.tag = tag
        else:
            ud.tag = self.latest_revision(url, ud, d)

        ud.localfile = data.expand('git_%s%s_%s.tar.gz' % (ud.host, ud.path.replace('/', '.'), ud.tag), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def go(self, loc, ud, d):
        """Fetch url"""

        if Fetch.try_mirror(d, ud.localfile):
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists (or was stashed). Skipping git checkout." % ud.localpath)
            return

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
                runfetchcmd("git clone -n %s://%s%s %s" % (ud.proto, ud.host, ud.path, repodir), d)

        os.chdir(repodir)
        # Remove all but the .git directory
        runfetchcmd("rm * -Rf", d)
        runfetchcmd("git pull %s://%s%s" % (ud.proto, ud.host, ud.path), d)
        runfetchcmd("git pull --tags %s://%s%s" % (ud.proto, ud.host, ud.path), d)
        runfetchcmd("git prune-packed", d)
        runfetchcmd("git pack-redundant --all | xargs -r rm", d)
        # old method of downloading tags
        #runfetchcmd("rsync -a --verbose --stats --progress rsync://%s%s/ %s" % (ud.host, ud.path, os.path.join(repodir, ".git", "")), d)

        os.chdir(repodir)
        bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git repository")
        runfetchcmd("tar -czf %s %s" % (repofile, os.path.join(".", ".git", "*") ), d)

        if os.path.exists(codir):
            prunedir(codir)

        bb.mkdirhier(codir)
        os.chdir(repodir)
        runfetchcmd("git read-tree %s" % (ud.tag), d)
        runfetchcmd("git checkout-index -q -f --prefix=%s -a" % (os.path.join(codir, "git", "")), d)

        os.chdir(codir)
        bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git checkout")
        runfetchcmd("tar -czf %s %s" % (ud.localpath, os.path.join(".", "*") ), d)

        os.chdir(repodir)
        prunedir(codir)

    def suppports_srcrev(self):
        return True

    def _revision_key(self, url, ud, d):
        """
        Return a unique key for the url
        """
        return "git:" + ud.host + ud.path.replace('/', '.')

    def _latest_revision(self, url, ud, d):

        output = runfetchcmd("git ls-remote %s://%s%s" % (ud.proto, ud.host, ud.path), d, True)
        return output.split()[0]

