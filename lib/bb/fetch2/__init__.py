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

from __future__ import absolute_import
from __future__ import print_function
import os, re
import logging
import bb
from   bb import data
from   bb import persist_data
from   bb import utils

__version__ = "2"

logger = logging.getLogger("BitBake.Fetch")

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
    if locidx != -1 and type.lower() != 'file':
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
            s1, s2 = s.split('=')
            p[s1] = s2

    return (type, host, path, user, pswd, p)

def encodeurl(decoded):
    """Encodes a URL from tokens (scheme, network location, path,
    user, password, parameters).
    """

    (type, host, path, user, pswd, p) = decoded

    if not type or not path:
        raise MissingParameterError("Type or path url components missing when encoding %s" % decoded)
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
    if not uri or not uri_find or not uri_replace:
        logger.debug(1, "uri_replace: passed an undefined value, not replacing")
    uri_decoded = list(decodeurl(uri))
    uri_find_decoded = list(decodeurl(uri_find))
    uri_replace_decoded = list(decodeurl(uri_replace))
    result_decoded = ['', '', '', '', '', {}]
    for i in uri_find_decoded:
        loc = uri_find_decoded.index(i)
        result_decoded[loc] = uri_decoded[loc]
        if isinstance(i, basestring):
            if (re.match(i, uri_decoded[loc])):
                result_decoded[loc] = re.sub(i, uri_replace_decoded[loc], uri_decoded[loc])
                if uri_find_decoded.index(i) == 2:
                    if d:
                        localfn = bb.fetch2.localpath(uri, d)
                        if localfn:
                            result_decoded[loc] = os.path.join(os.path.dirname(result_decoded[loc]), os.path.basename(bb.fetch2.localpath(uri, d)))
            else:
                return uri
    return encodeurl(result_decoded)

methods = []
urldata_cache = {}
saved_headrevs = {}

def fetcher_init(d):
    """
    Called to initialize the fetchers once the configuration data is known.
    Calls before this must not hit the cache.
    """
    pd = persist_data.persist(d)
    # When to drop SCM head revisions controlled by user policy
    srcrev_policy = bb.data.getVar('BB_SRCREV_POLICY', d, 1) or "clear"
    if srcrev_policy == "cache":
        logger.debug(1, "Keeping SRCREV cache due to cache policy of: %s", srcrev_policy)
    elif srcrev_policy == "clear":
        logger.debug(1, "Clearing SRCREV cache due to cache policy of: %s", srcrev_policy)
        try:
            bb.fetch2.saved_headrevs = pd['BB_URI_HEADREVS'].items()
        except:
            pass
        del pd['BB_URI_HEADREVS']
    else:
        raise FetchError("Invalid SRCREV cache policy of: %s" % srcrev_policy)

    for m in methods:
        if hasattr(m, "init"):
            m.init(d)

def fetcher_compare_revisions(d):
    """
    Compare the revisions in the persistant cache with current values and
    return true/false on whether they've changed.
    """

    pd = persist_data.persist(d)
    data = pd['BB_URI_HEADREVS'].items()
    data2 = bb.fetch2.saved_headrevs

    changed = False
    for key in data:
        if key not in data2 or data2[key] != data[key]:
            logger.debug(1, "%s changed", key)
            changed = True
            return True
        else:
            logger.debug(2, "%s did not change", key)
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

def mirror_from_string(data):
    return [ i.split() for i in (data or "").replace('\\n','\n').split('\n') if i ]

def verify_checksum(u, ud, d):
    """
    verify the MD5 and SHA256 checksum for downloaded src

    return value:
        - True: checksum matched
        - False: checksum unmatched

    if checksum is missing in recipes file, "BB_STRICT_CHECKSUM" decide the return value.
    if BB_STRICT_CHECKSUM = "1" then return false as unmatched, otherwise return true as
    matched
    """

    if not ud.type in ["http", "https", "ftp", "ftps"]:
        return

    md5data = bb.utils.md5_file(ud.localpath)
    sha256data = bb.utils.sha256_file(ud.localpath)

    if (ud.md5_expected == None or ud.sha256_expected == None):
        logger.warn('Missing SRC_URI checksum for %s, consider adding to the recipe:\n'
                    'SRC_URI[%s] = "%s"\nSRC_URI[%s] = "%s"',
                    ud.localpath, ud.md5_name, md5data,
                    ud.sha256_name, sha256data)
        if bb.data.getVar("BB_STRICT_CHECKSUM", d, True) == "1":
            raise FetchError("No checksum specified for %s." % u)
        return

    if (ud.md5_expected != md5data or ud.sha256_expected != sha256data):
        logger.error('The checksums for "%s" did not match.\n'
                     '  MD5: expected "%s", got "%s"\n'
                     '  SHA256: expected "%s", got "%s"\n',
                     ud.localpath, ud.md5_expected, md5data,
                     ud.sha256_expected, sha256data)
        raise FetchError("%s checksum mismatch." % u)

