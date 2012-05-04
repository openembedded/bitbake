#
# BitBake Tests for the Fetcher (fetch2/)
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
import tempfile
import os
import bb


class FetcherTest(unittest.TestCase):

    def setUp(self):
        self.d = bb.data.init()
        self.tempdir = tempfile.mkdtemp()
        self.dldir = os.path.join(self.tempdir, "download")
        os.mkdir(self.dldir)
        self.d.setVar("DL_DIR", self.dldir)
        self.unpackdir = os.path.join(self.tempdir, "unpacked")
        os.mkdir(self.unpackdir)

    def tearDown(self):
        bb.utils.prunedir(self.tempdir)

    def test_fetch(self):
        fetcher = bb.fetch.Fetch(["http://downloads.yoctoproject.org/releases/bitbake/bitbake-1.0.tar.gz", "http://downloads.yoctoproject.org/releases/bitbake/bitbake-1.1.tar.gz"], self.d)
        fetcher.download()
        self.assertEqual(os.path.getsize(self.dldir + "/bitbake-1.0.tar.gz"), 57749)
        self.assertEqual(os.path.getsize(self.dldir + "/bitbake-1.1.tar.gz"), 57892)
        self.d.setVar("BB_NO_NETWORK", "1")
        fetcher = bb.fetch.Fetch(["http://downloads.yoctoproject.org/releases/bitbake/bitbake-1.0.tar.gz", "http://downloads.yoctoproject.org/releases/bitbake/bitbake-1.1.tar.gz"], self.d)
        fetcher.download()
        fetcher.unpack(self.unpackdir)
        self.assertEqual(len(os.listdir(self.unpackdir + "/bitbake-1.0/")), 9)
        self.assertEqual(len(os.listdir(self.unpackdir + "/bitbake-1.1/")), 9)

    def test_fetch_mirror(self):
        self.d.setVar("MIRRORS", "http://.*/.* http://downloads.yoctoproject.org/releases/bitbake")
        fetcher = bb.fetch.Fetch(["http://invalid.yoctoproject.org/releases/bitbake/bitbake-1.0.tar.gz"], self.d)
        fetcher.download()
        self.assertEqual(os.path.getsize(self.dldir + "/bitbake-1.0.tar.gz"), 57749)

    def test_fetch_premirror(self):
        self.d.setVar("PREMIRRORS", "http://.*/.* http://downloads.yoctoproject.org/releases/bitbake")
        fetcher = bb.fetch.Fetch(["http://invalid.yoctoproject.org/releases/bitbake/bitbake-1.0.tar.gz"], self.d)
        fetcher.download()
        self.assertEqual(os.path.getsize(self.dldir + "/bitbake-1.0.tar.gz"), 57749)


class URLHandle(unittest.TestCase):

    datatable = {
       "http://www.google.com/index.html" : ('http', 'www.google.com', '/index.html', '', '', {}),
       "cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg" : ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', '', {'module': 'familiar/dist/ipkg'}),
       "cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;tag=V0-99-81;module=familiar/dist/ipkg" : ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'})
    }

    def test_decodeurl(self):
        for k, v in self.datatable.items():
            result = bb.fetch.decodeurl(k)
            self.assertEqual(result, v)

    def test_encodeurl(self):
        for k, v in self.datatable.items():
            result = bb.fetch.encodeurl(v)
            self.assertEqual(result, k)



