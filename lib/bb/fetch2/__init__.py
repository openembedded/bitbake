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
import bb.data, bb.persist_data, bb.utils
from bb import data

__version__ = "2"

logger = logging.getLogger("BitBake.Fetcher")

class BBFetchException(Exception):
    """Class all fetch exceptions inherit from"""
    def __init__(self, message):
         self.msg = message
         Exception.__init__(self, message)

    def __str__(self):
         return self.msg

class MalformedUrl(BBFetchException):
    """Exception raised when encountering an invalid url"""
    def __init__(self, url):
         msg = "The URL: '%s' is invalid and cannot be interpreted" % url
         self.url = url
         BBFetchException.__init__(self, msg)
         self.args = url

class FetchError(BBFetchException):
    """General fetcher exception when something happens incorrectly"""
    def __init__(self, message, url = None):
         msg = "Fetcher failure for URL: '%s'. %s" % (url, message)
         self.url = url
         BBFetchException.__init__(self, msg)
         self.args = (message, url)

class UnpackError(BBFetchException):
    """General fetcher exception when something happens incorrectly when unpacking"""
    def __init__(self, message, url):
         msg = "Unpack failure for URL: '%s'. %s" % (url, message)
         self.url = url
         BBFetchException.__init__(self, msg)
         self.args = (message, url)

class NoMethodError(BBFetchException):
    """Exception raised when there is no method to obtain a supplied url or set of urls"""
    def __init__(self, url):
         msg = "Could not find a fetcher which supports the URL: '%s'" % url
         self.url = url
         BBFetchException.__init__(self, msg)
         self.args = url

class MissingParameterError(BBFetchException):
    """Exception raised when a fetch method is missing a critical parameter in the url"""
    def __init__(self, missing, url):
         msg = "URL: '%s' is missing the required parameter '%s'" % (url, missing)
         self.url = url
         self.missing = missing
         BBFetchException.__init__(self, msg)
         self.args = (missing, url)

class ParameterError(BBFetchException):
    """Exception raised when a url cannot be proccessed due to invalid parameters."""
    def __init__(self, message, url):
         msg = "URL: '%s' has invalid parameters. %s" % (url, message)
         self.url = url
         BBFetchException.__init__(self, msg)
         self.args = (message, url)

class MD5SumError(BBFetchException):
    """Exception raised when a MD5 checksum of a file does not match for a downloaded file"""
    def __init__(self, path, wanted, got, url):
         msg = "File: '%s' has md5 checksum %s when %s was expected (from URL: '%s')" % (path, got, wanted, url)
         self.url = url
         self.path = path
         self.wanted = wanted
         self.got = got
         BBFetchException.__init__(self, msg)
         self.args = (path, wanted, got, url)

class SHA256SumError(MD5SumError):
    """Exception raised when a SHA256 checksum of a file does not match for a downloaded file"""
    def __init__(self, path, wanted, got, url):
         msg = "File: '%s' has sha256 checksum %s when %s was expected (from URL: '%s')" % (path, got, wanted, url)
         self.url = url
         self.path = path
         self.wanted = wanted
         self.got = got
         BBFetchException.__init__(self, msg)
         self.args = (path, wanted, got, url)

class NetworkAccess(BBFetchException):
    """Exception raised when network access is disabled but it is required."""
    def __init__(self, url, cmd):
         msg = "Network access disabled through BB_NO_NETWORK but access rquested with command %s (for url %s)" % (cmd, url)
         self.url = url
         self.cmd = cmd
         BBFetchException.__init__(self, msg)
         self.args = (url, cmd)


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

    if not path:
        raise MissingParameterError('path', "encoded from the data %s" % str(decoded))
    if not type:
        raise MissingParameterError('type', "encoded from the data %s" % str(decoded))
    url = '%s://' % type
    if user and type != "file":
        url += "%s" % user
        if pswd:
            url += ":%s" % pswd
        url += "@"
    if host and type != "file":
        url += "%s" % host
    url += "%s" % path
    if p:
        for parm in p:
            url += ";%s=%s" % (parm, p[parm])

    return url

