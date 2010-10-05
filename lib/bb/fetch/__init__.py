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

class MalformedUrl(Exception):
    """Exception raised when encountering an invalid url"""

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

class InvalidSRCREV(Exception):
    """Exception raised when an invalid SRCREV is encountered"""

def decodeurl(url):
    """Decodes an URL into the tokens (scheme, network location, path,
    user, password, parameters).

    >>> decodeurl("http://www.google.com/index.html")
    ('http', 'www.google.com', '/index.html', '', '', {})

    CVS url with username, host and cvsroot. The cvs module to check out is in the
    parameters:

    >>> decodeurl("cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg")
    ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', '', {'module': 'familiar/dist/ipkg'})

    Dito, but this time the username has a password part. And we also request a special tag
    to check out.

    >>> decodeurl("cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;module=familiar/dist/ipkg;tag=V0-99-81")
    ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'})
    """

    m = re.compile('(?P<type>[^:]*)://((?P<user>.+)@)?(?P<location>[^;]+)(;(?P<parm>.*))?').match(url)
    if not m:
        raise MalformedUrl(url)

    type = m.group('type')
    location = m.group('location')
    if not location:
        raise MalformedUrl(url)
    user = m.group('user')
    parm = m.group('parm')

    locidx = location.find('/')
    if locidx != -1:
        host = location[:locidx]
        path = location[locidx:]
    else:
        host = ""
        path = location
    if user:
        m = re.compile('(?P<user>[^:]+)(:?(?P<pswd>.*))').match(user)
        if m:
            user = m.group('user')
            pswd = m.group('pswd')
    else:
        user = ''
        pswd = ''

    p = {}
    if parm:
        for s in parm.split(';'):
            s1,s2 = s.split('=')
            p[s1] = s2

    return (type, host, path, user, pswd, p)

def encodeurl(decoded):
    """Encodes a URL from tokens (scheme, network location, path,
    user, password, parameters).

    >>> encodeurl(['http', 'www.google.com', '/index.html', '', '', {}])
    'http://www.google.com/index.html'

    CVS with username, host and cvsroot. The cvs module to check out is in the
    parameters:

    >>> encodeurl(['cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', '', {'module': 'familiar/dist/ipkg'}])
    'cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg'

    Dito, but this time the username has a password part. And we also request a special tag
    to check out.

    >>> encodeurl(['cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'}])
    'cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;tag=V0-99-81;module=familiar/dist/ipkg'
    """

    (type, host, path, user, pswd, p) = decoded

    if not type or not path:
        bb.msg.fatal(bb.msg.domain.Fetcher, "invalid or missing parameters for url encoding")
    url = '%s://' % type
    if user:
        url += "%s" % user
        if pswd:
            url += ":%s" % pswd
        url += "@"
    if host:
        url += "%s" % host
    url += "%s" % path
    if p:
        for parm in p:
            url += ";%s=%s" % (parm, p[parm])

    return url

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
#               for j in i:
#                   FIXME: apply replacements against options
    return bb.encodeurl(result_decoded)

methods = []
urldata_cache = {}
saved_headrevs = {}

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
        try:
            bb.fetch.saved_headrevs = pd.getKeyValues("BB_URI_HEADREVS")
        except:
            pass
        pd.delDomain("BB_URI_HEADREVS")
    else:
        bb.msg.fatal(bb.msg.domain.Fetcher, "Invalid SRCREV cache policy of: %s" % srcrev_policy)

    for m in methods:
        if hasattr(m, "init"):
            m.init(d)

    # Make sure our domains exist
    pd.addDomain("BB_URI_HEADREVS")
    pd.addDomain("BB_URI_LOCALCOUNT")

def fetcher_compare_revisons(d):
    """
    Compare the revisions in the persistant cache with current values and
    return true/false on whether they've changed.
    """

    pd = persist_data.PersistData(d)
    data = pd.getKeyValues("BB_URI_HEADREVS")
    data2 = bb.fetch.saved_headrevs

    changed = False
    for key in data:
        if key not in data2 or data2[key] != data[key]:
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s changed" % key)
            changed = True
            return True
        else:
            bb.msg.debug(2, bb.msg.domain.Fetcher, "%s did not change" % key)
    return False

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