def subprocess_setup():
    import signal
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    # SIGPIPE errors are known issues with gzip/bash
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def download(d, urls = None):
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
        localpath = ""

        if not ud.localfile:
            continue

        lf = bb.utils.lockfile(ud.lockfile)

        if m.try_premirror(u, ud, d):
            # First try fetching uri, u, from PREMIRRORS
            mirrors = mirror_from_string(bb.data.getVar('PREMIRRORS', d, True))
            localpath = try_mirrors(d, u, mirrors, False, m.forcefetch(u, ud, d))
        elif os.path.exists(ud.localfile):
            localpath = ud.localfile

        # Need to re-test forcefetch() which will return true if our copy is too old
        if m.forcefetch(u, ud, d) or not localpath:
            # Next try fetching from the original uri, u
            try:
                m.download(u, ud, d)
                if hasattr(m, "build_mirror_data"):
                    m.build_mirror_data(u, ud, d)
                localpath = ud.localpath
            except FetchError:
                # Remove any incomplete file
                bb.utils.remove(ud.localpath)
                # Finally, try fetching uri, u, from MIRRORS
                mirrors = mirror_from_string(bb.data.getVar('MIRRORS', d, True))
                localpath = try_mirrors (d, u, mirrors)
                if not localpath or not os.path.exists(localpath):
                    raise FetchError("Unable to fetch URL %s from any source." % u)

        ud.localpath = localpath

        if os.path.exists(ud.md5):
            # Touch the md5 file to show active use of the download
            try:
                os.utime(ud.md5, None)
            except:
                # Errors aren't fatal here
                pass
        else:
            # Only check the checksums if we've not seen this item before
            verify_checksum(u, ud, d)
            Fetch.write_md5sum(u, ud, d)

        bb.utils.unlockfile(lf)

def checkstatus(d, urls = None):
    """
    Check all urls exist upstream
    init must have previously been called
    """
    urldata = init([], d, True)

    if not urls:
        urls = urldata

    for u in urls:
        ud = urldata[u]
        m = ud.method
        logger.debug(1, "Testing URL %s", u)
        # First try checking uri, u, from PREMIRRORS
        mirrors = mirror_from_string(bb.data.getVar('PREMIRRORS', d, True))
        ret = try_mirrors(d, u, mirrors, True)
        if not ret:
            # Next try checking from the original uri, u
            try:
                ret = m.checkstatus(u, ud, d)
            except:
                # Finally, try checking uri, u, from MIRRORS
                mirrors = mirror_from_string(bb.data.getVar('MIRRORS', d, True))
                ret = try_mirrors (d, u, mirrors, True)

        if not ret:
            raise FetchError("URL %s doesn't work" % u)

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

def get_autorev(d):
    #  only not cache src rev in autorev case
    if bb.data.getVar('BB_SRCREV_POLICY', d, True) != "cache":
        bb.data.setVar('__BB_DONT_CACHE', '1', d)
    return "AUTOINC"

