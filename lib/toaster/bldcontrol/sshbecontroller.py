#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2014        Intel Corporation
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


import sys
import re
from django.db import transaction
from django.db.models import Q
from bldcontrol.models import BuildEnvironment, BRLayer, BRVariable, BRTarget, BRBitbake
import subprocess

from toastermain import settings

from bbcontroller import BuildEnvironmentController, ShellCmdException, BuildSetupException, _getgitcheckoutdirectoryname

def DN(path):
    return "/".join(path.split("/")[0:-1])

class SSHBEController(BuildEnvironmentController):
    """ Implementation of the BuildEnvironmentController for the localhost;
        this controller manages the default build directory,
        the server setup and system start and stop for the localhost-type build environment

    """

    def __init__(self, be):
        super(SSHBEController, self).__init__(be)
        self.dburl = settings.getDATABASE_URL()
        self.pokydirname = None
        self.islayerset = False

    def _shellcmd(self, command, cwd = None):
        if cwd is None:
            cwd = self.be.sourcedir

        p = subprocess.Popen("ssh %s 'cd %s && %s'" % (self.be.address, cwd, command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (out,err) = p.communicate()
        if p.returncode:
            if len(err) == 0:
                err = "command: %s \n%s" % (command, out)
            else:
                err = "command: %s \n%s" % (command, err)
            raise ShellCmdException(err)
        else:
            return out.strip()

    def _pathexists(self, path):
        try:
            self._shellcmd("test -e \"%s\"" % path)
            return True
        except ShellCmdException as e:
            return False

    def _pathcreate(self, path):
        self._shellcmd("mkdir -p \"%s\"" % path)

    def _setupBE(self):
        assert self.pokydirname and self._pathexists(self.pokydirname)
        self._pathcreate(self.be.builddir)
        self._shellcmd("bash -c \"source %s/oe-init-build-env %s\"" % (self.pokydirname, self.be.builddir))

    def startBBServer(self):
        assert self.pokydirname and self._pathexists(self.pokydirname)
        assert self.islayerset
        print self._shellcmd("bash -c \"source %s/oe-init-build-env %s && DATABASE_URL=%s source toaster start noweb && sleep 1\"" % (self.pokydirname, self.be.builddir, self.dburl))
        # FIXME unfortunate sleep 1 - we need to make sure that bbserver is started and the toaster ui is connected
        # but since they start async without any return, we just wait a bit
        print "Started server"
        assert self.be.sourcedir and self._pathexists(self.be.builddir)
        self.be.bbaddress = self.be.address.split("@")[-1]
        self.be.bbport = "8200"
        self.be.bbstate = BuildEnvironment.SERVER_STARTED
        self.be.save()

    def stopBBServer(self):
        assert self.pokydirname and self._pathexists(self.pokydirname)
        assert self.islayerset
        print self._shellcmd("bash -c \"source %s/oe-init-build-env %s && %s source toaster stop\"" %
            (self.pokydirname, self.be.builddir, (lambda: "" if self.be.bbtoken is None else "BBTOKEN=%s" % self.be.bbtoken)()))
        self.be.bbstate = BuildEnvironment.SERVER_STOPPED
        self.be.save()
        print "Stopped server"

    def setLayers(self, bitbakes, layers):
        """ a word of attention: by convention, the first layer for any build will be poky! """

        assert self.be.sourcedir is not None
        assert len(bitbakes) == 1
        # set layers in the layersource

        # 1. get a list of repos, and map dirpaths for each layer
        gitrepos = {}
        gitrepos[bitbakes[0].giturl] = []
        gitrepos[bitbakes[0].giturl].append( ("bitbake", bitbakes[0].dirpath, bitbakes[0].commit) )
        
        for layer in layers:
            # we don't process local URLs
            if layer.giturl.startswith("file://"):
                continue
            if not layer.giturl in gitrepos:
                gitrepos[layer.giturl] = []
            gitrepos[layer.giturl].append( (layer.name, layer.dirpath, layer.commit))
        for giturl in gitrepos.keys():
            commitid = gitrepos[giturl][0][2]
            for e in gitrepos[giturl]:
                if commitid != e[2]:
                    raise BuildSetupException("More than one commit per git url, unsupported configuration")

        layerlist = []

        # 2. checkout the repositories
        for giturl in gitrepos.keys():
            import os
            localdirname = os.path.join(self.be.sourcedir, _getgitcheckoutdirectoryname(giturl))
            print "DEBUG: giturl ", giturl ,"checking out in current directory", localdirname

            # make sure our directory is a git repository
            if self._pathexists(localdirname):
                if not giturl in self._shellcmd("git remote -v", localdirname):
                    raise BuildSetupException("Existing git repository at %s, but with different remotes (not '%s'). Aborting." % (localdirname, giturl))
            else:
                self._shellcmd("git clone \"%s\" \"%s\"" % (giturl, localdirname))
            # checkout the needed commit
            commit = gitrepos[giturl][0][2]

            # branch magic name "HEAD" will inhibit checkout
            if commit != "HEAD":
                print "DEBUG: checking out commit ", commit, "to", localdirname
                self._shellcmd("git fetch --all && git checkout \"%s\"" % commit , localdirname)

            # take the localdirname as poky dir if we can find the oe-init-build-env
            if self.pokydirname is None and self._pathexists(os.path.join(localdirname, "oe-init-build-env")):
                print "DEBUG: selected poky dir name", localdirname
                self.pokydirname = localdirname

            # verify our repositories
            for name, dirpath, commit in gitrepos[giturl]:
                localdirpath = os.path.join(localdirname, dirpath)
                if not self._pathexists(localdirpath):
                    raise BuildSetupException("Cannot find layer git path '%s' in checked out repository '%s:%s'. Aborting." % (localdirpath, giturl, commit))

                if name != "bitbake":
                    layerlist.append(localdirpath)

        print "DEBUG: current layer list ", layerlist

        # 3. configure the build environment, so we have a conf/bblayers.conf
        assert self.pokydirname is not None
        self._setupBE()

        # 4. update the bblayers.conf
        bblayerconf = os.path.join(self.be.builddir, "conf/bblayers.conf")
        if not self._pathexists(bblayerconf):
            raise BuildSetupException("BE is not consistent: bblayers.conf file missing at %s" % bblayerconf)

        conflines = open(bblayerconf, "r").readlines()

        bblayerconffile = open(bblayerconf, "w")
        for i in xrange(len(conflines)):
            if conflines[i].startswith("# line added by toaster"):
                i += 2
            else:
                bblayerconffile.write(conflines[i])

        bblayerconffile.write("\n# line added by toaster build control\nBBLAYERS = \"" + " ".join(layerlist) + "\"")
        bblayerconffile.close()

        self.islayerset = True
        return True

    def release(self):
        assert self.be.sourcedir and self._pathexists(self.be.builddir)
        import shutil
        shutil.rmtree(os.path.join(self.be.sourcedir, "build"))
        assert not self._pathexists(self.be.builddir)
