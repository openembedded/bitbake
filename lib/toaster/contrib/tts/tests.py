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
            run_shell_cmd("bash -c 'source %s/oe-init-build-env && source toaster start && source toaster stop'" % config.testdir, config.testdir)
        except ShellCmdException as e:
            self.fail("Failed starting interactive mode: %s" % (e))

    def test_start_managed_mode(self):
        try:
            run_shell_cmd("./poky/bitbake/bin/toaster webport=56789 & sleep 10 && curl http://localhost:56789/ && kill -2 %1")
            pass
        except ShellCmdException as e:
            self.fail("Failed starting managed mode: %s" % (e))