def go(d, urls = None):
    """
    Fetch all urls
    init must have previously been called
    """
    if not urls:
        urls = d.getVar("SRC_URI", 1).split()
    urldata = init(urls, d, True)

    for u in urls:
        ud = urldata[u]
        m = ud.method
        if ud.localfile:
            if not m.forcefetch(u, ud, d) and os.path.exists(ud.md5):
                # File already present along with md5 stamp file
                # Touch md5 file to show activity
                try:
                    os.utime(ud.md5, None)
                except:
                    # Errors aren't fatal here
                    pass
                continue
            lf = bb.utils.lockfile(ud.lockfile)
            if not m.forcefetch(u, ud, d) and os.path.exists(ud.md5):
                # If someone else fetched this before we got the lock, 
                # notice and don't try again
                try:
                    os.utime(ud.md5, None)
                except:
                    # Errors aren't fatal here
                    pass
                bb.utils.unlockfile(lf)
                continue

        # First try fetching uri, u, from PREMIRRORS
        mirrors = [ i.split() for i in (bb.data.getVar('PREMIRRORS', d, 1) or "").split('\n') if i ]
        localpath = try_mirrors(d, u, mirrors)
        if not localpath:
            # Next try fetching from the original uri, u
            try:
                m.go(u, ud, d)
                localpath = ud.localpath
            except FetchError:
                # Finally, try fetching uri, u, from MIRRORS
                mirrors = [ i.split() for i in (bb.data.getVar('MIRRORS', d, 1) or "").split('\n') if i ]
                localpath = try_mirrors (d, u, mirrors)
                if not localpath or not os.path.exists(localpath):
                    raise FetchError("Unable to fetch URL %s from any source." % u)

        if localpath:
            ud.localpath = localpath

        if ud.localfile:
            if not m.forcefetch(u, ud, d):
                Fetch.write_md5sum(u, ud, d)
            bb.utils.unlockfile(lf)


def checkstatus(d):
    """
    Check all urls exist upstream
    init must have previously been called
    """
    urldata = init([], d, True)

    for u in urldata:
        ud = urldata[u]
        m = ud.method
        bb.msg.note(1, bb.msg.domain.Fetcher, "Testing URL %s" % u)
        # First try checking uri, u, from PREMIRRORS
        mirrors = [ i.split() for i in (bb.data.getVar('PREMIRRORS', d, 1) or "").split('\n') if i ]
        ret = try_mirrors(d, u, mirrors, True)
        if not ret:
            # Next try checking from the original uri, u
            try:
                ret = m.checkstatus(u, ud, d)
            except:
                # Finally, try checking uri, u, from MIRRORS
                mirrors = [ i.split() for i in (bb.data.getVar('MIRRORS', d, 1) or "").split('\n') if i ]
                ret = try_mirrors (d, u, mirrors, True)

        if not ret:
            bb.msg.fatal(bb.msg.domain.Fetcher, "URL %s doesn't work" % u)

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

srcrev_internal_call = False

