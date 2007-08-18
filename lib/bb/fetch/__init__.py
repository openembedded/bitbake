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

import os, re, fcntl
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
urldata_cache = {}

def fetcher_init(d):
    """
    Called to initilize the fetchers once the configuration data is known
    Calls before this must not hit the cache.
    """
    pd = persist_data.PersistData(d)
    # When to drop SCM head revisions controled by user policy
    srcrev_policy = bb.data.getVar('BB_SRCREV_POLICY', d, 1) or "clear"
    if srcrev_policy == "cache":
        bb.msg.debug(1, bb.msg.domain.Fetcher, "Keeping SRCREV cache due to cache policy of: %s" % srcrev_policy)
    elif srcrev_policy == "clear":
        bb.msg.debug(1, bb.msg.domain.Fetcher, "Clearing SRCREV cache due to cache policy of: %s" % srcrev_policy)
        pd.delDomain("BB_URI_HEADREVS")
    else:
        bb.msg.fatal(bb.msg.domain.Fetcher, "Invalid SRCREV cache policy of: %s" % srcrev_policy)
    # Make sure our domains exist
    pd.addDomain("BB_URI_HEADREVS")
    pd.addDomain("BB_URI_LOCALCOUNT")

# Function call order is usually:
#   1. init
#   2. go
#   3. localpaths
# localpath can be called at any time

def init(urls, d, setup = True):
    urldata = {}
    fn = bb.data.getVar('FILE', d, 1)
    if fn in urldata_cache:
        urldata = urldata_cache[fn]

    for url in urls:
        if url not in urldata:
            urldata[url] = FetchData(url, d)

    if setup:
        for url in urldata:
            if not urldata[url].setup:
                urldata[url].setup_localpath(d) 

    urldata_cache[fn] = urldata
    return urldata

def go(d):
    """
    Fetch all urls
    init must have previously been called
    """
    urldata = init([], d, True)

    for u in urldata:
        ud = urldata[u]
        m = ud.method
        if ud.localfile:
            if not m.forcefetch(u, ud, d) and os.path.exists(ud.md5):
                # File already present along with md5 stamp file
                # Touch md5 file to show activity
                os.utime(ud.md5, None)
                continue
            lf = open(ud.lockfile, "a+")
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            if not m.forcefetch(u, ud, d) and os.path.exists(ud.md5):
                # If someone else fetched this before we got the lock, 
                # notice and don't try again
                os.utime(ud.md5, None)
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                lf.close
                continue
        m.go(u, ud, d)
        if ud.localfile:
            if not m.forcefetch(u, ud, d):
                Fetch.write_md5sum(u, ud, d)
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            lf.close

def localpaths(d):
    """
    Return a list of the local filenames, assuming successful fetch
    """
    local = []
    urldata = init([], d, True)

    for u in urldata:
        ud = urldata[u]      
        local.append(ud.localpath)

    return local

def get_srcrev(d):
    """
    Return the version string for the current package
    (usually to be used as PV)
    Most packages usually only have one SCM so we just pass on the call.
    In the multi SCM case, we build a value based on SRCREV_FORMAT which must 
    have been set.
    """
    scms = []
    # Only call setup_localpath on URIs which suppports_srcrev() 
    urldata = init(bb.data.getVar('SRC_URI', d, 1).split(), d, False)
    for u in urldata:
        ud = urldata[u]
        if ud.method.suppports_srcrev():
            if not ud.setup:
                ud.setup_localpath(d)
            scms.append(u)

    if len(scms) == 0:
        bb.msg.error(bb.msg.domain.Fetcher, "SRCREV was used yet no valid SCM was found in SRC_URI")
        raise ParameterError

    if len(scms) == 1:
        return urldata[scms[0]].method.sortable_revision(scms[0], urldata[scms[0]], d)

    #
    # Mutiple SCMs are in SRC_URI so we resort to SRCREV_FORMAT
    #
    format = bb.data.getVar('SRCREV_FORMAT', d, 1)
    if not format:
        bb.msg.error(bb.msg.domain.Fetcher, "The SRCREV_FORMAT variable must be set when multiple SCMs are used.")
        raise ParameterError

    for scm in scms:
        if 'name' in urldata[scm].parm:
            name = urldata[scm].parm["name"]
            rev = urldata[scm].method.sortable_revision(scm, urldata[scm], d)
            format = format.replace(name, rev)

    return format

def localpath(url, d, cache = True):
    """
    Called from the parser with cache=False since the cache isn't ready 
    at this point. Also called from classed in OE e.g. patch.bbclass
    """
    ud = init([url], d)
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
            print line,
        output += line

    status =  stdout_handle.close() or 0
    signal = status >> 8
    exitstatus = status & 0xff

    if signal:
        raise FetchError("Fetch command %s failed with signal %s, output:\n%s" % (pathcmd, signal, output))
    elif status != 0:
        raise FetchError("Fetch command %s failed with exit code %s, output:\n%s" % (pathcmd, status, output))

    return output

class FetchData(object):
    """
    A class which represents the fetcher state for a given URI.
    """
    def __init__(self, url, d):
        self.localfile = ""
        (self.type, self.host, self.path, self.user, self.pswd, self.parm) = bb.decodeurl(data.expand(url, d))
        self.date = Fetch.getSRCDate(self, d)
        self.url = url
        self.setup = False
        for m in methods:
            if m.supports(url, self, d):
                self.method = m
                break

    def setup_localpath(self, d):
        self.setup = True
        if "localpath" in self.parm:
            self.localpath = self.parm["localpath"]
        else:
            self.localpath = self.method.localpath(self.url, self, d)
        self.md5 = self.localpath + '.md5'
        self.lockfile = self.localpath + '.lock'
        # if user sets localpath for file, use it instead.


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

    def suppports_srcrev(self):
        """
        The fetcher supports auto source revisions (SRCREV)
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
            return data.getVar("SRCDATE_%s" % pn, d, 1) or data.getVar("CVSDATE_%s" % pn, d, 1) or data.getVar("SRCDATE", d, 1) or data.getVar("CVSDATE", d, 1) or data.getVar("DATE", d, 1)

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

    def latest_revision(self, url, ud, d):
        """
        Look in the cache for the latest revision, if not present ask the SCM.
        """
        if not hasattr(self, "_latest_revision"):
            raise ParameterError

        pd = persist_data.PersistData(d)
        key = self._revision_key(url, ud, d)
        rev = pd.getValue("BB_URI_HEADREVS", key)
        if rev != None:
            return str(rev)

        rev = self._latest_revision(url, ud, d)
        pd.setValue("BB_URI_HEADREVS", key, rev)
        return rev

    def sortable_revision(self, url, ud, d):
        """
        
        """
        if hasattr(self, "_sortable_revision"):
            return self._sortable_revision(url, ud, d)

        pd = persist_data.PersistData(d)
        key = self._revision_key(url, ud, d)
        latest_rev = self.latest_revision(url, ud, d)
        last_rev = pd.getValue("BB_URI_LOCALCOUNT", key + "_rev")
        count = pd.getValue("BB_URI_LOCALCOUNT", key + "_count")

        if last_rev == latest_rev:
            return str(count + "+" + latest_rev)

        if count is None:
            count = "0"
        else:
            count = str(int(count) + 1)

        pd.setValue("BB_URI_LOCALCOUNT", key + "_rev", latest_rev)
        pd.setValue("BB_URI_LOCALCOUNT", key + "_count", count)

        return str(count + "+" + latest_rev)


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
