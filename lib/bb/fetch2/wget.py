# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

Classes for obtaining upstream sources for the
BitBake build tools.

"""

# Copyright (C) 2003, 2004  Chris Larson
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
# Based on functions from the base bb module, Copyright 2003 Holger Schurig

import re
import tempfile
import subprocess
import os
import logging
import bb
import urllib
from   bb import data
from   bb.fetch2 import FetchMethod
from   bb.fetch2 import FetchError
from   bb.fetch2 import logger
from   bb.fetch2 import runfetchcmd
from   bs4 import BeautifulSoup

class Wget(FetchMethod):
    """Class to fetch urls via 'wget'"""
    def supports(self, ud, d):
        """
        Check to see if a given url can be fetched with wget.
        """
        return ud.type in ['http', 'https', 'ftp']

    def recommends_checksum(self, urldata):
        return True

    def urldata_init(self, ud, d):
        if 'protocol' in ud.parm:
            if ud.parm['protocol'] == 'git':
                raise bb.fetch2.ParameterError("Invalid protocol - if you wish to fetch from a git repository using http, you need to instead use the git:// prefix with protocol=http", ud.url)

        if 'downloadfilename' in ud.parm:
            ud.basename = ud.parm['downloadfilename']
        else:
            ud.basename = os.path.basename(ud.path)

        ud.localfile = data.expand(urllib.unquote(ud.basename), d)

        self.basecmd = d.getVar("FETCHCMD_wget", True) or "/usr/bin/env wget -t 2 -T 30 -nv --passive-ftp --no-check-certificate"

    def _runwget(self, ud, d, command, quiet):

        logger.debug(2, "Fetching %s using command '%s'" % (ud.url, command))
        bb.fetch2.check_network_access(d, command)
        runfetchcmd(command, d, quiet)

    def download(self, ud, d):
        """Fetch urls"""

        fetchcmd = self.basecmd

        if 'downloadfilename' in ud.parm:
            dldir = d.getVar("DL_DIR", True)
            bb.utils.mkdirhier(os.path.dirname(dldir + os.sep + ud.localfile))
            fetchcmd += " -O " + dldir + os.sep + ud.localfile

        uri = ud.url.split(";")[0]
        if os.path.exists(ud.localpath):
            # file exists, but we didnt complete it.. trying again..
            fetchcmd += d.expand(" -c -P ${DL_DIR} '%s'" % uri)
        else:
            fetchcmd += d.expand(" -P ${DL_DIR} '%s'" % uri)

        self._runwget(ud, d, fetchcmd, False)

        # Sanity check since wget can pretend it succeed when it didn't
        # Also, this used to happen if sourceforge sent us to the mirror page
        if not os.path.exists(ud.localpath):
            raise FetchError("The fetch command returned success for url %s but %s doesn't exist?!" % (uri, ud.localpath), uri)

        if os.path.getsize(ud.localpath) == 0:
            os.remove(ud.localpath)
            raise FetchError("The fetch of %s resulted in a zero size file?! Deleting and failing since this isn't right." % (uri), uri)

        return True

    def checkstatus(self, ud, d):

        uri = ud.url.split(";")[0]
        fetchcmd = self.basecmd + " --spider '%s'" % uri

        self._runwget(ud, d, fetchcmd, True)

        return True


    def _parse_path(self, regex, s):
        """
        Find and group name, version and archive type in the given string s
        """
        bb.debug(3, "parse_path(%s, %s)" % (regex.pattern, s))
        m = regex.search(s)
        if m:
            bb.debug(3, "%s, %s, %s" % (m.group('name'), m.group('ver'), m.group('type')))
            return (m.group('name'), m.group('ver'), m.group('type'))
        return None

    def _modelate_version(self, version):
        if version[0] in ['.', '-']:
            if version[1].isdigit():
                version = version[1] + version[0] + version[2:len(version)]
            else:
                version = version[1:len(version)]

        version = re.sub('\-', '.', version)
        version = re.sub('_', '.', version)
        version = re.sub('(rc)+', '.-1.', version)
        version = re.sub('(alpha)+', '.-3.', version)
        version = re.sub('(beta)+', '.-2.', version)
        if version[0] == 'v':
            version = version[1:len(version)]
        return version

    def _vercmp(self, old, new):
        """
        Check whether 'new' is newer than 'old' version. We use existing vercmp() for the
        purpose. PE is cleared in comparison as it's not for build, and PR is cleared too
        for simplicity as it's somehow difficult to get from various upstream format
        """

        (oldpn, oldpv, oldsuffix) = old
        (newpn, newpv, newsuffix) = new

        """
        Check for a new suffix type that we have never heard of before
        """
        if (newsuffix):
            m = self.suffixregex.search(newsuffix)
            if not m:
                bb.warn("%s has a possible unknown suffix: %s" % (newpn, newsuffix))
                return False

        """
        Not our package so ignore it
        """
        if oldpn != newpn:
            return False

        oldpv = self._modelate_version(oldpv)
        newpv = self._modelate_version(newpv)

        if bb.utils.vercmp(("0", oldpv, ""), ("0", newpv, "")) < 0:
            return True
        else:
            return False

    def _fetch_index(self, uri, ud, d):
        """
        Run fetch checkstatus to get directory information
        """
        f = tempfile.NamedTemporaryFile(dir="/tmp/s/", delete=False)

        agent = "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.12) Gecko/20101027 Ubuntu/9.10 (karmic) Firefox/3.6.12"
        fetchcmd = self.basecmd
        fetchcmd += " -O " + f.name + " --user-agent='" + agent + "' '" + uri + "'"
        try:
            self._runwget(ud, d, fetchcmd, True)
            fetchresult = f.read()
        except bb.fetch2.BBFetchException:
            fetchresult = ""

        f.close()
        # os.unlink(f.name)
        return fetchresult

    def _check_latest_dir(self, url, versionstring, ud, d):
        """
        Return the name of the directory with the greatest package version
        If error or no version, return ""
        """
        bb.debug(3, "DirURL: %s, %s" % (url, versionstring))
        soup = BeautifulSoup(self._fetch_index(url, ud, d))
        if not soup:
            return ""

        valid = 0
        prefix = ''
        regex = re.compile("(\D*)((\d+[\.\-_])+(\d+))")
        m = regex.search(versionstring)
        if m:
            version = ('', m.group(2), '')
            prefix = m.group(1)
            bb.debug(3, "version: %s, prefix: %s" % (version, prefix))
        else:
            version = ('', versionstring, '')

        for href in soup.find_all('a', href=True):
            bb.debug(3, "href: %s" % (href['href']))
            if href['href'].find(versionstring) >= 0:
                valid = 1
            m = regex.search(href['href'].strip("/"))
            if m:
                thisversion = ('', m.group(2), '')
                if thisversion and self._vercmp(version, thisversion) == True:
                    version = thisversion

        if valid:
            bb.debug(3, "Would return %s" % (prefix+version[1]))
            return prefix+version[1]
        else:
            bb.debug(3, "Not Valid")
            return ""

    def _check_latest_version(self, url, packagename, ud, d):
        """
        Return the latest version of a package inside a given directory path
        If error or no version, return ""
        """
        valid = 0
        version = self._parse_path(self.name_version_type_regex, packagename)

        bb.debug(3, "VersionURL: %s" % (url))
        soup = BeautifulSoup(self._fetch_index(url, ud, d))
        if not soup:
            bb.debug(3, "*** %s NO SOUP" % (packagename))
            return ""

        pn_regex = d.getVar('REGEX', True)
        if pn_regex:
            testversion = version
            pn_regex = re.compile(pn_regex)
            bb.debug(3, "pn_regex = '%s'" % (pn_regex.pattern))
            
        for line in soup.find_all('a', href=True):
            newver = ('', '', '')
            bb.debug(3, "line = '%s'" % (line['href']))
            if pn_regex:
                m = pn_regex.search(line['href'])
                if m:
                    bb.debug(3, "Name = '%s', Pver = '%s'" % (m.group('name'), m.group('pver')))
                    newver = (m.group('name'), m.group('pver'), '')
                else:
                    continue
            else:
                newver = self._parse_path(self.name_version_type_regex, line['href'])
            valid = 1
            if newver and self._vercmp(version, newver) == True:
                version = newver
                
        # check whether a valid package and version were found

        if not valid:
            version = ('', '', '')
        if not pn_regex:
            testversion = ('', '', '')
        bb.debug(3, "*** %s -> %s (TestVersion = %s)" % (packagename, version[1], testversion[1]))
        if valid and version:
            return re.sub('_', '.', version[1])

    def latest_versionstring(self, ud, d):
        """
        Manipulate the URL and try to obtain the latest package version

        sanity check to ensure same name and type. Match as many patterns as possible
        such as:
                gnome-common-2.20.0.tar.gz (most common format)
                gtk+-2.90.1.tar.gz
                xf86-input-synaptics-12.6.9.tar.gz
                dri2proto-2.3.tar.gz
                blktool_4.orig.tar.gz
                libid3tag-0.15.1b.tar.gz
                unzip552.tar.gz
                icu4c-3_6-src.tgz
                genext2fs_1.3.orig.tar.gz
                gst-fluendo-mp3
        """
        # match most patterns which uses "-" as separator to version digits
        pn_prefix1 = "[a-zA-Z][a-zA-Z0-9]*([\-_][a-zA-Z]\w+)*\+?[\-_]"
        # a loose pattern such as for unzip552.tar.gz
        pn_prefix2 = "[a-zA-Z]+"
        # a loose pattern such as for 80325-quicky-0.4.tar.gz
        pn_prefix3 = "[0-9]+[\-]?[a-zA-Z]+"
        # Save the Package Name (pn) Regex for use later
        self.pn_regex = "(%s|%s|%s)" % (pn_prefix1, pn_prefix2, pn_prefix3)

        # match version
        version_regex = "(([A-Z]*\d+[a-zA-Z]*[\.\-_]*)+)"

        # src.rpm extension was added only for rpm package. Can be removed if the rpm
        # packaged will always be considered as having to be manually upgraded
        suffixlist = "(tar\.gz|tgz|tar\.bz2|zip|xz|rpm|bz2|orig\.tar\.gz|tar\.xz|src\.tar\.gz|src\.tgz|svnr\d+\.tar\.bz2|stable\.tar\.gz|src\.rpm)"
        self.suffixregex = re.compile(suffixlist)

        # match name, version and archive type of a package
        self.name_version_type_regex = re.compile("(?P<name>%s?)\.?v?(?P<ver>%s)(\-source)?[\.\-](?P<type>%s$)" % (self.pn_regex, version_regex, suffixlist))

        regex_uri = d.getVar("REGEX_URI", True)
        newpath = ud.path
        pupver = ""

        # search for version matches on folders inside the path, like:
        # "5.7" in http://download.gnome.org/sources/${PN}/5.7/${PN}-${PV}.tar.gz
        m = re.search("(?P<dirver>[^/]*(\d+\.)*\d+([\-_]r\d+)*)/", ud.path)
        bb.debug(3, "path = %s" % (ud.path))
        bb.debug(3, "Regex: %s" % (self.name_version_type_regex.pattern))
        if m and not regex_uri:
            dirver = m.group('dirver')
            # generate the new uri after removing version directory name
            newuri = bb.fetch.encodeurl([ud.type, ud.host, ud.path.split(dirver)[0], ud.user, ud.pswd, {}])
            newversion = self._check_latest_dir(newuri, dirver, ud, d)
            if newversion and dirver != newversion:
                newpath = ud.path.replace(dirver, newversion, True)

        # try to acquire all remote files in current directory
        packagename = newpath.split("/")[-1]            # current package name
        newpath = newpath.split(packagename)[0] or "/"  # path to directory

        # generate the new uri with the appropriate latest directory
        newuri = regex_uri or bb.fetch.encodeurl([ud.type, ud.host, newpath, ud.user, ud.pswd, {}])
        newversion = self._check_latest_version(newuri, packagename, ud, d)
        while not newversion:
            # maybe it's hiding in a download directory so try there
            newuri = "/".join(newuri.split("/")[0:-2]) + "/download"
            if newuri == "/download" or newuri == "http://download":
                break
            newversion = self._check_latest_version(newuri, packagename, ud, d)

        return newversion

