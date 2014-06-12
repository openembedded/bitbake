"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase

from bldcontrol.bbcontroller import LocalhostBEController, BitbakeController
from bldcontrol.models import BuildEnvironment, BuildRequest
from bldcontrol.management.commands.runbuilds import Command

import socket
import subprocess

class LocalhostBEControllerTests(TestCase):
    def test_StartAndStopServer(self):
        obe = BuildEnvironment.objects.create(lock = BuildEnvironment.LOCK_FREE, betype = BuildEnvironment.TYPE_LOCAL)
        lbc = LocalhostBEController(obe)

        # test start server and stop
        self.assertTrue(socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('localhost', 8200)), "Port already occupied")
        lbc.startBBServer()
        self.assertFalse(socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('localhost', 8200)), "Server not answering")

        lbc.stopBBServer()
        self.assertTrue(socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('localhost', 8200)), "Server not stopped")

        # clean up
        import subprocess
        out, err = subprocess.Popen("netstat  -tapn 2>/dev/null | grep 8200 | awk '{print $7}' | sort -fu | cut -d \"/\" -f 1 | grep -v -- - | tee /dev/fd/2 | xargs -r kill", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

        self.assertTrue(err == '', "bitbake server pid %s not stopped" % err)

        obe = BuildEnvironment.objects.create(lock = BuildEnvironment.LOCK_FREE, betype = BuildEnvironment.TYPE_LOCAL)
        lbc = LocalhostBEController(obe)

        bbc = lbc.getBBController()
        self.assertTrue(isinstance(bbc, BitbakeController))
        # test set variable
        try:
            bbc.setVariable
        except Exception as e :
            self.fail("setVariable raised %s", e)

        lbc.stopBBServer()
        out, err = subprocess.Popen("netstat  -tapn 2>/dev/null | grep 8200 | awk '{print $7}' | sort -fu | cut -d \"/\" -f 1 | grep -v -- - | tee /dev/fd/2 | xargs -r kill", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        self.assertTrue(err == '', "bitbake server pid %s not stopped" % err)


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
        from orm.models import Project
        p, created = Project.objects.get_or_create(pk=1)
        obr = BuildRequest.objects.create(state = BuildRequest.REQ_QUEUED, project = p)
        command = Command()
        br = command._selectBuildRequest()

        # make sure we select the object we've just built
        self.assertTrue(obr.id == br.id, "Request is not properly selected")
        # we have a locked environment
        self.assertTrue(br.state == BuildRequest.REQ_INPROGRESS, "Request is not updated")
        # no more selections possible here
        self.assertRaises(IndexError, command._selectBuildRequest)