def get_srcrev(d):
    """
    Return the version string for the current package
    (usually to be used as PV)
    Most packages usually only have one SCM so we just pass on the call.
    In the multi SCM case, we build a value based on SRCREV_FORMAT which must 
    have been set.
    """

    #
    # Ugly code alert. localpath in the fetchers will try to evaluate SRCREV which 
    # could translate into a call to here. If it does, we need to catch this
    # and provide some way so it knows get_srcrev is active instead of being
    # some number etc. hence the srcrev_internal_call tracking and the magic  
    # "SRCREVINACTION" return value.
    #
    # Neater solutions welcome!
    #
    if bb.fetch.srcrev_internal_call:
        return "SRCREVINACTION"

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

    bb.data.setVar('__BB_DONT_CACHE','1', d)

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

    # Need to export PATH as binary could be in metadata paths
    # rather than host provided
    # Also include some other variables.
    # FIXME: Should really include all export varaiables?
    exportvars = ['PATH', 'GIT_PROXY_COMMAND', 'GIT_PROXY_HOST', 'GIT_PROXY_PORT', 'GIT_CONFIG', 'http_proxy', 'ftp_proxy', 'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'HOME']

    for var in exportvars:
        val = data.getVar(var, d, True)
        if val:
            cmd = 'export ' + var + '=%s; %s' % (val, cmd)

    bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % cmd)

    # redirect stderr to stdout
    stdout_handle = os.popen(cmd + " 2>&1", "r")
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
        raise FetchError("Fetch command %s failed with signal %s, output:\n%s" % (cmd, signal, output))
    elif status != 0:
        raise FetchError("Fetch command %s failed with exit code %s, output:\n%s" % (cmd, status, output))

    return output

def try_mirrors(d, uri, mirrors, check = False):
    """
    Try to use a mirrored version of the sources.
    This method will be automatically called before the fetchers go.

    d Is a bb.data instance
    uri is the original uri we're trying to download
    mirrors is the list of mirrors we're going to try
    """
    fpath = os.path.join(data.getVar("DL_DIR", d, 1), os.path.basename(uri))
    if not check and os.access(fpath, os.R_OK):
        bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists, skipping checkout." % fpath)
        return fpath

    ld = d.createCopy()
    for (find, replace) in mirrors:
        newuri = uri_replace(uri, find, replace, ld)
        if newuri != uri:
            try:
                ud = FetchData(newuri, ld)
            except bb.fetch.NoMethodError:
                bb.msg.debug(1, bb.msg.domain.Fetcher, "No method for %s" % uri)
                continue

            ud.setup_localpath(ld)

            try:
                if check:
                    ud.method.checkstatus(newuri, ud, ld)
                else:
                    ud.method.go(newuri, ud, ld)
                return ud.localpath
            except (bb.fetch.MissingParameterError,
                    bb.fetch.FetchError,
                    bb.fetch.MD5SumError):
                import sys
                (type, value, traceback) = sys.exc_info()
                bb.msg.debug(2, bb.msg.domain.Fetcher, "Mirror fetch failure: %s" % value)
                continue
    return None


