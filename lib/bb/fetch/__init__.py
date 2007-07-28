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

import os, re
import bb
from   bb import data
from   bb import persist_data

try:
    import cPickle as pickle
except ImportError:
    import pickle

class FetchError(Exception):
    """Exception raised when a download fails"""

class NoMethodError(Exception):
    """Exception raised when there is no method to obtain a supplied url or set of urls"""

class MissingParameterError(Exception):
    """Exception raised when a fetch method is missing a critical parameter in the url"""

class ParameterError(Exception):
    """Exception raised when a url cannot be proccessed due to invalid parameters."""

class MD5SumError(Exception):
    """Exception raised when a MD5SUM of a file does not match the expected one"""

def uri_replace(uri, uri_find, uri_replace, d):
#   bb.msg.note(1, bb.msg.domain.Fetcher, "uri_replace: operating on %s" % uri)
    if not uri or not uri_find or not uri_replace:
        bb.msg.debug(1, bb.msg.domain.Fetcher, "uri_replace: passed an undefined value, not replacing")
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
#                       bb.msg.note(1, bb.msg.domain.Fetcher, "uri_replace: matching %s against %s and replacing with %s" % (i, uri_decoded[loc], uri_replace_decoded[loc]))
            else:
#               bb.msg.note(1, bb.msg.domain.Fetcher, "uri_replace: no match")
                return uri
#           else:
#               for j in i.keys():
#                   FIXME: apply replacements against options
    return bb.encodeurl(result_decoded)

methods = []

def fetcher_init(d):
    """
    Called to initilize the fetchers once the configuration data is known
    Calls before this must not hit the cache.
    """
    pd = persist_data.PersistData(d)
    # Clear any cached data
    pd.delDomain("BB_URLDATA")
    # Make sure our domain exists
    pd.addDomain("BB_URLDATA")

# Function call order is usually:
#   1. init
#   2. go
#   3. localpaths
# localpath can be called at any time

def init(urls, d, cache = True):
    urldata = {}

    if cache:
        urldata, pd, fn = getdata(d)

    for url in urls:
        if url not in urldata:
            ud = FetchData(url, d)
            for m in methods:
                if m.supports(url, ud, d):
                    ud.init(m, d)
                    break
            urldata[url] = ud

    if cache:
        pd.setValue("BB_URLDATA", fn, pickle.dumps(urldata, 0))

    return urldata

def getdata(d):
    urldata = {}
    fn = bb.data.getVar('FILE', d, 1)
    pd = persist_data.PersistData(d)
    encdata = pd.getValue("BB_URLDATA", fn)
    if encdata:
        urldata = pickle.loads(str(encdata))

    return urldata, pd, fn

def go(d, urldata = None):
    """
    Fetch all urls
    """
    if not urldata:
        urldata, pd, fn = getdata(d)

    for u in urldata:
        ud = urldata[u]
        m = ud.method
        if ud.localfile and not m.forcefetch(u, ud, d) and os.path.exists(ud.md5):
            # File already present along with md5 stamp file
            # Touch md5 file to show activity
            os.utime(ud.md5, None)
            continue
        # RP - is olddir needed?
        # olddir = os.path.abspath(os.getcwd())
        m.go(u, ud, d)
        # os.chdir(olddir)
        if ud.localfile and not m.forcefetch(u, ud, d):
            Fetch.write_md5sum(u, ud, d)

def localpaths(d, urldata = None):
    """
    Return a list of the local filenames, assuming successful fetch
    """
    local = []
    if not urldata:
        urldata, pd, fn = getdata(d)

    for u in urldata:
        ud = urldata[u]      
        local.append(ud.localpath)

    return local

def localpath(url, d, cache = True):
    """
    Called from the parser with cache=False since the cache isn't ready 
    at this point. Also called from classed in OE e.g. patch.bbclass
    """
    ud = init([url], d, cache)
    if ud[url].method:
        return ud[url].localpath
    return url

def runfetchcmd(cmd, d, quiet = False):
    """
    Run cmd returning the command output
    Raise an error if interrupted or cmd fails
    Optionally echo command output to stdout
    """
    bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % cmd)

    # Need to export PATH as binary could be in metadata paths
    # rather than host provided
    pathcmd = 'export PATH=%s; %s' % (data.expand('${PATH}', d), cmd)

    stdout_handle = os.popen(pathcmd, "r")
    output = ""

    while 1:
        line = stdout_handle.readline()
        if not line:
            break
        if not quiet:
            print line
        output += line

    status =  stdout_handle.close() or 0
    signal = status >> 8
    exitstatus = status & 0xff

    if signal:
        raise FetchError("Fetch command %s failed with signal %s, output:\n%s" % pathcmd, signal, output)
    elif status != 0:
        raise FetchError("Fetch command %s failed with exit code %s, output:\n%s" % pathcmd, status, output)

    return output

