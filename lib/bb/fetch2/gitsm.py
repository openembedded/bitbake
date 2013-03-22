# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' git submodules implementation
"""

# Copyright (C) 2013 Richard Purdie
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
from   bb.fetch2.git import Git
from   bb.fetch2 import runfetchcmd
from   bb.fetch2 import logger

class GitSM(Git):
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with git.
        """
        return ud.type in ['gitsm']

    def uses_submodules(self, ud, d):
        for name in ud.names:
            try:
                runfetchcmd("%s show %s:.gitmodules" % (ud.basecmd, ud.revisions[name]), d, quiet=True)
                return True
            except bb.fetch.FetchError:
                pass
        return False

    def update_submodules(self, u, ud, d):
        # We have to convert bare -> full repo, do the submodule bit, then convert back
        tmpclonedir = ud.clonedir + ".tmp"
        gitdir = tmpclonedir + os.sep + ".git"
        bb.utils.remove(tmpclonedir, True)
        os.mkdir(tmpclonedir)
        os.rename(ud.clonedir, gitdir)
        runfetchcmd("sed " + gitdir + "/config -i -e 's/bare.*=.*true/bare = false/'", d)
        os.chdir(tmpclonedir)
        runfetchcmd("git reset --hard", d)
        runfetchcmd("git submodule init", d)
        runfetchcmd("git submodule update", d)
        runfetchcmd("sed " + gitdir + "/config -i -e 's/bare.*=.*false/bare = true/'", d)
        os.rename(gitdir, ud.clonedir,)
        bb.utils.remove(tmpclonedir, True)

    def download(self, loc, ud, d):
        Git.download(self, loc, ud, d)

        os.chdir(ud.clonedir)
        submodules = self.uses_submodules(ud, d)
        if submodules:
            self.update_submodules(loc, ud, d)

    def unpack(self, ud, destdir, d):
        Git.unpack(self, ud, destdir, d)
        
        os.chdir(ud.destdir)
        submodules = self.uses_submodules(ud, d)
        if submodules:
            runfetchcmd("cp -r " + ud.clonedir + "/modules " + ud.destdir + "/.git/", d)
            runfetchcmd("git submodule init", d)
            runfetchcmd("git submodule update", d)

