#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' git implementation

Copyright (C) 2005 Richard Purdie

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc., 59 Temple
Place, Suite 330, Boston, MA 02111-1307 USA. 
"""

import os, re
import bb
from   bb    import data
from   bb.fetch import Fetch
from   bb.fetch import FetchError

def prunedir(topdir):
    # Delete everything reachable from the directory named in 'topdir'.
    # CAUTION:  This is dangerous!
    for root, dirs, files in os.walk(topdir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

def rungitcmd(cmd,d):

    bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % cmd)

    # Need to export PATH as git is likely to be in metadata paths 
    # rather than host provided
    pathcmd = 'export PATH=%s; %s' % (data.expand('${PATH}', d), cmd)

    myret = os.system(pathcmd)

    if myret != 0:
        raise FetchError("Git: %s failed" % pathcmd)

class Git(Fetch):
    """Class to fetch a module or modules from git repositories"""
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with cvs.
        """
        return ud.type in ['git']

    def localpath(self, url, ud, d):

        ud.proto = "rsync"
        if 'protocol' in ud.parm:
            ud.proto = ud.parm['protocol']

        ud.tag = "master"
        if 'tag' in ud.parm:
            ud.tag = ud.parm['tag']

        ud.localfile = data.expand('git_%s%s_%s.tar.gz' % (ud.host, ud.path.replace('/', '.'), ud.tag), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def go(self, loc, ud, d):
        """Fetch url"""

        gitsrcname = '%s%s' % (ud.host, path.replace('/', '.'))

        repofilename = 'git_%s.tar.gz' % (gitsrcname)
        repofile = os.path.join(data.getVar("DL_DIR", d, 1), repofilename)
        repodir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

        coname = '%s' % (ud.tag)
        codir = os.path.join(repodir, coname)

        # tag=="master" must always update
        if (ud.tag != "master") and Fetch.try_mirror(d, ud.localfile):
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists (or was stashed). Skipping git checkout." % ud.localpath)
            return

        if not os.path.exists(repodir):
            if Fetch.try_mirror(d, repofilename):    
                bb.mkdirhier(repodir)
                os.chdir(repodir)
                rungitcmd("tar -xzf %s" % (repofile),d)
            else:
                rungitcmd("git clone -n %s://%s%s %s" % (ud.proto, ud.host, ud.path, repodir),d)

        os.chdir(repodir)
        rungitcmd("git pull %s://%s%s" % (ud.proto, ud.host, ud.path),d)
        rungitcmd("git pull --tags %s://%s%s" % (ud.proto, ud.host, ud.path),d)
        rungitcmd("git prune-packed", d)
        rungitcmd("git pack-redundant --all | xargs -r rm", d)
        # Remove all but the .git directory
        rungitcmd("rm * -Rf", d)
        # old method of downloading tags
        #rungitcmd("rsync -a --verbose --stats --progress rsync://%s%s/ %s" % (ud.host, ud.path, os.path.join(repodir, ".git", "")),d)

        os.chdir(repodir)
        bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git repository")
        rungitcmd("tar -czf %s %s" % (repofile, os.path.join(".", ".git", "*") ),d)

        if os.path.exists(codir):
            prunedir(codir)

        bb.mkdirhier(codir)
        os.chdir(repodir)
        rungitcmd("git read-tree %s" % (ud.tag),d)
        rungitcmd("git checkout-index -q -f --prefix=%s -a" % (os.path.join(codir, "git", "")),d)

        os.chdir(codir)
        bb.msg.note(1, bb.msg.domain.Fetcher, "Creating tarball of git checkout")
        rungitcmd("tar -czf %s %s" % (ud.localpath, os.path.join(".", "*") ),d)