def get_srcrev(d):
    """
    Return the version string for the current package
    (usually to be used as PV)
    Most packages usually only have one SCM so we just pass on the call.
    In the multi SCM case, we build a value based on SRCREV_FORMAT which must
    have been set.
    """

    scms = []

    # Only call setup_localpath on URIs which supports_srcrev()
    urldata = init(bb.data.getVar('SRC_URI', d, 1).split(), d, False)
    for u in urldata:
        ud = urldata[u]
        if ud.method.supports_srcrev():
            if not ud.setup:
                ud.setup_localpath(d)
            scms.append(u)

    if len(scms) == 0:
        logger.error("SRCREV was used yet no valid SCM was found in SRC_URI")
        raise ParameterError

    if len(scms) == 1:
        return urldata[scms[0]].method.sortable_revision(scms[0], urldata[scms[0]], d)

    #
    # Mutiple SCMs are in SRC_URI so we resort to SRCREV_FORMAT
    #
    format = bb.data.getVar('SRCREV_FORMAT', d, 1)
    if not format:
        logger.error("The SRCREV_FORMAT variable must be set when multiple SCMs are used.")
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
    exportvars = ['PATH', 'GIT_PROXY_COMMAND', 'GIT_PROXY_HOST',
                  'GIT_PROXY_PORT', 'GIT_CONFIG', 'http_proxy', 'ftp_proxy',
                  'https_proxy', 'no_proxy', 'ALL_PROXY', 'all_proxy',
                  'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'HOME']

    for var in exportvars:
        val = data.getVar(var, d, True)
        if val:
            cmd = 'export ' + var + '=\"%s\"; %s' % (val, cmd)

    logger.debug(1, "Running %s", cmd)

    # redirect stderr to stdout
    stdout_handle = os.popen(cmd + " 2>&1", "r")
    output = ""

    while True:
        line = stdout_handle.readline()
        if not line:
            break
        if not quiet:
            print(line, end=' ')
        output += line

    status = stdout_handle.close() or 0
    signal = status >> 8
    exitstatus = status & 0xff

    if signal:
        raise FetchError("Fetch command %s failed with signal %s, output:\n%s" % (cmd, signal, output))
    elif status != 0:
        raise FetchError("Fetch command %s failed with exit code %s, output:\n%s" % (cmd, status, output))

    return output

def try_mirrors(d, uri, mirrors, check = False, force = False):
    """
    Try to use a mirrored version of the sources.
    This method will be automatically called before the fetchers go.

    d Is a bb.data instance
    uri is the original uri we're trying to download
    mirrors is the list of mirrors we're going to try
    """
    fpath = os.path.join(data.getVar("DL_DIR", d, 1), os.path.basename(uri))
    if not check and os.access(fpath, os.R_OK) and not force:
        logger.debug(1, "%s already exists, skipping checkout.", fpath)
        return fpath

    ld = d.createCopy()
    for (find, replace) in mirrors:
        newuri = uri_replace(uri, find, replace, ld)
        if newuri != uri:
            try:
                ud = FetchData(newuri, ld)
            except bb.fetch2.NoMethodError:
                logger.debug(1, "No method for %s", uri)
                continue

            ud.setup_localpath(ld)

            try:
                if check:
                    found = ud.method.checkstatus(newuri, ud, ld)
                    if found:
                        return found
                else:
                    ud.method.download(newuri, ud, ld)
                    if hasattr(ud.method,"build_mirror_data"):
                        ud.method.build_mirror_data(newuri, ud, ld)
                    return ud.localpath
            except (bb.fetch2.MissingParameterError,
                    bb.fetch2.FetchError,
                    bb.fetch2.MD5SumError):
                import sys
                (type, value, traceback) = sys.exc_info()
                logger.debug(2, "Mirror fetch failure: %s", value)
                bb.utils.remove(ud.localpath)
                continue
    return None


class FetchData(object):
    """
    A class which represents the fetcher state for a given URI.
    """
    def __init__(self, url, d):
        self.localfile = ""
        (self.type, self.host, self.path, self.user, self.pswd, self.parm) = decodeurl(data.expand(url, d))
        self.date = Fetch.getSRCDate(self, d)
        self.url = url
        if not self.user and "user" in self.parm:
            self.user = self.parm["user"]
        if not self.pswd and "pswd" in self.parm:
            self.pswd = self.parm["pswd"]
        self.setup = False

        if "name" in self.parm:
            self.md5_name = "%s.md5sum" % self.parm["name"]
            self.sha256_name = "%s.sha256sum" % self.parm["name"]
        else:
            self.md5_name = "md5sum"
            self.sha256_name = "sha256sum"
        self.md5_expected = bb.data.getVarFlag("SRC_URI", self.md5_name, d)
        self.sha256_expected = bb.data.getVarFlag("SRC_URI", self.sha256_name, d)

        for m in methods:
            if m.supports(url, self, d):
                self.method = m
                if hasattr(m,"urldata_init"):
                    m.urldata_init(self, d)
                if m.supports_srcrev():
                    self.revision = Fetch.srcrev_internal_helper(self, d);
                return
        raise NoMethodError("Missing implementation for url %s" % url)

    def setup_localpath(self, d):
        self.setup = True
        if "localpath" in self.parm:
            # if user sets localpath for file, use it instead.
            self.localpath = self.parm["localpath"]
            self.basename = os.path.basename(self.localpath)
        else:
            premirrors = bb.data.getVar('PREMIRRORS', d, True)
            local = ""
            if premirrors and self.url:
                aurl = self.url.split(";")[0]
                mirrors = mirror_from_string(premirrors)
                for (find, replace) in mirrors:
                    if replace.startswith("file://"):
                        path = aurl.split("://")[1]
                        path = path.split(";")[0]
                        local = replace.split("://")[1] + os.path.basename(path)
                        if local == aurl or not os.path.exists(local) or os.path.isdir(local):
                            local = ""
                self.localpath = local
            if not local:
                self.localpath = self.method.localpath(self.url, self, d)
                # We have to clear data's internal caches since the cached value of SRCREV is now wrong.
                # Horrible...
                bb.data.delVar("ISHOULDNEVEREXIST", d)

        if self.localpath is not None:
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
    def _strip_leading_slashes(self, relpath):
        """
        Remove leading slash as os.path.join can't cope
        """
        while os.path.isabs(relpath):
            relpath = relpath[1:]
        return relpath

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

    def supports_srcrev(self):
        """
        The fetcher supports auto source revisions (SRCREV)
        """
        return False

    def download(self, url, urldata, d):
        """
        Fetch urls
        Assumes localpath was called first
        """
        raise NoMethodError("Missing implementation for url")

    def unpack(self, urldata, rootdir, data):
        import subprocess
        file = urldata.localpath
        dots = file.split(".")
        if dots[-1] in ['gz', 'bz2', 'Z']:
            efile = os.path.join(bb.data.getVar('WORKDIR', data, 1),os.path.basename('.'.join(dots[0:-1])))
        else:
            efile = file
        cmd = None
        if file.endswith('.tar'):
            cmd = 'tar x --no-same-owner -f %s' % file
        elif file.endswith('.tgz') or file.endswith('.tar.gz') or file.endswith('.tar.Z'):
            cmd = 'tar xz --no-same-owner -f %s' % file
        elif file.endswith('.tbz') or file.endswith('.tbz2') or file.endswith('.tar.bz2'):
            cmd = 'bzip2 -dc %s | tar x --no-same-owner -f -' % file
        elif file.endswith('.gz') or file.endswith('.Z') or file.endswith('.z'):
            cmd = 'gzip -dc %s > %s' % (file, efile)
        elif file.endswith('.bz2'):
            cmd = 'bzip2 -dc %s > %s' % (file, efile)
        elif file.endswith('.tar.xz'):
            cmd = 'xz -dc %s | tar x --no-same-owner -f -' % file
        elif file.endswith('.xz'):
            cmd = 'xz -dc %s > %s' % (file, efile)
        elif file.endswith('.zip') or file.endswith('.jar'):
            cmd = 'unzip -q -o'
            if 'dos' in urldata.parm:
                cmd = '%s -a' % cmd
            cmd = "%s '%s'" % (cmd, file)
        elif os.path.isdir(file):
            filesdir = os.path.realpath(bb.data.getVar("FILESDIR", data, 1))
            destdir = "."
            if file[0:len(filesdir)] == filesdir:
                destdir = file[len(filesdir):file.rfind('/')]
                destdir = destdir.strip('/')
                if len(destdir) < 1:
                    destdir = "."
                elif not os.access("%s/%s" % (rootdir, destdir), os.F_OK):
                    os.makedirs("%s/%s" % (rootdir, destdir))
            cmd = 'cp -pPR %s %s/%s/' % (file, rootdir, destdir)
        else:
            if not 'patch' in urldata.parm:
                # The "destdir" handling was specifically done for FILESPATH
                # items.  So, only do so for file:// entries.
                if urldata.type == "file" and urldata.path.find("/") != -1:
                    destdir = urldata.path.rsplit("/", 1)[0]
                else:
                    destdir = "."
                bb.mkdirhier("%s/%s" % (rootdir, destdir))
                cmd = 'cp %s %s/%s/' % (file, rootdir, destdir)

        if not cmd:
            return True

        dest = os.path.join(rootdir, os.path.basename(file))
        if os.path.exists(dest):
            if os.path.samefile(file, dest):
                return True

        # Change to subdir before executing command
        save_cwd = os.getcwd();
        os.chdir(rootdir)
        if 'subdir' in urldata.parm:
            newdir = ("%s/%s" % (rootdir, urldata.parm['subdir']))
            bb.mkdirhier(newdir)
            os.chdir(newdir)

        cmd = "PATH=\"%s\" %s" % (bb.data.getVar('PATH', data, 1), cmd)
        bb.note("Unpacking %s to %s/" % (file, os.getcwd()))
        ret = subprocess.call(cmd, preexec_fn=subprocess_setup, shell=True)

        os.chdir(save_cwd)

        return ret == 0

    def try_premirror(self, url, urldata, d):
        """
        Should premirrors be used?
        """
        if urldata.method.forcefetch(url, urldata, d):
            return True
        elif os.path.exists(urldata.md5) and os.path.exists(urldata.localfile):
            return False
        else:
            return True

    def checkstatus(self, url, urldata, d):
        """
        Check the status of a URL
        Assumes localpath was called first
        """
        logger.info("URL %s could not be checked for status since no method exists.", url)
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
            b) latest revision if SREREV="AUTOINC"
            c) None if not specified
        """

        if 'rev' in ud.parm:
            return ud.parm['rev']

        if 'tag' in ud.parm:
            return ud.parm['tag']

        rev = None
        if 'name' in ud.parm:
            pn = data.getVar("PN", d, 1)
            rev = data.getVar("SRCREV_%s_pn-%s" % (ud.parm['name'], pn), d, 1)
            if not rev:
                rev = data.getVar("SRCREV_pn-%s_%s" % (pn, ud.parm['name']), d, 1)
            if not rev:
                rev = data.getVar("SRCREV_%s" % (ud.parm['name']), d, 1)
        if not rev:
            rev = data.getVar("SRCREV", d, 1)
        if rev == "INVALID":
            raise InvalidSRCREV("Please set SRCREV to a valid value")
        if rev == "AUTOINC":
            rev = ud.method.latest_revision(ud.url, ud, d)

        return rev

    srcrev_internal_helper = staticmethod(srcrev_internal_helper)

    def localcount_internal_helper(ud, d):
        """
        Return:
            a) a locked localcount if specified
            b) None otherwise
        """

        localcount = None
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
        wanted_sum = ud.parm.get('md5sum')
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

        pd = persist_data.persist(d)
        revs = pd['BB_URI_HEADREVS']
        key = self.generate_revision_key(url, ud, d)
        rev = revs[key]
        if rev != None:
            return str(rev)

        revs[key] = rev = self._latest_revision(url, ud, d)
        return rev

    def sortable_revision(self, url, ud, d):
        """

        """
        if hasattr(self, "_sortable_revision"):
            return self._sortable_revision(url, ud, d)

        pd = persist_data.persist(d)
        localcounts = pd['BB_URI_LOCALCOUNT']
        key = self.generate_revision_key(url, ud, d)

        latest_rev = self._build_revision(url, ud, d)
        last_rev = localcounts[key + '_rev']
        uselocalcount = bb.data.getVar("BB_LOCALCOUNT_OVERRIDE", d, True) or False
        count = None
        if uselocalcount:
            count = Fetch.localcount_internal_helper(ud, d)
        if count is None:
            count = localcounts[key + '_count']

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

        localcounts[key + '_rev'] = latest_rev
        localcounts[key + '_count'] = count

        return str(count + "+" + latest_rev)

    def generate_revision_key(self, url, ud, d):
        key = self._revision_key(url, ud, d)
        return "%s-%s" % (key, bb.data.getVar("PN", d, True) or "")

from . import cvs
from . import git
from . import local
from . import svn
from . import wget
from . import svk
from . import ssh
from . import perforce
from . import bzr
from . import hg
from . import osc
from . import repo

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
