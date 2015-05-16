# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Test for lib/bb/parse/
#
# Copyright (C) 2015 Richard Purdie
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
#

import unittest
import tempfile
import logging
import bb
import os

logger = logging.getLogger('BitBake.TestParse')

import bb.parse
import bb.data
import bb.siggen

class ParseTest(unittest.TestCase):

    testfile = """
A = "1"
B = "2"
do_install() {
	echo "hello"
}

C = "3"
"""

    def setUp(self):
        self.d = bb.data.init()
        bb.parse.siggen = bb.siggen.init(self.d)

    def parsehelper(self, content):

        f = tempfile.NamedTemporaryFile(suffix = ".bb")
        f.write(content)
        f.flush()
        os.chdir(os.path.dirname(f.name))
        return f

    def test_parse_simple(self):
        f = self.parsehelper(self.testfile)
        d = bb.parse.handle(f.name, self.d)['']
        self.assertEqual(d.getVar("A", True), "1")
        self.assertEqual(d.getVar("B", True), "2")
        self.assertEqual(d.getVar("C", True), "3")

    def test_parse_incomplete_function(self):
        testfileB = self.testfile.replace("}", "")
        f = self.parsehelper(testfileB)
        with self.assertRaises(bb.parse.ParseError):
            d = bb.parse.handle(f.name, self.d)['']
