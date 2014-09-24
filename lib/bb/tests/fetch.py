# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
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
from bb.fetch2 import URI
import bb

class URITest(unittest.TestCase):
    test_uris = {
        "http://www.google.com/index.html" : {
            'uri': 'http://www.google.com/index.html',
            'scheme': 'http',
            'hostname': 'www.google.com',
            'port': None,
            'hostport': 'www.google.com',
            'path': '/index.html',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': False
        },
        "http://www.google.com/index.html;param1=value1" : {
            'uri': 'http://www.google.com/index.html;param1=value1',
            'scheme': 'http',
            'hostname': 'www.google.com',
            'port': None,
            'hostport': 'www.google.com',
            'path': '/index.html',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {
                'param1': 'value1'
            },
            'query': {},
            'relative': False
        },
        "http://www.example.org/index.html?param1=value1" : {
            'uri': 'http://www.example.org/index.html?param1=value1',
            'scheme': 'http',
            'hostname': 'www.example.org',
            'port': None,
            'hostport': 'www.example.org',
            'path': '/index.html',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {
                'param1': 'value1'
            },
            'relative': False
        },
        "http://www.example.org/index.html?qparam1=qvalue1;param2=value2" : {
            'uri': 'http://www.example.org/index.html?qparam1=qvalue1;param2=value2',
            'scheme': 'http',
            'hostname': 'www.example.org',
            'port': None,
            'hostport': 'www.example.org',
            'path': '/index.html',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {
                'param2': 'value2'
            },
            'query': {
                'qparam1': 'qvalue1'
            },
            'relative': False
        },
        "http://www.example.com:8080/index.html" : {
            'uri': 'http://www.example.com:8080/index.html',
            'scheme': 'http',
            'hostname': 'www.example.com',
            'port': 8080,
            'hostport': 'www.example.com:8080',
            'path': '/index.html',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': False
        },
        "cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg" : {
            'uri': 'cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg',
            'scheme': 'cvs',
            'hostname': 'cvs.handhelds.org',
            'port': None,
            'hostport': 'cvs.handhelds.org',
            'path': '/cvs',
            'userinfo': 'anoncvs',
            'username': 'anoncvs',
            'password': '',
            'params': {
                'module': 'familiar/dist/ipkg'
            },
            'query': {},
            'relative': False
        },
        "cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;tag=V0-99-81;module=familiar/dist/ipkg": {
            'uri': 'cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;tag=V0-99-81;module=familiar/dist/ipkg',
            'scheme': 'cvs',
            'hostname': 'cvs.handhelds.org',
            'port': None,
            'hostport': 'cvs.handhelds.org',
            'path': '/cvs',
            'userinfo': 'anoncvs:anonymous',
            'username': 'anoncvs',
            'password': 'anonymous',
            'params': {
                'tag': 'V0-99-81',
                'module': 'familiar/dist/ipkg'
            },
            'query': {},
            'relative': False
        },
        "file://example.diff": { # NOTE: Not RFC compliant!
            'uri': 'file:example.diff',
            'scheme': 'file',
            'hostname': '',
            'port': None,
            'hostport': '',
            'path': 'example.diff',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': True
        },
        "file:example.diff": { # NOTE: RFC compliant version of the former
            'uri': 'file:example.diff',
            'scheme': 'file',
            'hostname': '',
            'port': None,
            'hostport': '',
            'path': 'example.diff',
            'userinfo': '',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': True
        },
        "file:///tmp/example.diff": {
            'uri': 'file:///tmp/example.diff',
            'scheme': 'file',
            'hostname': '',
            'port': None,
            'hostport': '',
            'path': '/tmp/example.diff',
            'userinfo': '',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': False
        },
        "git:///path/example.git": {
            'uri': 'git:///path/example.git',
            'scheme': 'git',
            'hostname': '',
            'port': None,
            'hostport': '',
            'path': '/path/example.git',
            'userinfo': '',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': False
        },
        "git:path/example.git": {
            'uri': 'git:path/example.git',
            'scheme': 'git',
            'hostname': '',
            'port': None,
            'hostport': '',
            'path': 'path/example.git',
            'userinfo': '',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': True
        },
        "git://example.net/path/example.git": {
            'uri': 'git://example.net/path/example.git',
            'scheme': 'git',
            'hostname': 'example.net',
            'port': None,
            'hostport': 'example.net',
            'path': '/path/example.git',
            'userinfo': '',
            'userinfo': '',
            'username': '',
            'password': '',
            'params': {},
            'query': {},
            'relative': False
        }
    }

    def test_uri(self):
        for test_uri, ref in self.test_uris.items():
            uri = URI(test_uri)

            self.assertEqual(str(uri), ref['uri'])

            # expected attributes
            self.assertEqual(uri.scheme, ref['scheme'])

            self.assertEqual(uri.userinfo, ref['userinfo'])
            self.assertEqual(uri.username, ref['username'])
            self.assertEqual(uri.password, ref['password'])

            self.assertEqual(uri.hostname, ref['hostname'])
            self.assertEqual(uri.port, ref['port'])
            self.assertEqual(uri.hostport, ref['hostport'])

            self.assertEqual(uri.path, ref['path'])
            self.assertEqual(uri.params, ref['params'])

            self.assertEqual(uri.relative, ref['relative'])

    def test_dict(self):
        for test in self.test_uris.values():
            uri = URI()

            self.assertEqual(uri.scheme, '')
            self.assertEqual(uri.userinfo, '')
            self.assertEqual(uri.username, '')
            self.assertEqual(uri.password, '')
            self.assertEqual(uri.hostname, '')
            self.assertEqual(uri.port, None)
            self.assertEqual(uri.path, '')
            self.assertEqual(uri.params, {})


            uri.scheme = test['scheme']
            self.assertEqual(uri.scheme, test['scheme'])

            uri.userinfo = test['userinfo']
            self.assertEqual(uri.userinfo, test['userinfo'])
            self.assertEqual(uri.username, test['username'])
            self.assertEqual(uri.password, test['password'])

            # make sure changing the values doesn't do anything unexpected
            uri.username = 'changeme'
            self.assertEqual(uri.username, 'changeme')
            self.assertEqual(uri.password, test['password'])
            uri.password = 'insecure'
            self.assertEqual(uri.username, 'changeme')
            self.assertEqual(uri.password, 'insecure')

            # reset back after our trickery
            uri.userinfo = test['userinfo']
            self.assertEqual(uri.userinfo, test['userinfo'])
            self.assertEqual(uri.username, test['username'])
            self.assertEqual(uri.password, test['password'])

            uri.hostname = test['hostname']
            self.assertEqual(uri.hostname, test['hostname'])
            self.assertEqual(uri.hostport, test['hostname'])

            uri.port = test['port']
            self.assertEqual(uri.port, test['port'])
            self.assertEqual(uri.hostport, test['hostport'])

            uri.path = test['path']
            self.assertEqual(uri.path, test['path'])

            uri.params = test['params']
            self.assertEqual(uri.params, test['params'])

            uri.query = test['query']
            self.assertEqual(uri.query, test['query'])

            self.assertEqual(str(uri), test['uri'])

            uri.params = {}
            self.assertEqual(uri.params, {})
            self.assertEqual(str(uri), (str(uri).split(";"))[0])

