#!/usr/bin/python

# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2015 Alexandru Damian for Intel Corp.
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


# Test definitions. The runner will look for and auto-discover the tests
# no matter what they file are they in, as long as they are in the same directory
# as this file.

import unittest
from shellutils import *

import pexpect
import sys, os, signal, time

class TestPyCompilable(unittest.TestCase):
    ''' Verifies that all Python files are syntactically correct '''
    def test_compile_file(self):
        try:
            out = run_shell_cmd("find . -name *py -type f -print0 | xargs -0 -n1 -P20 python -m py_compile", config.testdir)
        except ShellCmdException as e:
            self.fail("Error compiling python files: %s" % (e))
        except Exception as e:
            self.fail("Unknown error: %s" % e)


class TestPySystemStart(unittest.TestCase):
    ''' Attempts to start Toaster, verify that it is succesfull, and stop it '''
    def setUp(self):
        run_shell_cmd("bash -c 'rm -f build/*log'")

    def test_start_interactive_mode(self):
        try:
            run_shell_cmd("bash -c 'source %s/oe-init-build-env && source toaster start webport=%d && source toaster stop'" % (config.testdir, config.TOASTER_PORT), config.testdir)
        except ShellCmdException as e:
            self.fail("Failed starting interactive mode: %s" % (e))

    def test_start_managed_mode(self):
        try:
            run_shell_cmd("%s/bitbake/bin/toaster webport=%d nobrowser & sleep 10 && curl http://localhost:%d/ && kill -2 %1" % (config.testdir, config.TOASTER_PORT, config.TOASTER_PORT), config.testdir)
            pass
        except ShellCmdException as e:
            self.fail("Failed starting managed mode: %s" % (e))

class TestHTML5Compliance(unittest.TestCase):
    def setUp(self):
        self.origdir = os.getcwd()
        self.crtdir = os.path.dirname(config.testdir)
        os.chdir(self.crtdir)
        if not os.path.exists(os.path.join(self.crtdir, "toaster.sqlite")):
            run_shell_cmd("%s/bitbake/lib/toaster/manage.py syncdb --noinput" % config.testdir)
            run_shell_cmd("%s/bitbake/lib/toaster/manage.py migrate orm" % config.testdir)
            run_shell_cmd("%s/bitbake/lib/toaster/manage.py migrate bldcontrol" % config.testdir)
            run_shell_cmd("%s/bitbake/lib/toaster/manage.py loadconf %s/meta-yocto/conf/toasterconf.json" % (config.testdir, config.testdir))

            setup = pexpect.spawn("%s/bitbake/lib/toaster/manage.py checksettings" % config.testdir)
            setup.logfile = sys.stdout
            setup.expect(r".*or type the full path to a different directory: ")
            setup.sendline('')
            setup.sendline('')
            setup.expect(r".*or type the full path to a different directory: ")
            setup.sendline('')
            setup.expect(r"Enter your option: ")
            setup.sendline('0')

        self.child = pexpect.spawn("%s/bitbake/bin/toaster webport=%d nobrowser" % (config.testdir, config.TOASTER_PORT))
        self.child.logfile=sys.stdout
        self.child.expect("Toaster is now running. You can stop it with Ctrl-C")

    def test_html5_compliance(self):
        import urllist, urlcheck
        results = {}
        for url in urllist.URLS:
            results[url] = urlcheck.validate_html5(config.TOASTER_BASEURL + url)

        failed = []
        for url in results:
            if results[url][1] != 0:
                failed.append((url, results[url]))


        self.assertTrue(len(failed)== 0, "Not all URLs validate: \n%s " % "\n".join(map(lambda x: "".join(str(x)),failed)))

        #(config.TOASTER_BASEURL + url, status, errors, warnings))

    def tearDown(self):
        while self.child.isalive():
            self.child.kill(signal.SIGINT)
            time.sleep(1)
        os.chdir(self.origdir)
#        if os.path.exists(os.path.join(self.crtdir, "toaster.sqlite")):
#            os.remove(os.path.join(self.crtdir, "toaster.sqlite"))