class FetchData(object):
    """Class for fetcher variable store"""
    def __init__(self, url, d):
        self.localfile = ""
        (self.type, self.host, self.path, self.user, self.pswd, self.parm) = bb.decodeurl(data.expand(url, d))
        self.date = Fetch.getSRCDate(self, d)
        self.url = url
        self.force = False

    def init(self, method, d):
        self.method = method
        self.localpath = method.localpath(self.url, self, d)
        self.md5 = self.localpath + '.md5'
        # if user sets localpath for file, use it instead.
        if "localpath" in self.parm:
            self.localpath = self.parm["localpath"]

class Fetch(object):
    """Base class for 'fetch'ing data"""

    def __init__(self, urls = []):
        self.urls = []

    def supports(self, url, urldata, d):
        """
        Check to see if this fetch class supports a given url.
        """
        return 0

    def localpath(self, url, urldata, d):
        """
        Return the local filename of a given url assuming a successful fetch.
        Can also setup variables in urldata for use in go (saving code duplication 
        and duplicate code execution)
        """
        return url

    def setUrls(self, urls):
        self.__urls = urls

    def getUrls(self):
        return self.__urls

    urls = property(getUrls, setUrls, None, "Urls property")

    def forcefetch(self, url, urldata, d):
        """
        Force a fetch, even if localpath exists?
        """
        return False

    def go(self, url, urldata, d):
        """
        Fetch urls
        Assumes localpath was called first
        """
        raise NoMethodError("Missing implementation for url")

    def getSRCDate(urldata, d):
        """
        Return the SRC Date for the component

        d the bb.data module
        """
        if "srcdate" in urldata.parm:
            return urldata.parm['srcdate']

        pn = data.getVar("PN", d, 1)

        if pn:
            return data.getVar("SRCDATE_%s" % pn, d, 1) or data.getVar("CVSDATE_%s" % pn, d, 1) or data.getVar("DATE", d, 1)

        return data.getVar("SRCDATE", d, 1) or data.getVar("CVSDATE", d, 1) or data.getVar("DATE", d, 1)
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
        tarpath = os.path.join(data.getVar("DL_DIR", d, 1), tarfn)
        if os.access(tarpath, os.R_OK):
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists, skipping checkout." % tarfn)
            return True

        pn = data.getVar('PN', d, True)
        src_tarball_stash = None
        if pn:
            src_tarball_stash = (data.getVar('SRC_TARBALL_STASH_%s' % pn, d, True) or data.getVar('CVS_TARBALL_STASH_%s' % pn, d, True) or data.getVar('SRC_TARBALL_STASH', d, True) or data.getVar('CVS_TARBALL_STASH', d, True) or "").split()

        for stash in src_tarball_stash:
            fetchcmd = data.getVar("FETCHCOMMAND_mirror", d, True) or data.getVar("FETCHCOMMAND_wget", d, True)
            uri = stash + tarfn
            bb.msg.note(1, bb.msg.domain.Fetcher, "fetch " + uri)
            fetchcmd = fetchcmd.replace("${URI}", uri)
            ret = os.system(fetchcmd)
            if ret == 0:
                bb.msg.note(1, bb.msg.domain.Fetcher, "Fetched %s from tarball stash, skipping checkout" % tarfn)
                return True
        return False
    try_mirror = staticmethod(try_mirror)

    def verify_md5sum(ud, got_sum):
        """
        Verify the md5sum we wanted with the one we got
        """
        wanted_sum = None
        if 'md5sum' in ud.parm:
            wanted_sum = ud.parm['md5sum']
        if not wanted_sum:
            return True

        return wanted_sum == got_sum
    verify_md5sum = staticmethod(verify_md5sum)

    def write_md5sum(url, ud, d):
        if bb.which(data.getVar('PATH', d), 'md5sum'):
            try:
                md5pipe = os.popen('md5sum ' + ud.localpath)
                md5data = (md5pipe.readline().split() or [ "" ])[0]
                md5pipe.close()
            except OSError:
                md5data = ""

        # verify the md5sum
        if not Fetch.verify_md5sum(ud, md5data):
            raise MD5SumError(url)

        md5out = file(ud.md5, 'w')
        md5out.write(md5data)
        md5out.close()
    write_md5sum = staticmethod(write_md5sum)

import cvs
import git
import local
import svn
import wget
import svk
import ssh
import perforce

methods.append(local.Local())
methods.append(wget.Wget())
methods.append(svn.Svn())
methods.append(git.Git())
methods.append(cvs.Cvs())
methods.append(svk.Svk())
methods.append(ssh.SSH())
methods.append(perforce.Perforce())