class FetcherTest(unittest.TestCase):

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

class MirrorUriTest(FetcherTest):

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
            : "file:///somepath/downloads/subversion-1.7.1.tar.bz2",
        ("git://git.invalid.infradead.org/mtd-utils.git;tag=1234567890123456789012345678901234567890", "git://.*/.*", "git://somewhere.org/somedir/BASENAME;protocol=http") 
            : "git://somewhere.org/somedir/mtd-utils.git;tag=1234567890123456789012345678901234567890;protocol=http", 
        ("git://git.invalid.infradead.org/foo/mtd-utils.git;tag=1234567890123456789012345678901234567890", "git://.*/.*", "git://somewhere.org/somedir/BASENAME;protocol=http") 
            : "git://somewhere.org/somedir/mtd-utils.git;tag=1234567890123456789012345678901234567890;protocol=http", 
        ("git://git.invalid.infradead.org/foo/mtd-utils.git;tag=1234567890123456789012345678901234567890", "git://.*/.*", "git://somewhere.org/somedir/MIRRORNAME;protocol=http") 
            : "git://somewhere.org/somedir/git.invalid.infradead.org.foo.mtd-utils.git;tag=1234567890123456789012345678901234567890;protocol=http", 

        #Renaming files doesn't work
        #("http://somewhere.org/somedir1/somefile_1.2.3.tar.gz", "http://somewhere.org/somedir1/somefile_1.2.3.tar.gz", "http://somewhere2.org/somedir3/somefile_2.3.4.tar.gz") : "http://somewhere2.org/somedir3/somefile_2.3.4.tar.gz"
        #("file://sstate-xyz.tgz", "file://.*/.*", "file:///somewhere/1234/sstate-cache") : "file:///somewhere/1234/sstate-cache/sstate-xyz.tgz",
    }

    mirrorvar = "http://.*/.* file:///somepath/downloads/ \n" \
                "git://someserver.org/bitbake git://git.openembedded.org/bitbake \n" \
                "https://.*/.* file:///someotherpath/downloads/ \n" \
                "http://.*/.* file:///someotherpath/downloads/ \n"

    def test_urireplace(self):
        for k, v in self.replaceuris.items():
            ud = bb.fetch.FetchData(k[0], self.d)
            ud.setup_localpath(self.d)
            mirrors = bb.fetch2.mirror_from_string("%s %s" % (k[1], k[2]))
            newuris, uds = bb.fetch2.build_mirroruris(ud, mirrors, self.d)
            self.assertEqual([v], newuris)

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


