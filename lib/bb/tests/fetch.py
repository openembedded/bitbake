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
import subprocess
import os
import bb


class FetcherTest(unittest.TestCase):

    replaceuris = {
        ("git://git.invalid.infradead.org/mtd-utils.git;tag=1234567890123456789012345678901234567890", "git://.*/.*", "http://somewhere.org/somedir/") 
            : "http://somewhere.org/somedir/git2_git.invalid.infradead.org.mtd-utils.git.tar.gz",
        ("git://git.invalid.infradead.org/mtd-utils.git;tag=1234567890123456789012345678901234567890", "git://.*/([^/]+/)*([^/]*)", "git://somewhere.org/somedir/\\2;protocol=http") 
            : "git://somewhere.org/somedir/mtd-utils.git;tag=1234567890123456789012345678901234567890;protocol=http", 
        ("git://git.invalid.infradead.org/foo/mtd-utils.git;tag=1234567890123456789012345678901234567890", "git://.*/([^/]+/)*([^/]*)", "git://somewhere.org/somedir/\\2;protocol=http") 
            : "git://somewhere.org/somedir/mtd-utils.git;tag=1234567890123456789012345678901234567890;protocol=http", 
        ("git://git.invalid.infradead.org/foo/mtd-utils.git;tag=1234567890123456789012345678901234567890", "git://.*/([^/]+/)*([^/]*)", "git://somewhere.org/\\2;protocol=http") 
            : "git://somewhere.org/mtd-utils.git;tag=1234567890123456789012345678901234567890;protocol=http", 
        ("git://someserver.org/bitbake;tag=1234567890123456789012345678901234567890", "git://someserver.org/bitbake", "git://git.openembedded.org/bitbake")
            : "git://git.openembedded.org/bitbake;tag=1234567890123456789012345678901234567890",
        ("file://sstate-xyz.tgz", "file://.*", "file:///somewhere/1234/sstate-cache") 
            : "file:///somewhere/1234/sstate-cache/sstate-xyz.tgz",
        ("file://sstate-xyz.tgz", "file://.*", "file:///somewhere/1234/sstate-cache/") 
            : "file:///somewhere/1234/sstate-cache/sstate-xyz.tgz",
        ("http://somewhere.org/somedir1/somedir2/somefile_1.2.3.tar.gz", "http://.*/.*", "http://somewhere2.org/somedir3") 
            : "http://somewhere2.org/somedir3/somefile_1.2.3.tar.gz",
        ("http://somewhere.org/somedir1/somefile_1.2.3.tar.gz", "http://somewhere.org/somedir1/somefile_1.2.3.tar.gz", "http://somewhere2.org/somedir3/somefile_1.2.3.tar.gz") 
            : "http://somewhere2.org/somedir3/somefile_1.2.3.tar.gz",
        ("http://www.apache.org/dist/subversion/subversion-1.7.1.tar.bz2", "http://www.apache.org/dist", "http://archive.apache.org/dist")
            : "http://archive.apache.org/dist/subversion/subversion-1.7.1.tar.bz2",
        ("http://www.apache.org/dist/subversion/subversion-1.7.1.tar.bz2", "http://.*/.*", "file:///somepath/downloads/")
            : "file:///somepath/downloads/subversion-1.7.1.tar.bz2"
        #Renaming files doesn't work
        #("http://somewhere.org/somedir1/somefile_1.2.3.tar.gz", "http://somewhere.org/somedir1/somefile_1.2.3.tar.gz", "http://somewhere2.org/somedir3/somefile_2.3.4.tar.gz") : "http://somewhere2.org/somedir3/somefile_2.3.4.tar.gz"
        #("file://sstate-xyz.tgz", "file://.*/.*", "file:///somewhere/1234/sstate-cache") : "file:///somewhere/1234/sstate-cache/sstate-xyz.tgz",
    }

    mirrorvar = "http://.*/.* file:///somepath/downloads/ \n" \
                "git://someserver.org/bitbake git://git.openembedded.org/bitbake \n" \
                "https://.*/.* file:///someotherpath/downloads/ \n" \
                "http://.*/.* file:///someotherpath/downloads/ \n"

    def setUp(self):
        self.d = bb.data.init()
        self.tempdir = tempfile.mkdtemp()
        self.dldir = os.path.join(self.tempdir, "download")
        os.mkdir(self.dldir)
        self.d.setVar("DL_DIR", self.dldir)
        self.unpackdir = os.path.join(self.tempdir, "unpacked")
        os.mkdir(self.unpackdir)
        persistdir = os.path.join(self.tempdir, "persistdata")
        self.d.setVar("PERSISTENT_DIR", persistdir)

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

    def gitfetcher(self, url1, url2):
        def checkrevision(self, fetcher):
            fetcher.unpack(self.unpackdir)
            revision = subprocess.check_output("git rev-parse HEAD", shell=True, cwd=self.unpackdir + "/git").strip()
            self.assertEqual(revision, "270a05b0b4ba0959fe0624d2a4885d7b70426da5")

        self.d.setVar("BB_GENERATE_MIRROR_TARBALLS", "1")
        self.d.setVar("SRCREV", "270a05b0b4ba0959fe0624d2a4885d7b70426da5")
        fetcher = bb.fetch.Fetch([url1], self.d)
        fetcher.download()
        checkrevision(self, fetcher)
        # Wipe out the dldir clone and the unpacked source, turn off the network and check mirror tarball works
        bb.utils.prunedir(self.dldir + "/git2/")
        bb.utils.prunedir(self.unpackdir)
        self.d.setVar("BB_NO_NETWORK", "1")
        fetcher = bb.fetch.Fetch([url2], self.d)
        fetcher.download()
        checkrevision(self, fetcher)

    def test_gitfetch(self):
        url1 = url2 = "git://git.openembedded.org/bitbake"
        self.gitfetcher(url1, url2)

    def test_gitfetch_premirror(self):
        url1 = "git://git.openembedded.org/bitbake"
        url2 = "git://someserver.org/bitbake"
        self.d.setVar("PREMIRRORS", "git://someserver.org/bitbake git://git.openembedded.org/bitbake \n")
        self.gitfetcher(url1, url2)

    def test_gitfetch_premirror2(self):
        url1 = url2 = "git://someserver.org/bitbake"
        self.d.setVar("PREMIRRORS", "git://someserver.org/bitbake git://git.openembedded.org/bitbake \n")
        self.gitfetcher(url1, url2)

    def test_gitfetch_premirror3(self):
        realurl = "git://git.openembedded.org/bitbake"
        dummyurl = "git://someserver.org/bitbake"
        self.sourcedir = self.unpackdir.replace("unpacked", "sourcemirror.git")
        subprocess.check_output("git clone %s %s 2> /dev/null" % (realurl, self.sourcedir), shell=True)
        self.d.setVar("PREMIRRORS", "%s git://%s;protocol=file \n" % (dummyurl, self.sourcedir))
        self.gitfetcher(dummyurl, dummyurl)

    def test_urireplace(self):
        for k, v in self.replaceuris.items():
            ud = bb.fetch.FetchData(k[0], self.d)
            ud.setup_localpath(self.d)
            newuris = bb.fetch2.uri_replace(ud, k[1], k[2], self.d)
            self.assertEqual(newuris, v)

    def test_urilist1(self):
        fetcher = bb.fetch.FetchData("http://downloads.yoctoproject.org/releases/bitbake/bitbake-1.0.tar.gz", self.d)
        mirrors = bb.fetch2.mirror_from_string(self.mirrorvar)
        uris, uds = bb.fetch2.build_mirroruris(fetcher, mirrors, self.d)
        self.assertEqual(uris, ['file:///somepath/downloads/bitbake-1.0.tar.gz', 'file:///someotherpath/downloads/bitbake-1.0.tar.gz'])

    def test_urilist2(self):
        # Catch https:// -> files:// bug
        fetcher = bb.fetch.FetchData("https://downloads.yoctoproject.org/releases/bitbake/bitbake-1.0.tar.gz", self.d)
        mirrors = bb.fetch2.mirror_from_string(self.mirrorvar)
        uris, uds = bb.fetch2.build_mirroruris(fetcher, mirrors, self.d)
        self.assertEqual(uris, ['file:///someotherpath/downloads/bitbake-1.0.tar.gz'])


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



