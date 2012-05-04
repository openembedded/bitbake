#
# BitBake Tests for utils.py
#
# Copyright (C) 2012 Richard Purdie
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
import bb

class VerCmpString(unittest.TestCase):

    def test_vercmpstring(self):
        result = bb.utils.vercmp_string('1', '2')
        self.assertTrue(result < 0)
        result = bb.utils.vercmp_string('2', '1')
        self.assertTrue(result > 0)
        result = bb.utils.vercmp_string('1', '1.0')
        self.assertTrue(result < 0)
        result = bb.utils.vercmp_string('1', '1.1')
        self.assertTrue(result < 0)
        result = bb.utils.vercmp_string('1.1', '1_p2')
        self.assertTrue(result < 0)

