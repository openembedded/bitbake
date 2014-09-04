"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase

from bldcontrol.bbcontroller import BitbakeController
from bldcontrol.localhostbecontroller import LocalhostBEController
from bldcontrol.sshbecontroller import SSHBEController
from bldcontrol.models import BuildEnvironment, BuildRequest
from bldcontrol.management.commands.runbuilds import Command

import socket
import subprocess

# standard poky data hardcoded for testing
BITBAKE_LAYERS = [type('bitbake_info', (object,), { "giturl": "git://git.yoctoproject.org/poky.git", "dirpath": "", "commit": "HEAD"})]
POKY_LAYERS = [
    type('poky_info', (object,), { "name": "meta", "giturl": "git://git.yoctoproject.org/poky.git", "dirpath": "meta", "commit": "HEAD"}),
    type('poky_info', (object,), { "name": "meta-yocto", "giturl": "git://git.yoctoproject.org/poky.git", "dirpath": "meta-yocto", "commit": "HEAD"}),
    type('poky_info', (object,), { "name": "meta-yocto-bsp", "giturl": "git://git.yoctoproject.org/poky.git", "dirpath": "meta-yocto-bsp", "commit": "HEAD"}),
    ]



# we have an abstract test class designed to ensure that the controllers use a single interface
# specific controller tests only need to override the _getBuildEnvironment() method

class BEControllerTests(object):

    def _serverForceStop(self, bc):
        err = bc._shellcmd("netstat  -tapn 2>/dev/null | grep 8200 | awk '{print $7}' | sort -fu | cut -d \"/\" -f 1 | grep -v -- - | tee /dev/fd/2 | xargs -r kill")
        self.assertTrue(err == '', "bitbake server pid %s not stopped" % err)

    def test_serverStartAndStop(self):
        obe =  self._getBuildEnvironment()
        bc = self._getBEController(obe)
        bc.setLayers(BITBAKE_LAYERS, POKY_LAYERS) # setting layers, skip any layer info

        hostname = self.test_address.split("@")[-1]

        # test start server and stop
        self.assertTrue(socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex((hostname, 8200)), "Port already occupied")
        bc.startBBServer()
        self.assertFalse(socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex((hostname, 8200)), "Server not answering")

        bc.stopBBServer()
        self.assertTrue(socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex((hostname, 8200)), "Server not stopped")

        self._serverForceStop(bc)

    def test_getBBController(self):
        obe = self._getBuildEnvironment()
        bc = self._getBEController(obe)
        bc.setLayers(BITBAKE_LAYERS, POKY_LAYERS) # setting layers, skip any layer info

        bbc = bc.getBBController()
        self.assertTrue(isinstance(bbc, BitbakeController))
        # test set variable, use no build marker -1 for BR value
        try:
            bbc.setVariable("TOASTER_BRBE", "%d:%d" % (-1, obe.pk))
        except Exception as e :
            self.fail("setVariable raised %s", e)

        bc.stopBBServer()

        self._serverForceStop(bc)

class LocalhostBEControllerTests(TestCase, BEControllerTests):
    def __init__(self, *args):
        super(LocalhostBEControllerTests, self).__init__(*args)
        # hardcoded for Alex's machine; since the localhost BE is machine-dependent,
        # I found no good way to abstractize this
        self.test_sourcedir = "/home/ddalex/ssd/yocto"
        self.test_builddir = "/home/ddalex/ssd/yocto/build"
        self.test_address = "localhost"

    def _getBuildEnvironment(self):
        return BuildEnvironment.objects.create(
                lock = BuildEnvironment.LOCK_FREE,
                betype = BuildEnvironment.TYPE_LOCAL,
                address = self.test_address,
                sourcedir = self.test_sourcedir,
                builddir = self.test_builddir )

    def _getBEController(self, obe):
        return LocalhostBEController(obe)

class SSHBEControllerTests(TestCase, BEControllerTests):
    def __init__(self, *args):
        super(SSHBEControllerTests, self).__init__(*args)
        self.test_address = "ddalex-desktop.local"
        # hardcoded for ddalex-desktop.local machine; since the localhost BE is machine-dependent,
        # I found no good way to abstractize this
        self.test_sourcedir = "/home/ddalex/ssd/yocto"
        self.test_builddir = "/home/ddalex/ssd/yocto/build"

    def _getBuildEnvironment(self):
        return BuildEnvironment.objects.create(
                lock = BuildEnvironment.LOCK_FREE,
                betype = BuildEnvironment.TYPE_SSH,
                address = self.test_address,
                sourcedir = self.test_sourcedir,
                builddir = self.test_builddir )

    def _getBEController(self, obe):
        return SSHBEController(obe)

    def test_pathExists(self):
        obe = BuildEnvironment.objects.create(betype = BuildEnvironment.TYPE_SSH, address= self.test_address)
        sbc = SSHBEController(obe)
        self.assertTrue(sbc._pathexists("/"))
        self.assertFalse(sbc._pathexists("/.deadbeef"))
        self.assertTrue(sbc._pathexists(sbc._shellcmd("pwd")))


class RunBuildsCommandTests(TestCase):
    def test_bec_select(self):
        """
        Tests that we can find and lock a build environment
        """

        obe = BuildEnvironment.objects.create(lock = BuildEnvironment.LOCK_FREE, betype = BuildEnvironment.TYPE_LOCAL)
        command = Command()
        bec = command._selectBuildEnvironment()

        # make sure we select the object we've just built
        self.assertTrue(bec.be.id == obe.id, "Environment is not properly selected")
        # we have a locked environment
        self.assertTrue(bec.be.lock == BuildEnvironment.LOCK_LOCK, "Environment is not locked")
        # no more selections possible here
        self.assertRaises(IndexError, command._selectBuildEnvironment)

    def test_br_select(self):
        from orm.models import Project, Release, BitbakeVersion
        p = Project.objects.create_project("test", Release.objects.get_or_create(name = "HEAD", bitbake_version = BitbakeVersion.objects.get_or_create(name="HEAD", branch="HEAD")[0])[0])
        obr = BuildRequest.objects.create(state = BuildRequest.REQ_QUEUED, project = p)
        command = Command()
        br = command._selectBuildRequest()

        # make sure we select the object we've just built
        self.assertTrue(obr.id == br.id, "Request is not properly selected")
        # we have a locked environment
        self.assertTrue(br.state == BuildRequest.REQ_INPROGRESS, "Request is not updated")
        # no more selections possible here
        self.assertRaises(IndexError, command._selectBuildRequest)
