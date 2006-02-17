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

    bb.debug(1, "Running %s" % cmd)

    # Need to export PATH as git is likely to be in metadata paths 
    # rather than host provided
    pathcmd = 'export PATH=%s; %s' % (data.expand('${PATH}', d), cmd)

    myret = os.system(pathcmd)

    if myret != 0:
        raise FetchError("Git: %s failed" % pathcmd)

def gettag(parm):
    if 'tag' in parm:
        tag = parm['tag']
    else:
        tag = ""
    if not tag:
        tag = "master"

    return tag

class Git(Fetch):
    """Class to fetch a module or modules from git repositories"""
    def supports(url, d):
        """Check to see if a given url can be fetched with cvs.
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))
        return type in ['git']
    supports = staticmethod(supports)

    def localpath(url, d):
        (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))

        #if user sets localpath for file, use it instead.
        if "localpath" in parm:
            return parm["localpath"]

        tag = gettag(parm)

        localname = data.expand('git_%s%s_%s.tar.gz' % (host, path.replace('/', '.'), tag), d)

        return os.path.join(data.getVar("DL_DIR", d, 1),data.expand('%s' % (localname), d))

    localpath = staticmethod(localpath)

    def go(self, d, urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        for loc in urls:
            (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(loc, d))

            tag = gettag(parm)

            gitsrcname = '%s%s' % (host, path.replace('/', '.'))

            repofile = os.path.join(data.getVar("DL_DIR", d, 1), 'git_%s.tar.gz' % (gitsrcname))
            repodir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

            coname = '%s' % (tag)
            codir = os.path.join(repodir, coname)

            cofile = self.localpath(loc, d)

            # Always update to current if tag=="master"
            #if os.access(cofile, os.R_OK) and (tag != "master"):
            if os.access(cofile, os.R_OK):
                bb.debug(1, "%s already exists, skipping git checkout." % cofile)
                continue

# Still Need to add GIT_TARBALL_STASH Support...
#           if Fetch.try_mirror(d, tarfn):
#               continue

            #if os.path.exists(repodir):
                #prunedir(repodir)

            bb.mkdirhier(repodir)
            os.chdir(repodir)

            #print("Changing to %s" % repodir)

            if os.access(repofile, os.R_OK):
                rungitcmd("tar -xzf %s" % (repofile),d)
            else:
                rungitcmd("git clone rsync://%s%s %s" % (host, path, repodir),d)

            rungitcmd("rsync -a --verbose --stats --progress rsync://%s%s/ %s" % (host, path, os.path.join(repodir, ".git", "")),d)

            #print("Changing to %s" % repodir)
            os.chdir(repodir)
            rungitcmd("git pull rsync://%s%s" % (host, path),d)

            #print("Changing to %s" % repodir)
            os.chdir(repodir)
            rungitcmd("tar -czf %s %s" % (repofile, os.path.join(".", ".git", "*") ),d)

            if os.path.exists(codir):
                prunedir(codir)

            #print("Changing to %s" % repodir)
            bb.mkdirhier(codir)
            os.chdir(repodir)
            rungitcmd("git read-tree %s" % (tag),d)

            rungitcmd("git checkout-index -q -f --prefix=%s -a" % (os.path.join(codir, "git", "")),d)

            #print("Changing to %s" % codir)
            os.chdir(codir)
            rungitcmd("tar -czf %s %s" % (cofile, os.path.join(".", "*") ),d)