def uri_replace(ud, uri_find, uri_replace, d):
    if not ud.url or not uri_find or not uri_replace:
        logger.debug(1, "uri_replace: passed an undefined value, not replacing")
    uri_decoded = list(decodeurl(ud.url))
    uri_find_decoded = list(decodeurl(uri_find))
    uri_replace_decoded = list(decodeurl(uri_replace))
    result_decoded = ['', '', '', '', '', {}]
    for i in uri_find_decoded:
        loc = uri_find_decoded.index(i)
        result_decoded[loc] = uri_decoded[loc]
        if isinstance(i, basestring):
            if (re.match(i, uri_decoded[loc])):
                if not uri_replace_decoded[loc]:
                    result_decoded[loc] = ""    
                else:
                    result_decoded[loc] = re.sub(i, uri_replace_decoded[loc], uri_decoded[loc])
                if uri_find_decoded.index(i) == 2:
                    if ud.mirrortarball:
                        result_decoded[loc] = os.path.join(os.path.dirname(result_decoded[loc]), os.path.basename(ud.mirrortarball))
                    elif ud.localpath:
                        result_decoded[loc] = os.path.join(os.path.dirname(result_decoded[loc]), os.path.basename(ud.localpath))
            else:
                return ud.url
    return encodeurl(result_decoded)

methods = []
urldata_cache = {}
saved_headrevs = {}

def fetcher_init(d):
    """
    Called to initialize the fetchers once the configuration data is known.
    Calls before this must not hit the cache.
    """
    # When to drop SCM head revisions controlled by user policy
    srcrev_policy = bb.data.getVar('BB_SRCREV_POLICY', d, True) or "clear"
    if srcrev_policy == "cache":
        logger.debug(1, "Keeping SRCREV cache due to cache policy of: %s", srcrev_policy)
    elif srcrev_policy == "clear":
        logger.debug(1, "Clearing SRCREV cache due to cache policy of: %s", srcrev_policy)
        revs = bb.persist_data.persist('BB_URI_HEADREVS', d)
        try:
            bb.fetch2.saved_headrevs = revs.items()
        except:
            pass
        revs.clear()
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

    data = bb.persist_data.persist('BB_URI_HEADREVS', d).items()
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
            raise FetchError("No checksum specified for %s." % u, u)
        return

    if ud.md5_expected != md5data:
        raise MD5SumError(ud.localpath, ud.md5_expected, md5data, u)

    if ud.sha256_expected != sha256data:
        raise SHA256SumError(ud.localpath, ud.sha256_expected, sha256data, u)

def update_stamp(u, ud, d):
    """
        donestamp is file stamp indicating the whole fetching is done
        this function update the stamp after verifying the checksum
    """
    if os.path.exists(ud.donestamp):
        # Touch the done stamp file to show active use of the download
        try:
            os.utime(ud.donestamp, None)
        except:
            # Errors aren't fatal here
            pass
    else:
        verify_checksum(u, ud, d)
        open(ud.donestamp, 'w').close()

def subprocess_setup():
    import signal
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    # SIGPIPE errors are known issues with gzip/bash
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

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
    fetcher = Fetch(bb.data.getVar('SRC_URI', d, True).split(), d)
    urldata = fetcher.ud
    for u in urldata:
        if urldata[u].method.supports_srcrev():
            scms.append(u)

    if len(scms) == 0:
        raise FetchError("SRCREV was used yet no valid SCM was found in SRC_URI")

    if len(scms) == 1 and len(urldata[scms[0]].names) == 1:
        return urldata[scms[0]].method.sortable_revision(scms[0], urldata[scms[0]], d, urldata[scms[0]].names[0])

    #
    # Mutiple SCMs are in SRC_URI so we resort to SRCREV_FORMAT
    #
    format = bb.data.getVar('SRCREV_FORMAT', d, True)
    if not format:
        raise FetchError("The SRCREV_FORMAT variable must be set when multiple SCMs are used.")

    for scm in scms:
        ud = urldata[scm]
        for name in ud.names:
            rev = ud.method.sortable_revision(scm, ud, d, name)
            format = format.replace(name, rev)

    return format

def localpath(url, d):
    fetcher = bb.fetch2.Fetch([url], d)
    return fetcher.localpath(url)