class FetcherLocalTest(FetcherTest):
    def setUp(self):
        def touch(fn):
            with file(fn, 'a'):
                os.utime(fn, None)

        super(FetcherLocalTest, self).setUp()
        self.localsrcdir = os.path.join(self.tempdir, 'localsrc')
        os.makedirs(self.localsrcdir)
        touch(os.path.join(self.localsrcdir, 'a'))
        touch(os.path.join(self.localsrcdir, 'b'))
        os.makedirs(os.path.join(self.localsrcdir, 'dir'))
        touch(os.path.join(self.localsrcdir, 'dir', 'c'))
        touch(os.path.join(self.localsrcdir, 'dir', 'd'))
        os.makedirs(os.path.join(self.localsrcdir, 'dir', 'subdir'))
        touch(os.path.join(self.localsrcdir, 'dir', 'subdir', 'e'))
        self.d.setVar("FILESPATH", self.localsrcdir)

    def fetchUnpack(self, uris):
        fetcher = bb.fetch.Fetch(uris, self.d)
        fetcher.download()
        fetcher.unpack(self.unpackdir)
        flst = []
        for root, dirs, files in os.walk(self.unpackdir):
            for f in files:
                flst.append(os.path.relpath(os.path.join(root, f), self.unpackdir))
        flst.sort()
        return flst

    def test_local(self):
        tree = self.fetchUnpack(['file://a', 'file://dir/c'])
        self.assertEqual(tree, ['a', 'dir/c'])

    def test_local_wildcard(self):
        tree = self.fetchUnpack(['file://a', 'file://dir/*'])
        # FIXME: this is broken - it should return ['a', 'dir/c', 'dir/d', 'dir/subdir/e']
        # see https://bugzilla.yoctoproject.org/show_bug.cgi?id=6128
        self.assertEqual(tree, ['a', 'b', 'dir/c', 'dir/d', 'dir/subdir/e'])

    def test_local_dir(self):
        tree = self.fetchUnpack(['file://a', 'file://dir'])
        self.assertEqual(tree, ['a', 'dir/c', 'dir/d', 'dir/subdir/e'])

    def test_local_subdir(self):
        tree = self.fetchUnpack(['file://dir/subdir'])
        # FIXME: this is broken - it should return ['dir/subdir/e']
        # see https://bugzilla.yoctoproject.org/show_bug.cgi?id=6129
        self.assertEqual(tree, ['subdir/e'])

    def test_local_subdir_file(self):
        tree = self.fetchUnpack(['file://dir/subdir/e'])
        self.assertEqual(tree, ['dir/subdir/e'])

    def test_local_subdirparam(self):
        tree = self.fetchUnpack(['file://a;subdir=bar'])
        self.assertEqual(tree, ['bar/a'])

    def test_local_deepsubdirparam(self):
        tree = self.fetchUnpack(['file://dir/subdir/e;subdir=bar'])
        self.assertEqual(tree, ['bar/dir/subdir/e'])

