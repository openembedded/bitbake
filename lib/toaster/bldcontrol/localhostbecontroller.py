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


import os
import sys
import re
import shutil
from django.db import transaction
from django.db.models import Q
from bldcontrol.models import BuildEnvironment, BRLayer, BRVariable, BRTarget, BRBitbake
from orm.models import CustomImageRecipe, Layer, Layer_Version, ProjectLayer
import subprocess

from toastermain import settings

from bbcontroller import BuildEnvironmentController, ShellCmdException, BuildSetupException

import logging
logger = logging.getLogger("toaster")

from pprint import pprint, pformat

class LocalhostBEController(BuildEnvironmentController):
    """ Implementation of the BuildEnvironmentController for the localhost;
        this controller manages the default build directory,
        the server setup and system start and stop for the localhost-type build environment

    """

    def __init__(self, be):
        super(LocalhostBEController, self).__init__(be)
        self.pokydirname = None
        self.islayerset = False

    def _shellcmd(self, command, cwd = None):
        if cwd is None:
            cwd = self.be.sourcedir

        logger.debug("lbc_shellcmmd: (%s) %s" % (cwd, command))
        p = subprocess.Popen(command, cwd = cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out,err) = p.communicate()
        p.wait()
        if p.returncode:
            if len(err) == 0:
                err = "command: %s \n%s" % (command, out)
            else:
                err = "command: %s \n%s" % (command, err)
            logger.warn("localhostbecontroller: shellcmd error %s" % err)
            raise ShellCmdException(err)
        else:
            logger.debug("localhostbecontroller: shellcmd success")
            return out

    def startBBServer(self):
        assert self.pokydirname and os.path.exists(self.pokydirname)
        assert self.islayerset

        # find our own toasterui listener/bitbake
        from toaster.bldcontrol.management.commands.loadconf import _reduce_canon_path

        toaster = _reduce_canon_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../bin/toaster"))
        assert os.path.exists(toaster) and os.path.isfile(toaster)

        # restart bitbake server and toastergui observer
        self._shellcmd("bash -c 'source %s restart-bitbake'" % toaster, self.be.builddir)
        logger.debug("localhostbecontroller: restarted bitbake server")

        # read port number from bitbake.lock
        self.be.bbport = ""
        bblock = os.path.join(self.be.builddir, 'bitbake.lock')
        if os.path.exists(bblock):
            with open(bblock) as fplock:
                for line in fplock:
                    if ":" in line:
                        self.be.bbport = line.split(":")[-1].strip()
                        logger.debug("localhostbecontroller: bitbake port %s", self.be.bbport)
                        break

        if not self.be.bbport:
            raise BuildSetupException("localhostbecontroller: can't read bitbake port from %s" % bblock)

        self.be.bbaddress = "localhost"
        self.be.bbstate = BuildEnvironment.SERVER_STARTED
        self.be.save()

    def getGitCloneDirectory(self, url, branch):
        """Construct unique clone directory name out of url and branch."""
        if branch != "HEAD":
            return "_toaster_clones/_%s_%s" % (re.sub('[:/@%]', '_', url), branch)

        # word of attention; this is a localhost-specific issue; only on the localhost we expect to have "HEAD" releases
        # which _ALWAYS_ means the current poky checkout
        from os.path import dirname as DN
        local_checkout_path = DN(DN(DN(DN(DN(os.path.abspath(__file__))))))
        #logger.debug("localhostbecontroller: using HEAD checkout in %s" % local_checkout_path)
        return local_checkout_path


    def setLayers(self, bitbake, layers, targets):
        """ a word of attention: by convention, the first layer for any build will be poky! """

        assert self.be.sourcedir is not None
        # set layers in the layersource

        # 1. get a list of repos with branches, and map dirpaths for each layer
        gitrepos = {}

        gitrepos[(bitbake.giturl, bitbake.commit)] = []
        gitrepos[(bitbake.giturl, bitbake.commit)].append( ("bitbake", bitbake.dirpath) )

        for layer in layers:
            # we don't process local URLs
            if layer.giturl.startswith("file://"):
                continue
            if not (layer.giturl, layer.commit) in gitrepos:
                gitrepos[(layer.giturl, layer.commit)] = []
            gitrepos[(layer.giturl, layer.commit)].append( (layer.name, layer.dirpath) )


        logger.debug("localhostbecontroller, our git repos are %s" % pformat(gitrepos))


        # 2. Note for future use if the current source directory is a
        # checked-out git repos that could match a layer's vcs_url and therefore
        # be used to speed up cloning (rather than fetching it again).

        cached_layers = {}

        try:
            for remotes in self._shellcmd("git remote -v", self.be.sourcedir).split("\n"):
                try:
                    remote = remotes.split("\t")[1].split(" ")[0]
                    if remote not in cached_layers:
                        cached_layers[remote] = self.be.sourcedir
                except IndexError:
                    pass
        except ShellCmdException:
            # ignore any errors in collecting git remotes this is an optional
            # step
            pass

        logger.info("Using pre-checked out source for layer %s", cached_layers)

        layerlist = []


        # 3. checkout the repositories
        for giturl, commit in gitrepos.keys():
            localdirname = os.path.join(self.be.sourcedir, self.getGitCloneDirectory(giturl, commit))
            logger.debug("localhostbecontroller: giturl %s:%s checking out in current directory %s" % (giturl, commit, localdirname))

            # make sure our directory is a git repository
            if os.path.exists(localdirname):
                localremotes = self._shellcmd("git remote -v", localdirname)
                if not giturl in localremotes:
                    raise BuildSetupException("Existing git repository at %s, but with different remotes ('%s', expected '%s'). Toaster will not continue out of fear of damaging something." % (localdirname, ", ".join(localremotes.split("\n")), giturl))
            else:
                if giturl in cached_layers:
                    logger.debug("localhostbecontroller git-copying %s to %s" % (cached_layers[giturl], localdirname))
                    self._shellcmd("git clone \"%s\" \"%s\"" % (cached_layers[giturl], localdirname))
                    self._shellcmd("git remote remove origin", localdirname)
                    self._shellcmd("git remote add origin \"%s\"" % giturl, localdirname)
                else:
                    logger.debug("localhostbecontroller: cloning %s in %s" % (giturl, localdirname))
                    self._shellcmd('git clone "%s" "%s"' % (giturl, localdirname))

            # branch magic name "HEAD" will inhibit checkout
            if commit != "HEAD":
                logger.debug("localhostbecontroller: checking out commit %s to %s " % (commit, localdirname))
                ref = commit if re.match('^[a-fA-F0-9]+$', commit) else 'origin/%s' % commit
                self._shellcmd('git fetch --all && git reset --hard "%s"' % ref, localdirname)

            # take the localdirname as poky dir if we can find the oe-init-build-env
            if self.pokydirname is None and os.path.exists(os.path.join(localdirname, "oe-init-build-env")):
                logger.debug("localhostbecontroller: selected poky dir name %s" % localdirname)
                self.pokydirname = localdirname

                # make sure we have a working bitbake
                if not os.path.exists(os.path.join(self.pokydirname, 'bitbake')):
                    logger.debug("localhostbecontroller: checking bitbake into the poky dirname %s " % self.pokydirname)
                    self._shellcmd("git clone -b \"%s\" \"%s\" \"%s\" " % (bitbake.commit, bitbake.giturl, os.path.join(self.pokydirname, 'bitbake')))

            # verify our repositories
            for name, dirpath in gitrepos[(giturl, commit)]:
                localdirpath = os.path.join(localdirname, dirpath)
                logger.debug("localhostbecontroller: localdirpath expected '%s'" % localdirpath)
                if not os.path.exists(localdirpath):
                    raise BuildSetupException("Cannot find layer git path '%s' in checked out repository '%s:%s'. Aborting." % (localdirpath, giturl, commit))

                if name != "bitbake":
                    layerlist.append(localdirpath.rstrip("/"))

        logger.debug("localhostbecontroller: current layer list %s " % pformat(layerlist))

        # 4. update the bblayers.conf
        bblayerconf = os.path.join(self.be.builddir, "conf/bblayers.conf")
        if not os.path.exists(bblayerconf):
            raise BuildSetupException("BE is not consistent: bblayers.conf file missing at %s" % bblayerconf)

        # 5. create custom layer and add custom recipes to it
        layerpath = os.path.join(self.be.sourcedir, "_meta-toaster-custom")
        if os.path.isdir(layerpath):
            shutil.rmtree(layerpath) # remove leftovers from previous builds
        for target in targets:
            try:
                customrecipe = CustomImageRecipe.objects.get(name=target.target,
                                                             project=bitbake.req.project)
            except CustomImageRecipe.DoesNotExist:
                continue # not a custom recipe, skip

            # create directory structure
            for name in ("conf", "recipes"):
                path = os.path.join(layerpath, name)
                if not os.path.isdir(path):
                    os.makedirs(path)

            # create layer.oonf
            config = os.path.join(layerpath, "conf", "layer.conf")
            if not os.path.isfile(config):
                with open(config, "w") as conf:
                    conf.write('BBPATH .= ":${LAYERDIR}"\nBBFILES += "${LAYERDIR}/recipes/*.bb"\n')

            # create recipe
            recipe_path = \
                    os.path.join(layerpath, "recipes", "%s.bb" % target.target)
            with open(recipe_path, "w") as recipef:
                recipef.write(customrecipe.generate_recipe_file_contents())

            # Update the layer and recipe objects
            customrecipe.layer_version.dirpath = layerpath
            customrecipe.layer_version.save()

            customrecipe.file_path = recipe_path
            customrecipe.save()

            # create *Layer* objects needed for build machinery to work
            BRLayer.objects.get_or_create(req=target.req,
                                          name=layer.name,
                                          dirpath=layerpath,
                                          giturl="file://%s" % layerpath)
        if os.path.isdir(layerpath):
            layerlist.append(layerpath)

        BuildEnvironmentController._updateBBLayers(bblayerconf, layerlist)

        self.islayerset = True
        return True

    def readServerLogFile(self):
        return open(os.path.join(self.be.builddir, "toaster_server.log"), "r").read()

    def release(self):
        assert self.be.sourcedir and os.path.exists(self.be.builddir)
        import shutil
        shutil.rmtree(os.path.join(self.be.sourcedir, "build"))
        assert not os.path.exists(self.be.builddir)


    def triggerBuild(self, bitbake, layers, variables, targets):
        # set up the build environment with the needed layers
        self.setLayers(bitbake, layers, targets)

        # write configuration file
        filepath = os.path.join(self.be.builddir, "conf/toaster.conf")
        with open(filepath, 'w') as conf:
            for var in variables:
                conf.write('%s="%s"\n' % (var.name, var.value))
            conf.write('INHERIT+="toaster buildhistory"')

        # get the bb server running with the build req id and build env id
        bbctrl = self.getBBController()

        # set variables
        for var in variables:
            bbctrl.setVariable(var.name, var.value)
            if var.name == 'TOASTER_BRBE':
                bbctrl.triggerEvent('bb.event.MetadataEvent("SetBRBE", "%s")' \
                                     % var.value)

        # Add 'toaster' and 'buildhistory' to INHERIT variable
        inherit = {item.strip() for item in bbctrl.getVariable('INHERIT').split()}
        inherit = inherit.union(["toaster", "buildhistory"])
        bbctrl.setVariable('INHERIT', ' '.join(inherit))

        # trigger the build command
        task = reduce(lambda x, y: x if len(y)== 0 else y, map(lambda y: y.task, targets))
        if len(task) == 0:
            task = None

        bbctrl.build(list(map(lambda x:x.target, targets)), task)

        logger.debug("localhostbecontroller: Build launched, exiting. Follow build logs at %s/toaster_ui.log" % self.be.builddir)

        # disconnect from the server
        bbctrl.disconnect()