def runfetchcmd(cmd, d, quiet = False, cleanup = []):
    """
    Run cmd returning the command output
    Raise an error if interrupted or cmd fails
    Optionally echo command output to stdout
    Optionally remove the files/directories listed in cleanup upon failure
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
        val = bb.data.getVar(var, d, True)
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

    if (signal or status != 0):
        for f in cleanup:
            try:
                bb.utils.remove(f, True)
            except OSError:
                pass

        if signal:
            raise FetchError("Fetch command %s failed with signal %s, output:\n%s" % (cmd, signal, output))
        elif status != 0:
            raise FetchError("Fetch command %s failed with exit code %s, output:\n%s" % (cmd, status, output))

    return output

def check_network_access(d, info = "", url = None):
    """
    log remote network access, and error if BB_NO_NETWORK is set
    """
    if bb.data.getVar("BB_NO_NETWORK", d, True) == "1":
        raise NetworkAccess(url, info)
    else:
        logger.debug(1, "Fetcher accessed the network with the command %s" % info)

def try_mirrors(d, origud, mirrors, check = False):
    """
    Try to use a mirrored version of the sources.
    This method will be automatically called before the fetchers go.

    d Is a bb.data instance
    uri is the original uri we're trying to download
    mirrors is the list of mirrors we're going to try
    """
    ld = d.createCopy()
    for line in mirrors:
        try:
            (find, replace) = line
        except ValueError:
            continue
        newuri = uri_replace(origud, find, replace, ld)
        if newuri == origud.url:
            continue
        try:
            ud = FetchData(newuri, ld)
            ud.setup_localpath(ld)

            if check:
                found = ud.method.checkstatus(newuri, ud, ld)
                if found:
                    return found
                continue

            if ud.method.need_update(newuri, ud, ld):
                ud.method.download(newuri, ud, ld)
                if hasattr(ud.method,"build_mirror_data"):
                    ud.method.build_mirror_data(newuri, ud, ld)

            if not ud.localpath or not os.path.exists(ud.localpath):
                continue

            if ud.localpath == origud.localpath:
                return ud.localpath

            # We may be obtaining a mirror tarball which needs further processing by the real fetcher
            # If that tarball is a local file:// we need to provide a symlink to it
            dldir = ld.getVar("DL_DIR", True)
            if os.path.basename(ud.localpath) != os.path.basename(origud.localpath):
                dest = os.path.join(dldir, os.path.basename(ud.localpath))
                if not os.path.exists(dest):
                    os.symlink(ud.localpath, dest)
                return None
            # Otherwise the result is a local file:// and we symlink to it
            if not os.path.exists(origud.localpath):
                 os.symlink(ud.localpath, origud.localpath)
            return ud.localpath

        except bb.fetch2.NetworkAccess:
            raise

        except bb.fetch2.BBFetchException as e:
            logger.debug(1, "Mirror fetch failure for url %s (original url: %s)" % (newuri, origud.url))
            logger.debug(1, str(e))
            try:
                if os.path.isfile(ud.localpath):
                    bb.utils.remove(ud.localpath)
            except UnboundLocalError:
                pass
            continue
    return None

def srcrev_internal_helper(ud, d, name):
    """
    Return:
        a) a source revision if specified
        b) latest revision if SRCREV="AUTOINC"
        c) None if not specified
    """

    if 'rev' in ud.parm:
        return ud.parm['rev']

    if 'tag' in ud.parm:
        return ud.parm['tag']

    rev = None
    pn = bb.data.getVar("PN", d, True)
    if name != '':
        rev = bb.data.getVar("SRCREV_%s_pn-%s" % (name, pn), d, True)
        if not rev:
            rev = bb.data.getVar("SRCREV_%s" % name, d, True)
    if not rev:
       rev = bb.data.getVar("SRCREV_pn-%s" % pn, d, True)
    if not rev:
        rev = bb.data.getVar("SRCREV", d, True)
    if rev == "INVALID":
        raise FetchError("Please set SRCREV to a valid value", ud.url)
    if rev == "AUTOINC":
        rev = ud.method.latest_revision(ud.url, ud, d, name)

    return rev

class FetchData(object):
    """
    A class which represents the fetcher state for a given URI.
    """
    def __init__(self, url, d):
        # localpath is the location of a downloaded result. If not set, the file is local.
        self.donestamp = None
        self.localfile = ""
        self.localpath = None
        self.lockfile = None
        self.mirrortarball = None
        self.basename = None
        (self.type, self.host, self.path, self.user, self.pswd, self.parm) = decodeurl(data.expand(url, d))
        self.date = self.getSRCDate(d)
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

        self.names = self.parm.get("name",'default').split(',')

        self.method = None
        for m in methods:
            if m.supports(url, self, d):
                self.method = m
                break                

        if not self.method:
            raise NoMethodError(url)

        if hasattr(self.method, "urldata_init"):
            self.method.urldata_init(self, d)

        if "localpath" in self.parm:
            # if user sets localpath for file, use it instead.
            self.localpath = self.parm["localpath"]
            self.basename = os.path.basename(self.localpath)
        elif self.localfile:
            self.localpath = self.method.localpath(self.url, self, d)

        # Note: These files should always be in DL_DIR whereas localpath may not be.
        basepath = bb.data.expand("${DL_DIR}/%s" % os.path.basename(self.localpath or self.basename), d)
        self.donestamp = basepath + '.done'
        self.lockfile = basepath + '.lock'

    def setup_revisons(self, d):
        self.revisions = {}
        for name in self.names:
            self.revisions[name] = srcrev_internal_helper(self, d, name)

        # add compatibility code for non name specified case
        if len(self.names) == 1:
            self.revision = self.revisions[self.names[0]]

    def setup_localpath(self, d):
        if not self.localpath:
            self.localpath = self.method.localpath(self.url, self, d)

    def getSRCDate(self, d):
        """
        Return the SRC Date for the component

        d the bb.data module
        """
        if "srcdate" in self.parm:
            return self.parm['srcdate']

        pn = bb.data.getVar("PN", d, True)

        if pn:
            return bb.data.getVar("SRCDATE_%s" % pn, d, True) or bb.data.getVar("SRCDATE", d, True) or bb.data.getVar("DATE", d, True)

        return bb.data.getVar("SRCDATE", d, True) or bb.data.getVar("DATE", d, True)

class FetchMethod(object):
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
        return os.path.join(data.getVar("DL_DIR", d, True), urldata.localfile)

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

    def need_update(self, url, ud, d):
        """
        Force a fetch, even if localpath exists?
        """
        if os.path.exists(ud.localpath):
            return False
        return True

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
        raise NoMethodError(url)

    def unpack(self, urldata, rootdir, data):
        import subprocess
        iterate = False
        file = urldata.localpath

        try:
            unpack = bb.utils.to_boolean(urldata.parm.get('unpack'), True)
        except ValueError as exc:
            bb.fatal("Invalid value for 'unpack' parameter for %s: %s" %
                     (file, urldata.parm.get('unpack')))

        dots = file.split(".")
        if dots[-1] in ['gz', 'bz2', 'Z']:
            efile = os.path.join(bb.data.getVar('WORKDIR', data, True),os.path.basename('.'.join(dots[0:-1])))
        else:
            efile = file
        cmd = None

        if unpack:
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
                try:
                    dos = bb.utils.to_boolean(urldata.parm.get('dos'), False)
                except ValueError as exc:
                    bb.fatal("Invalid value for 'dos' parameter for %s: %s" %
                             (file, urldata.parm.get('dos')))
                cmd = 'unzip -q -o'
                if dos:
                    cmd = '%s -a' % cmd
                cmd = "%s '%s'" % (cmd, file)
            elif file.endswith('.src.rpm') or file.endswith('.srpm'):
                if 'extract' in urldata.parm:
                    unpack_file = urldata.parm.get('extract')
                    cmd = 'rpm2cpio.sh %s | cpio -i %s' % (file, unpack_file)
                    iterate = True
                    iterate_file = unpack_file
                else:
                    cmd = 'rpm2cpio.sh %s | cpio -i' % (file)

        if not unpack or not cmd:
            # If file == dest, then avoid any copies, as we already put the file into dest!
            dest = os.path.join(rootdir, os.path.basename(file))
            if (file != dest) and not (os.path.exists(dest) and os.path.samefile(file, dest)):
                if os.path.isdir(file):
                    filesdir = os.path.realpath(bb.data.getVar("FILESDIR", data, True))
                    destdir = "."
                    if file[0:len(filesdir)] == filesdir:
                        destdir = file[len(filesdir):file.rfind('/')]
                        destdir = destdir.strip('/')
                        if len(destdir) < 1:
                            destdir = "."
                        elif not os.access("%s/%s" % (rootdir, destdir), os.F_OK):
                            os.makedirs("%s/%s" % (rootdir, destdir))
                    cmd = 'cp -pPR %s %s/%s/' % (file, rootdir, destdir)
                    #cmd = 'tar -cf - -C "%d" -ps . | tar -xf - -C "%s/%s/"' % (file, rootdir, destdir)
                else:
                    # The "destdir" handling was specifically done for FILESPATH
                    # items.  So, only do so for file:// entries.
                    if urldata.type == "file" and urldata.path.find("/") != -1:
                       destdir = urldata.path.rsplit("/", 1)[0]
                    else:
                       destdir = "."
                    bb.utils.mkdirhier("%s/%s" % (rootdir, destdir))
                    cmd = 'cp %s %s/%s/' % (file, rootdir, destdir)

        if not cmd:
            return

        # Change to subdir before executing command
        save_cwd = os.getcwd();
        os.chdir(rootdir)
        if 'subdir' in urldata.parm:
            newdir = ("%s/%s" % (rootdir, urldata.parm.get('subdir')))
            bb.utils.mkdirhier(newdir)
            os.chdir(newdir)

        cmd = "PATH=\"%s\" %s" % (bb.data.getVar('PATH', data, True), cmd)
        bb.note("Unpacking %s to %s/" % (file, os.getcwd()))
        ret = subprocess.call(cmd, preexec_fn=subprocess_setup, shell=True)

        os.chdir(save_cwd)

        if ret != 0:
            raise UnpackError("Unpack command %s failed with return value %s" % (cmd, ret), urldata.url)

        if iterate is True:
            iterate_urldata = urldata
            iterate_urldata.localpath = "%s/%s" % (rootdir, iterate_file)
            self.unpack(urldata, rootdir, data)

        return

    def clean(self, urldata, d):
       """
       Clean any existing full or partial download
       """
       bb.utils.remove(urldata.localpath)

    def try_premirror(self, url, urldata, d):
        """
        Should premirrors be used?
        """
        return True

    def checkstatus(self, url, urldata, d):
        """
        Check the status of a URL
        Assumes localpath was called first
        """
        logger.info("URL %s could not be checked for status since no method exists.", url)
        return True

    def localcount_internal_helper(ud, d, name):
        """
        Return:
            a) a locked localcount if specified
            b) None otherwise
        """

        localcount = None
        if name != '':
            pn = bb.data.getVar("PN", d, True)
            localcount = bb.data.getVar("LOCALCOUNT_" + name, d, True)
        if not localcount:
            localcount = bb.data.getVar("LOCALCOUNT", d, True)
        return localcount

    localcount_internal_helper = staticmethod(localcount_internal_helper)

    def latest_revision(self, url, ud, d, name):
        """
        Look in the cache for the latest revision, if not present ask the SCM.
        """
        if not hasattr(self, "_latest_revision"):
            raise ParameterError("The fetcher for this URL does not support _latest_revision", url)

        revs = bb.persist_data.persist('BB_URI_HEADREVS', d)
        key = self.generate_revision_key(url, ud, d, name)
        try:
            return revs[key]
        except KeyError:
            revs[key] = rev = self._latest_revision(url, ud, d, name)
            return rev

    def sortable_revision(self, url, ud, d, name):
        """

        """
        if hasattr(self, "_sortable_revision"):
            return self._sortable_revision(url, ud, d)

        localcounts = bb.persist_data.persist('BB_URI_LOCALCOUNT', d)
        key = self.generate_revision_key(url, ud, d, name)

        latest_rev = self._build_revision(url, ud, d, name)
        last_rev = localcounts.get(key + '_rev')
        uselocalcount = bb.data.getVar("BB_LOCALCOUNT_OVERRIDE", d, True) or False
        count = None
        if uselocalcount:
            count = FetchMethod.localcount_internal_helper(ud, d, name)
        if count is None:
            count = localcounts.get(key + '_count') or "0"

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

    def generate_revision_key(self, url, ud, d, name):
        key = self._revision_key(url, ud, d, name)
        return "%s-%s" % (key, bb.data.getVar("PN", d, True) or "")

class Fetch(object):
    def __init__(self, urls, d, cache = True):
        if len(urls) == 0:
            urls = d.getVar("SRC_URI", True).split()
        self.urls = urls
        self.d = d
        self.ud = {}

        fn = bb.data.getVar('FILE', d, True)
        if cache and fn in urldata_cache:
            self.ud = urldata_cache[fn]

        for url in urls:
            if url not in self.ud:
                self.ud[url] = FetchData(url, d)

        if cache:
            urldata_cache[fn] = self.ud

    def localpath(self, url):
        if url not in self.urls:
            self.ud[url] = FetchData(url, self.d)

        self.ud[url].setup_localpath(self.d)
        return bb.data.expand(self.ud[url].localpath, self.d)

    def localpaths(self):
        """
        Return a list of the local filenames, assuming successful fetch
        """
        local = []

        for u in self.urls:
            ud = self.ud[u]
            ud.setup_localpath(self.d)
            local.append(ud.localpath)

        return local

    def download(self, urls = []):
        """
        Fetch all urls
        """
        if len(urls) == 0:
            urls = self.urls

        network = bb.data.getVar("BB_NO_NETWORK", self.d, True)
        premirroronly = (bb.data.getVar("BB_FETCH_PREMIRRORONLY", self.d, True) == "1")

        for u in urls:
            ud = self.ud[u]
            ud.setup_localpath(self.d)
            m = ud.method
            localpath = ""

            lf = bb.utils.lockfile(ud.lockfile)

            try:
                bb.data.setVar("BB_NO_NETWORK", network, self.d)
 
                if not m.need_update(u, ud, self.d):
                    localpath = ud.localpath
                elif m.try_premirror(u, ud, self.d):
                    logger.debug(1, "Trying PREMIRRORS")
                    mirrors = mirror_from_string(bb.data.getVar('PREMIRRORS', self.d, True))
                    localpath = try_mirrors(self.d, ud, mirrors, False)

                if premirroronly:
                    bb.data.setVar("BB_NO_NETWORK", "1", self.d)

                if not localpath and m.need_update(u, ud, self.d):
                    try:
                        logger.debug(1, "Trying Upstream")
                        m.download(u, ud, self.d)
                        if hasattr(m, "build_mirror_data"):
                            m.build_mirror_data(u, ud, self.d)
                        localpath = ud.localpath
                        # early checksum verify, so that if checksum mismatched,
                        # fetcher still have chance to fetch from mirror
                        update_stamp(u, ud, self.d)

                    except bb.fetch2.NetworkAccess:
                        raise

                    except BBFetchException as e:
                        logger.warn(str(e))
                        # Remove any incomplete fetch
                        if os.path.isfile(ud.localpath):
                            bb.utils.remove(ud.localpath)
                        logger.debug(1, "Trying MIRRORS")
                        mirrors = mirror_from_string(bb.data.getVar('MIRRORS', self.d, True))
                        localpath = try_mirrors (self.d, ud, mirrors)

                if not localpath or ((not os.path.exists(localpath)) and localpath.find("*") == -1):
                    raise FetchError("Unable to fetch URL %s from any source." % u, u)

                update_stamp(u, ud, self.d)

            finally:
                bb.utils.unlockfile(lf)

    def checkstatus(self, urls = []):
        """
        Check all urls exist upstream
        """

        if len(urls) == 0:
            urls = self.urls

        for u in urls:
            ud = self.ud[u]
            ud.setup_localpath(self.d)
            m = ud.method
            logger.debug(1, "Testing URL %s", u)
            # First try checking uri, u, from PREMIRRORS
            mirrors = mirror_from_string(bb.data.getVar('PREMIRRORS', self.d, True))
            ret = try_mirrors(self.d, ud, mirrors, True)
            if not ret:
                # Next try checking from the original uri, u
                try:
                    ret = m.checkstatus(u, ud, self.d)
                except:
                    # Finally, try checking uri, u, from MIRRORS
                    mirrors = mirror_from_string(bb.data.getVar('MIRRORS', self.d, True))
                    ret = try_mirrors (self.d, ud, mirrors, True)

            if not ret:
                raise FetchError("URL %s doesn't work" % u, u)

    def unpack(self, root, urls = []):
        """
        Check all urls exist upstream
        """

        if len(urls) == 0:
            urls = self.urls

        for u in urls:
            ud = self.ud[u]
            ud.setup_localpath(self.d)

            if bb.data.expand(self.localpath, self.d) is None:
                continue

            if ud.lockfile:
                lf = bb.utils.lockfile(ud.lockfile)

            ud.method.unpack(ud, root, self.d)

            if ud.lockfile:
                bb.utils.unlockfile(lf)

    def clean(self, urls = []):
        """
        Clean files that the fetcher gets or places
        """

        if len(urls) == 0:
            urls = self.urls

        for url in urls:
            if url not in self.ud:
                self.ud[url] = FetchData(url, d)
            ud = self.ud[url]
            ud.setup_localpath(self.d)

            if not ud.localfile or self.localpath is None:
                continue

            if ud.lockfile:
                lf = bb.utils.lockfile(ud.lockfile)

            ud.method.clean(ud, self.d)
            if ud.donestamp:
                bb.utils.remove(ud.donestamp)

            if ud.lockfile:
                bb.utils.unlockfile(lf)

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