class FetcherNetworkTest(FetcherTest):

    if os.environ.get("BB_SKIP_NETTESTS") == "yes":
        print("Unset BB_SKIP_NETTESTS to run network tests")
    else:
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
                revision = bb.process.run("git rev-parse HEAD", shell=True, cwd=self.unpackdir + "/git")[0].strip()
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

        def test_gitfetch_goodsrcrev(self):
            # SRCREV is set but matches rev= parameter
            url1 = url2 = "git://git.openembedded.org/bitbake;rev=270a05b0b4ba0959fe0624d2a4885d7b70426da5"
            self.gitfetcher(url1, url2)

        def test_gitfetch_badsrcrev(self):
            # SRCREV is set but does not match rev= parameter
            url1 = url2 = "git://git.openembedded.org/bitbake;rev=dead05b0b4ba0959fe0624d2a4885d7b70426da5"
            self.assertRaises(bb.fetch.FetchError, self.gitfetcher, url1, url2)

        def test_gitfetch_tagandrev(self):
            # SRCREV is set but does not match rev= parameter
            url1 = url2 = "git://git.openembedded.org/bitbake;rev=270a05b0b4ba0959fe0624d2a4885d7b70426da5;tag=270a05b0b4ba0959fe0624d2a4885d7b70426da5"
            self.assertRaises(bb.fetch.FetchError, self.gitfetcher, url1, url2)

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
            os.chdir(self.tempdir)
            bb.process.run("git clone %s %s 2> /dev/null" % (realurl, self.sourcedir), shell=True)
            self.d.setVar("PREMIRRORS", "%s git://%s;protocol=file \n" % (dummyurl, self.sourcedir))
            self.gitfetcher(dummyurl, dummyurl)

        def test_git_submodule(self):
            fetcher = bb.fetch.Fetch(["gitsm://git.yoctoproject.org/git-submodule-test;rev=f12e57f2edf0aa534cf1616fa983d165a92b0842"], self.d)
            fetcher.download()
            # Previous cwd has been deleted
            os.chdir(os.path.dirname(self.unpackdir))
            fetcher.unpack(self.unpackdir)

class URLHandle(unittest.TestCase):

    datatable = {
       "http://www.google.com/index.html" : ('http', 'www.google.com', '/index.html', '', '', {}),
       "cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg" : ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', '', {'module': 'familiar/dist/ipkg'}),
       "cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;tag=V0-99-81;module=familiar/dist/ipkg" : ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'}),
       "git://git.openembedded.org/bitbake;branch=@foo" : ('git', 'git.openembedded.org', '/bitbake', '', '', {'branch': '@foo'})
    }

    def test_decodeurl(self):
        for k, v in self.datatable.items():
            result = bb.fetch.decodeurl(k)
            self.assertEqual(result, v)

    def test_encodeurl(self):
        for k, v in self.datatable.items():
            result = bb.fetch.encodeurl(v)
            self.assertEqual(result, k)



