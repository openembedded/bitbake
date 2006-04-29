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

def getprotocol(parm):
    if 'protocol' in parm:
        proto = parm['protocol']
    else:
        proto = ""
    if not proto:
        proto = "rsync"

    return proto

def localfile(url, d):
    """Return the filename to cache the checkout in"""
    (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(url, d))

    #if user sets localpath for file, use it instead.
    if "localpath" in parm:
        return parm["localpath"]

    tag = gettag(parm)

    return data.expand('git_%s%s_%s.tar.gz' % (host, path.replace('/', '.'), tag), d)

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

        return os.path.join(data.getVar("DL_DIR", d, 1), localfile(url, d))

    localpath = staticmethod(localpath)

    def go(self, d, urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        for loc in urls:
            (type, host, path, user, pswd, parm) = bb.decodeurl(data.expand(loc, d))

            tag = gettag(parm)
            proto = getprotocol(parm)

            gitsrcname = '%s%s' % (host, path.replace('/', '.'))

            repofilename = 'git_%s.tar.gz' % (gitsrcname)
            repofile = os.path.join(data.getVar("DL_DIR", d, 1), repofilename)
            repodir = os.path.join(data.expand('${GITDIR}', d), gitsrcname)

            coname = '%s' % (tag)
            codir = os.path.join(repodir, coname)

            cofile = self.localpath(loc, d)

            # tag=="master" must always update
            if (tag != "master") and Fetch.try_mirror(d, localfile(loc, d)):
                bb.debug(1, "%s already exists (or was stashed). Skipping git checkout." % cofile)
                continue

            if not os.path.exists(repodir):
                if Fetch.try_mirror(d, repofilename):    
                    bb.mkdirhier(repodir)
                    os.chdir(repodir)
                    rungitcmd("tar -xzf %s" % (repofile),d)
                else:
                    rungitcmd("git clone -n %s://%s%s %s" % (proto, host, path, repodir),d)

            os.chdir(repodir)
            rungitcmd("git pull %s://%s%s" % (proto, host, path),d)
            rungitcmd("git pull --tags %s://%s%s" % (proto, host, path),d)
            rungitcmd("git prune-packed", d)
            # old method of downloading tags
            #rungitcmd("rsync -a --verbose --stats --progress rsync://%s%s/ %s" % (host, path, os.path.join(repodir, ".git", "")),d)

            os.chdir(repodir)
            bb.note("Creating tarball of git repository")
            rungitcmd("tar -czf %s %s" % (repofile, os.path.join(".", ".git", "*") ),d)

            if os.path.exists(codir):
                prunedir(codir)

            bb.mkdirhier(codir)
            os.chdir(repodir)
            rungitcmd("git read-tree %s" % (tag),d)
            rungitcmd("git checkout-index -q -f --prefix=%s -a" % (os.path.join(codir, "git", "")),d)

            os.chdir(codir)
            bb.note("Creating tarball of git checkout")
            rungitcmd("tar -czf %s %s" % (cofile, os.path.join(".", "*") ),d)
