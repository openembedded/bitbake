#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

Classes for obtaining upstream sources for the
BitBake build tools.

Copyright (C) 2003, 2004  Chris Larson

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc., 59 Temple
Place, Suite 330, Boston, MA 02111-1307 USA. 

Based on functions from the base bb module, Copyright 2003 Holger Schurig
"""

import os, re
import bb
from   bb import data

class FetchError(Exception):
    """Exception raised when a download fails"""

class NoMethodError(Exception):
    """Exception raised when there is no method to obtain a supplied url or set of urls"""

class MissingParameterError(Exception):
    """Exception raised when a fetch method is missing a critical parameter in the url"""

class MD5SumError(Exception):
    """Exception raised when a MD5SUM of a file does not match the expected one"""

def uri_replace(uri, uri_find, uri_replace, d):
#   bb.note("uri_replace: operating on %s" % uri)
    if not uri or not uri_find or not uri_replace:
        bb.debug(1, "uri_replace: passed an undefined value, not replacing")
    uri_decoded = list(bb.decodeurl(uri))
    uri_find_decoded = list(bb.decodeurl(uri_find))
    uri_replace_decoded = list(bb.decodeurl(uri_replace))
    result_decoded = ['','','','','',{}]
    for i in uri_find_decoded:
        loc = uri_find_decoded.index(i)
        result_decoded[loc] = uri_decoded[loc]
        import types
        if type(i) == types.StringType:
            import re
            if (re.match(i, uri_decoded[loc])):
                result_decoded[loc] = re.sub(i, uri_replace_decoded[loc], uri_decoded[loc])
                if uri_find_decoded.index(i) == 2:
                    if d:
                        localfn = bb.fetch.localpath(uri, d)
                        if localfn:
                            result_decoded[loc] = os.path.dirname(result_decoded[loc]) + "/" + os.path.basename(bb.fetch.localpath(uri, d))
#                       bb.note("uri_replace: matching %s against %s and replacing with %s" % (i, uri_decoded[loc], uri_replace_decoded[loc]))
            else:
#               bb.note("uri_replace: no match")
                return uri
#           else:
#               for j in i.keys():
#                   FIXME: apply replacements against options
    return bb.encodeurl(result_decoded)

methods = []

def init(urls = [], d = None):
    if d == None:
        bb.debug(2,"BUG init called with None as data object!!!")
        return

    for m in methods:
        m.urls = []

    for u in urls:
        for m in methods:
            m.data = d
            if m.supports(u, d):
                m.urls.append(u)

def go(d):
    """Fetch all urls"""
    for m in methods:
        if m.urls:
            m.go(d)

def localpaths(d):
    """Return a list of the local filenames, assuming successful fetch"""
    local = []
    for m in methods:
        for u in m.urls:
            local.append(m.localpath(u, d))
    return local

def localpath(url, d):
    for m in methods:
        if m.supports(url, d):
            return m.localpath(url, d)
    return url

class Fetch(object):
    """Base class for 'fetch'ing data"""

    def __init__(self, urls = []):
        self.urls = []
        for url in urls:
            if self.supports(bb.decodeurl(url), d) is 1:
                self.urls.append(url)

    def supports(url, d):
        """Check to see if this fetch class supports a given url.
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        return 0
    supports = staticmethod(supports)

    def localpath(url, d):
        """Return the local filename of a given url assuming a successful fetch.
        """
        return url
    localpath = staticmethod(localpath)

    def setUrls(self, urls):
        self.__urls = urls

    def getUrls(self):
        return self.__urls

    urls = property(getUrls, setUrls, None, "Urls property")

    def setData(self, data):
        self.__data = data

    def getData(self):
        return self.__data

    data = property(getData, setData, None, "Data property")

    def go(self, urls = []):
        """Fetch urls"""
        raise NoMethodError("Missing implementation for url")

    def getSRCDate(d):
        """
        Return the SRC Date for the component

        d the bb.data module
        """
        return data.getVar("SRCDATE", d, 1) or data.getVar("CVSDATE", d, 1) or data.getVar("DATE", d, 1 )
    getSRCDate = staticmethod(getSRCDate)

    def try_mirror(d, tarfn):
        """
        Try to use a mirrored version of the sources. We do this
        to avoid massive loads on foreign cvs and svn servers.
        This method will be used by the different fetcher
        implementations.

        d Is a bb.data instance
        tarfn is the name of the tarball
        """
        pn = data.getVar('PN', d, True)
        src_tarball_stash = None
        if pn:
            src_tarball_stash = (data.getVar('SRC_TARBALL_STASH_%s' % pn, d, True) or data.getVar('CVS_TARBALL_STASH_%s' % pn, d, True) or data.getVar('SRC_TARBALL_STASH', d, True) or data.getVar('CVS_TARBALL_STASH', d, True) or "").split()

        for stash in src_tarball_stash:
            fetchcmd = data.getVar("FETCHCOMMAND_mirror", d, True) or data.getVar("FETCHCOMMAND_wget", d, True)
            uri = stash + tarfn
            bb.note("fetch " + uri)
            fetchcmd = fetchcmd.replace("${URI}", uri)
            ret = os.system(fetchcmd)
            if ret == 0:
                bb.note("Fetched %s from tarball stash, skipping checkout" % tarfn)
                return True
        return False
    try_mirror = staticmethod(try_mirror)

    def check_for_tarball(d, tarfn, dldir, date):
        """
        Check for a local copy then check the tarball stash.
        Both checks are skipped if date == 'now'.

        d Is a bb.data instance
        tarfn is the name of the tarball
        date is the SRCDATE
        """
        if "now" != date:
            dl = os.path.join(dldir, tarfn)
            if os.access(dl, os.R_OK):
                bb.debug(1, "%s already exists, skipping checkout." % tarfn)
                return True

            # try to use the tarball stash
            if Fetch.try_mirror(d, tarfn):
                return True
        return False
    check_for_tarball = staticmethod(check_for_tarball)


import cvs
import git
import local
import svn
import wget
import svk

methods.append(cvs.Cvs())
methods.append(git.Git())
methods.append(local.Local())
methods.append(svn.Svn())
methods.append(wget.Wget())
methods.append(svk.Svk())