class FetchData(object):
    """
    A class which represents the fetcher state for a given URI.
    """
    def __init__(self, url, d):
        self.localfile = ""
        (self.type, self.host, self.path, self.user, self.pswd, self.parm) = bb.decodeurl(data.expand(url, d))
        self.date = Fetch.getSRCDate(self, d)
        self.url = url
        if not self.user and "user" in self.parm:
            self.user = self.parm["user"]
        if not self.pswd and "pswd" in self.parm:
            self.pswd = self.parm["pswd"]
        self.setup = False
        for m in methods:
            if m.supports(url, self, d):
                self.method = m
                return
        raise NoMethodError("Missing implementation for url %s" % url)

    def setup_localpath(self, d):
        self.setup = True
        if "localpath" in self.parm:
            # if user sets localpath for file, use it instead.
            self.localpath = self.parm["localpath"]
        else:
            premirrors = bb.data.getVar('PREMIRRORS', d, True)
            local = ""
            if premirrors and self.url:
                aurl = self.url.split(";")[0]
                mirrors = [ i.split() for i in (premirrors or "").split('\n') if i ]
                for (find, replace) in mirrors:
                    if replace.startswith("file://"):
                        path = aurl.split("://")[1]
                        path = path.split(";")[0]
                        local = replace.split("://")[1] + os.path.basename(path)
                        if local == aurl or not os.path.exists(local) or os.path.isdir(local):
                            local = ""
                self.localpath = local
            if not local:
                try:
                    bb.fetch.srcrev_internal_call = True
                    self.localpath = self.method.localpath(self.url, self, d)
                finally:
                    bb.fetch.srcrev_internal_call = False
                # We have to clear data's internal caches since the cached value of SRCREV is now wrong.
                # Horrible...
                bb.data.delVar("ISHOULDNEVEREXIST", d)

        # Note: These files should always be in DL_DIR whereas localpath may not be.
        basepath = bb.data.expand("${DL_DIR}/%s" % os.path.basename(self.localpath), d)
        self.md5 = basepath + '.md5'
        self.lockfile = basepath + '.lock'


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

    def checkstatus(self, url, urldata, d):
        """
        Check the status of a URL
        Assumes localpath was called first
        """
        bb.msg.note(1, bb.msg.domain.Fetcher, "URL %s could not be checked for status since no method exists." % url)
        return True

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

    def srcrev_internal_helper(ud, d):
        """
        Return:
            a) a source revision if specified
	    b) True if auto srcrev is in action
	    c) False otherwise
        """

        if 'rev' in ud.parm:
            return ud.parm['rev']

        if 'tag' in ud.parm:
            return ud.parm['tag']

        rev = None
        if 'name' in ud.parm:
            pn = data.getVar("PN", d, 1)
            rev = data.getVar("SRCREV_pn-" + pn + "_" + ud.parm['name'], d, 1)
        if not rev:
            rev = data.getVar("SRCREV", d, 1)
        if rev == "INVALID":
            raise InvalidSRCREV("Please set SRCREV to a valid value")
        if not rev:
            return False
        if rev is "SRCREVINACTION":
            return True
        return rev

    srcrev_internal_helper = staticmethod(srcrev_internal_helper)

    def localcount_internal_helper(ud, d):
        """
        Return:
            a) a locked localcount if specified
            b) None otherwise
        """

        localcount= None
        if 'name' in ud.parm:
            pn = data.getVar("PN", d, 1)
            localcount = data.getVar("LOCALCOUNT_" + ud.parm['name'], d, 1)
        if not localcount:
            localcount = data.getVar("LOCALCOUNT", d, 1)
        return localcount

    localcount_internal_helper = staticmethod(localcount_internal_helper)

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
        md5data = bb.utils.md5_file(ud.localpath)
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
        key = self.generate_revision_key(url, ud, d)
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
        key = self.generate_revision_key(url, ud, d)

        latest_rev = self._build_revision(url, ud, d)
        last_rev = pd.getValue("BB_URI_LOCALCOUNT", key + "_rev")
        uselocalcount = bb.data.getVar("BB_LOCALCOUNT_OVERRIDE", d, True) or False
        count = None
        if uselocalcount:
            count = Fetch.localcount_internal_helper(ud, d)
        if count is None:
            count = pd.getValue("BB_URI_LOCALCOUNT", key + "_count")

        if last_rev == latest_rev:
            return str(count + "+" + latest_rev)

        buildindex_provided = hasattr(self, "_sortable_buildindex")
        if buildindex_provided:
            count = self._sortable_buildindex(url, ud, d, latest_rev)

        if count is None:
            count = "0"
        elif uselocalcount or buildindex_provided:
            count = str(count)
        else:
            count = str(int(count) + 1)

        pd.setValue("BB_URI_LOCALCOUNT", key + "_rev", latest_rev)
        pd.setValue("BB_URI_LOCALCOUNT", key + "_count", count)

        return str(count + "+" + latest_rev)

    def generate_revision_key(self, url, ud, d):
        key = self._revision_key(url, ud, d)
        return "%s-%s" % (key, bb.data.getVar("PN", d, True) or "")

import cvs
import git
import local
import svn
import wget
import svk
import ssh
import perforce
import bzr
import hg
import osc
import repo

methods.append(local.Local())
methods.append(wget.Wget())
methods.append(svn.Svn())
methods.append(git.Git())
methods.append(cvs.Cvs())
methods.append(svk.Svk())
methods.append(ssh.SSH())
methods.append(perforce.Perforce())
methods.append(bzr.Bzr())
methods.append(hg.Hg())
methods.append(osc.Osc())
methods.append(repo.Repo())
