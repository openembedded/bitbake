# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

Classes for obtaining upstream sources for the
BitBake build tools.
"""

# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2012  Intel Corporation
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
import signal
import glob
import logging
import urllib
import urlparse
import operator
import bb.persist_data, bb.utils
import bb.checksum
from bb import data
import bb.process
import subprocess

__version__ = "2"
_checksum_cache = bb.checksum.FileChecksumCache()

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
    def __init__(self, url, message=''):
         if message:
             msg = message
         else:
             msg = "The URL: '%s' is invalid and cannot be interpreted" % url
         self.url = url
         BBFetchException.__init__(self, msg)
         self.args = (url,)

class FetchError(BBFetchException):
    """General fetcher exception when something happens incorrectly"""
    def __init__(self, message, url = None):
         if url:
            msg = "Fetcher failure for URL: '%s'. %s" % (url, message)
         else:
            msg = "Fetcher failure: %s" % message
         self.url = url
         BBFetchException.__init__(self, msg)
         self.args = (message, url)

class ChecksumError(FetchError):
    """Exception when mismatched checksum encountered"""
    def __init__(self, message, url = None, checksum = None):
        self.checksum = checksum
        FetchError.__init__(self, message, url)

class NoChecksumError(FetchError):
    """Exception when no checksum is specified, but BB_STRICT_CHECKSUM is set"""

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
         self.args = (url,)

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

class NetworkAccess(BBFetchException):
    """Exception raised when network access is disabled but it is required."""
    def __init__(self, url, cmd):
         msg = "Network access disabled through BB_NO_NETWORK (or set indirectly due to use of BB_FETCH_PREMIRRORONLY) but access requested with command %s (for url %s)" % (cmd, url)
         self.url = url
         self.cmd = cmd
         BBFetchException.__init__(self, msg)
         self.args = (url, cmd)

class NonLocalMethod(Exception):
    def __init__(self):
        Exception.__init__(self)


class URI(object):
    """
    A class representing a generic URI, with methods for
    accessing the URI components, and stringifies to the
    URI.

    It is constructed by calling it with a URI, or setting
    the attributes manually:

     uri = URI("http://example.com/")

     uri = URI()
     uri.scheme = 'http'
     uri.hostname = 'example.com'
     uri.path = '/'

    It has the following attributes:

      * scheme (read/write)
      * userinfo (authentication information) (read/write)
        * username (read/write)
        * password (read/write)

        Note, password is deprecated as of RFC 3986.

      * hostname (read/write)
      * port (read/write)
      * hostport (read only)
        "hostname:port", if both are set, otherwise just "hostname"
      * path (read/write)
      * path_quoted (read/write)
        A URI quoted version of path
      * params (dict) (read/write)
      * query (dict) (read/write)
      * relative (bool) (read only)
        True if this is a "relative URI", (e.g. file:foo.diff)

    It stringifies to the URI itself.

    Some notes about relative URIs: while it's specified that
    a URI beginning with <scheme>:// should either be directly
    followed by a hostname or a /, the old URI handling of the
    fetch2 library did not comform to this. Therefore, this URI
    class has some kludges to make sure that URIs are parsed in
    a way comforming to bitbake's current usage. This URI class
    supports the following:

     file:relative/path.diff (IETF compliant)
     git:relative/path.git (IETF compliant)
     git:///absolute/path.git (IETF compliant)
     file:///absolute/path.diff (IETF compliant)

     file://relative/path.diff (not IETF compliant)

    But it does not support the following:

     file://hostname/absolute/path.diff (would be IETF compliant)

    Note that the last case only applies to a list of
    "whitelisted" schemes (currently only file://), that requires
    its URIs to not have a network location.
    """

    _relative_schemes = ['file', 'git']
    _netloc_forbidden = ['file']

    def __init__(self, uri=None):
        self.scheme = ''
        self.userinfo = ''
        self.hostname = ''
        self.port = None
        self._path = ''
        self.params = {}
        self.query = {}
        self.relative = False

        if not uri:
            return

        # We hijack the URL parameters, since the way bitbake uses
        # them are not quite RFC compliant.
        uri, param_str = (uri.split(";", 1) + [None])[:2]

        urlp = urlparse.urlparse(uri)
        self.scheme = urlp.scheme

        reparse = 0

        # Coerce urlparse to make URI scheme use netloc
        if not self.scheme in urlparse.uses_netloc:
            urlparse.uses_params.append(self.scheme)
            reparse = 1

        # Make urlparse happy(/ier) by converting local resources
        # to RFC compliant URL format. E.g.:
        #   file://foo.diff -> file:foo.diff
        if urlp.scheme in self._netloc_forbidden:
            uri = re.sub("(?<=:)//(?!/)", "", uri, 1)
            reparse = 1

        if reparse:
            urlp = urlparse.urlparse(uri)

        # Identify if the URI is relative or not
        if urlp.scheme in self._relative_schemes and \
           re.compile("^\w+:(?!//)").match(uri):
            self.relative = True

        if not self.relative:
            self.hostname = urlp.hostname or ''
            self.port = urlp.port

            self.userinfo += urlp.username or ''

            if urlp.password:
                self.userinfo += ':%s' % urlp.password

        self.path = urllib.unquote(urlp.path)

        if param_str:
            self.params = self._param_str_split(param_str, ";")
        if urlp.query:
            self.query = self._param_str_split(urlp.query, "&")

    def __str__(self):
        userinfo = self.userinfo
        if userinfo:
            userinfo += '@'

        return "%s:%s%s%s%s%s%s" % (
            self.scheme,
            '' if self.relative else '//',
            userinfo,
            self.hostport,
            self.path_quoted,
            self._query_str(),
            self._param_str())

    def _param_str(self):
        return (
            ''.join([';', self._param_str_join(self.params, ";")])
            if self.params else '')

    def _query_str(self):
        return (
            ''.join(['?', self._param_str_join(self.query, "&")])
            if self.query else '')

    def _param_str_split(self, string, elmdelim, kvdelim="="):
        ret = {}
        for k, v in [x.split(kvdelim, 1) for x in string.split(elmdelim)]:
            ret[k] = v
        return ret

    def _param_str_join(self, dict_, elmdelim, kvdelim="="):
        return elmdelim.join([kvdelim.join([k, v]) for k, v in dict_.items()])

    @property
    def hostport(self):
        if not self.port:
            return self.hostname
        return "%s:%d" % (self.hostname, self.port)

    @property
    def path_quoted(self):
        return urllib.quote(self.path)

    @path_quoted.setter
    def path_quoted(self, path):
        self.path = urllib.unquote(path)

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path):
        self._path = path

        if re.compile("^/").match(path):
            self.relative = False
        else:
            self.relative = True

    @property
    def username(self):
        if self.userinfo:
            return (self.userinfo.split(":", 1))[0]
        return ''

    @username.setter
    def username(self, username):
        password = self.password
        self.userinfo = username
        if password:
            self.userinfo += ":%s" % password

    @property
    def password(self):
        if self.userinfo and ":" in self.userinfo:
            return (self.userinfo.split(":", 1))[1]
        return ''

    @password.setter
    def password(self, password):
        self.userinfo = "%s:%s" % (self.username, password)

def decodeurl(url):
    """Decodes an URL into the tokens (scheme, network location, path,
    user, password, parameters).
    """

    m = re.compile('(?P<type>[^:]*)://((?P<user>[^/]+)@)?(?P<location>[^;]+)(;(?P<parm>.*))?').match(url)
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
            if s:
                if not '=' in s:
                    raise MalformedUrl(url, "The URL: '%s' is invalid: parameter %s does not specify a value (missing '=')" % (url, s))
                s1, s2 = s.split('=')
                p[s1] = s2

    return type, host, urllib.unquote(path), user, pswd, p

def encodeurl(decoded):
    """Encodes a URL from tokens (scheme, network location, path,
    user, password, parameters).
    """

    type, host, path, user, pswd, p = decoded

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
    # Standardise path to ensure comparisons work
    while '//' in path:
        path = path.replace("//", "/")
    url += "%s" % urllib.quote(path)
    if p:
        for parm in p:
            url += ";%s=%s" % (parm, p[parm])

    return url

def uri_replace(ud, uri_find, uri_replace, replacements, d):
    if not ud.url or not uri_find or not uri_replace:
        logger.error("uri_replace: passed an undefined value, not replacing")
        return None
    uri_decoded = list(decodeurl(ud.url))
    uri_find_decoded = list(decodeurl(uri_find))
    uri_replace_decoded = list(decodeurl(uri_replace))
    logger.debug(2, "For url %s comparing %s to %s" % (uri_decoded, uri_find_decoded, uri_replace_decoded))
    result_decoded = ['', '', '', '', '', {}]
    for loc, i in enumerate(uri_find_decoded):
        result_decoded[loc] = uri_decoded[loc]
        regexp = i
        if loc == 0 and regexp and not regexp.endswith("$"):
            # Leaving the type unanchored can mean "https" matching "file" can become "files"
            # which is clearly undesirable.
            regexp += "$"
        if loc == 5:
            # Handle URL parameters
            if i:
                # Any specified URL parameters must match
                for k in uri_replace_decoded[loc]:
                    if uri_decoded[loc][k] != uri_replace_decoded[loc][k]:
                        return None
            # Overwrite any specified replacement parameters
            for k in uri_replace_decoded[loc]:
                for l in replacements:
                    uri_replace_decoded[loc][k] = uri_replace_decoded[loc][k].replace(l, replacements[l])
                result_decoded[loc][k] = uri_replace_decoded[loc][k]
        elif (re.match(regexp, uri_decoded[loc])):
            if not uri_replace_decoded[loc]:
                result_decoded[loc] = ""    
            else:
                for k in replacements:
                    uri_replace_decoded[loc] = uri_replace_decoded[loc].replace(k, replacements[k])
                #bb.note("%s %s %s" % (regexp, uri_replace_decoded[loc], uri_decoded[loc]))
                result_decoded[loc] = re.sub(regexp, uri_replace_decoded[loc], uri_decoded[loc])
            if loc == 2:
                # Handle path manipulations
                basename = None
                if uri_decoded[0] != uri_replace_decoded[0] and ud.mirrortarball:
                    # If the source and destination url types differ, must be a mirrortarball mapping
                    basename = os.path.basename(ud.mirrortarball)
                    # Kill parameters, they make no sense for mirror tarballs
                    uri_decoded[5] = {}
                elif ud.localpath and ud.method.supports_checksum(ud):
                    basename = os.path.basename(ud.localpath)
                if basename and not result_decoded[loc].endswith(basename):
                    result_decoded[loc] = os.path.join(result_decoded[loc], basename)
        else:
            return None
    result = encodeurl(result_decoded)
    if result == ud.url:
        return None
    logger.debug(2, "For url %s returning %s" % (ud.url, result))
    return result

methods = []
urldata_cache = {}
saved_headrevs = {}

def fetcher_init(d):
    """
    Called to initialize the fetchers once the configuration data is known.
    Calls before this must not hit the cache.
    """
    # When to drop SCM head revisions controlled by user policy
    srcrev_policy = d.getVar('BB_SRCREV_POLICY', True) or "clear"
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

    _checksum_cache.init_cache(d)

    for m in methods:
        if hasattr(m, "init"):
            m.init(d)

def fetcher_parse_save(d):
    _checksum_cache.save_extras(d)

def fetcher_parse_done(d):
    _checksum_cache.save_merge(d)

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

def verify_checksum(ud, d):
    """
    verify the MD5 and SHA256 checksum for downloaded src

    Raises a FetchError if one or both of the SRC_URI checksums do not match
    the downloaded file, or if BB_STRICT_CHECKSUM is set and there are no
    checksums specified.

    """

    if ud.ignore_checksums or not ud.method.supports_checksum(ud):
        return

    md5data = bb.utils.md5_file(ud.localpath)
    sha256data = bb.utils.sha256_file(ud.localpath)

    if ud.method.recommends_checksum(ud):
        # If strict checking enabled and neither sum defined, raise error
        strict = d.getVar("BB_STRICT_CHECKSUM", True) or "0"
        if (strict == "1") and not (ud.md5_expected or ud.sha256_expected):
            logger.error('No checksum specified for %s, please add at least one to the recipe:\n'
                             'SRC_URI[%s] = "%s"\nSRC_URI[%s] = "%s"' %
                             (ud.localpath, ud.md5_name, md5data,
                              ud.sha256_name, sha256data))
            raise NoChecksumError('Missing SRC_URI checksum', ud.url)

        # Log missing sums so user can more easily add them
        if not ud.md5_expected:
            logger.warn('Missing md5 SRC_URI checksum for %s, consider adding to the recipe:\n'
                        'SRC_URI[%s] = "%s"',
                        ud.localpath, ud.md5_name, md5data)

        if not ud.sha256_expected:
            logger.warn('Missing sha256 SRC_URI checksum for %s, consider adding to the recipe:\n'
                        'SRC_URI[%s] = "%s"',
                        ud.localpath, ud.sha256_name, sha256data)

    md5mismatch = False
    sha256mismatch = False

    if ud.md5_expected != md5data:
        md5mismatch = True

    if ud.sha256_expected != sha256data:
        sha256mismatch = True

    # We want to alert the user if a checksum is defined in the recipe but
    # it does not match.
    msg = ""
    mismatch = False
    if md5mismatch and ud.md5_expected:
        msg = msg + "\nFile: '%s' has %s checksum %s when %s was expected" % (ud.localpath, 'md5', md5data, ud.md5_expected)
        mismatch = True;

    if sha256mismatch and ud.sha256_expected:
        msg = msg + "\nFile: '%s' has %s checksum %s when %s was expected" % (ud.localpath, 'sha256', sha256data, ud.sha256_expected)
        mismatch = True;

    if mismatch:
        msg = msg + '\nIf this change is expected (e.g. you have upgraded to a new version without updating the checksums) then you can use these lines within the recipe:\nSRC_URI[%s] = "%s"\nSRC_URI[%s] = "%s"\nOtherwise you should retry the download and/or check with upstream to determine if the file has become corrupted or otherwise unexpectedly modified.\n' % (ud.md5_name, md5data, ud.sha256_name, sha256data)

    if len(msg):
        raise ChecksumError('Checksum mismatch!%s' % msg, ud.url, md5data)


def update_stamp(ud, d):
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
        verify_checksum(ud, d)
        open(ud.donestamp, 'w').close()

def subprocess_setup():
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    # SIGPIPE errors are known issues with gzip/bash
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def get_autorev(d):
    #  only not cache src rev in autorev case
    if d.getVar('BB_SRCREV_POLICY', True) != "cache":
        d.setVar('__BB_DONT_CACHE', '1')
    return "AUTOINC"

def get_srcrev(d):
    """
    Return the revsion string, usually for use in the version string (PV) of the current package
    Most packages usually only have one SCM so we just pass on the call.
    In the multi SCM case, we build a value based on SRCREV_FORMAT which must
    have been set.

    The idea here is that we put the string "AUTOINC+" into return value if the revisions are not 
    incremental, other code is then responsible for turning that into an increasing value (if needed)
    """

    scms = []
    fetcher = Fetch(d.getVar('SRC_URI', True).split(), d)
    urldata = fetcher.ud
    for u in urldata:
        if urldata[u].method.supports_srcrev():
            scms.append(u)

    if len(scms) == 0:
        raise FetchError("SRCREV was used yet no valid SCM was found in SRC_URI")

    if len(scms) == 1 and len(urldata[scms[0]].names) == 1:
        autoinc, rev = urldata[scms[0]].method.sortable_revision(urldata[scms[0]], d, urldata[scms[0]].names[0])
        if len(rev) > 10:
            rev = rev[:10]
        if autoinc:
            return "AUTOINC+" + rev
        return rev

    #
    # Mutiple SCMs are in SRC_URI so we resort to SRCREV_FORMAT
    #
    format = d.getVar('SRCREV_FORMAT', True)
    if not format:
        raise FetchError("The SRCREV_FORMAT variable must be set when multiple SCMs are used.")

    seenautoinc = False
    for scm in scms:
        ud = urldata[scm]
        for name in ud.names:
            autoinc, rev = ud.method.sortable_revision(ud, d, name)
            seenautoinc = seenautoinc or autoinc
            if len(rev) > 10:
                rev = rev[:10]
            format = format.replace(name, rev)
    if seenautoinc:
       format = "AUTOINC+" + format

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
    exportvars = ['HOME', 'PATH',
                  'HTTP_PROXY', 'http_proxy',
                  'HTTPS_PROXY', 'https_proxy',
                  'FTP_PROXY', 'ftp_proxy',
                  'FTPS_PROXY', 'ftps_proxy',
                  'NO_PROXY', 'no_proxy',
                  'ALL_PROXY', 'all_proxy',
                  'GIT_PROXY_COMMAND',
                  'SSH_AUTH_SOCK', 'SSH_AGENT_PID',
                  'SOCKS5_USER', 'SOCKS5_PASSWD']

    for var in exportvars:
        val = d.getVar(var, True)
        if val:
            cmd = 'export ' + var + '=\"%s\"; %s' % (val, cmd)

    logger.debug(1, "Running %s", cmd)

    success = False
    error_message = ""

    try:
        (output, errors) = bb.process.run(cmd, shell=True, stderr=subprocess.PIPE)
        success = True
    except bb.process.NotFoundError as e:
        error_message = "Fetch command %s" % (e.command)
    except bb.process.ExecutionError as e:
        if e.stdout:
            output = "output:\n%s\n%s" % (e.stdout, e.stderr)
        elif e.stderr:
            output = "output:\n%s" % e.stderr
        else:
            output = "no output"
        error_message = "Fetch command failed with exit code %s, %s" % (e.exitcode, output)
    except bb.process.CmdError as e:
        error_message = "Fetch command %s could not be run:\n%s" % (e.command, e.msg)
    if not success:
        for f in cleanup:
            try:
                bb.utils.remove(f, True)
            except OSError:
                pass

        raise FetchError(error_message)

    return output

def check_network_access(d, info = "", url = None):
    """
    log remote network access, and error if BB_NO_NETWORK is set
    """
    if d.getVar("BB_NO_NETWORK", True) == "1":
        raise NetworkAccess(url, info)
    else:
        logger.debug(1, "Fetcher accessed the network with the command %s" % info)

def build_mirroruris(origud, mirrors, ld):
    uris = []
    uds = []

    replacements = {}
    replacements["TYPE"] = origud.type
    replacements["HOST"] = origud.host
    replacements["PATH"] = origud.path
    replacements["BASENAME"] = origud.path.split("/")[-1]
    replacements["MIRRORNAME"] = origud.host.replace(':','.') + origud.path.replace('/', '.').replace('*', '.')

    def adduri(ud, uris, uds):
        for line in mirrors:
            try:
                (find, replace) = line
            except ValueError:
                continue
            newuri = uri_replace(ud, find, replace, replacements, ld)
            if not newuri or newuri in uris or newuri == origud.url:
                continue
            try:
                newud = FetchData(newuri, ld)
                newud.setup_localpath(ld)
            except bb.fetch2.BBFetchException as e:
                logger.debug(1, "Mirror fetch failure for url %s (original url: %s)" % (newuri, origud.url))
                logger.debug(1, str(e))
                try:
                    ud.method.clean(ud, ld)
                except UnboundLocalError:
                    pass
                continue   
            uris.append(newuri)
            uds.append(newud)

            adduri(newud, uris, uds)

    adduri(origud, uris, uds)

    return uris, uds

def rename_bad_checksum(ud, suffix):
    """
    Renames files to have suffix from parameter
    """

    if ud.localpath is None:
        return

    new_localpath = "%s_bad-checksum_%s" % (ud.localpath, suffix)
    bb.warn("Renaming %s to %s" % (ud.localpath, new_localpath))
    bb.utils.movefile(ud.localpath, new_localpath)

def safe_symlink(source, link_name):
    if not os.path.exists(link_name):
        if os.path.islink(link_name):
            os.unlink(link_name)

        os.symlink(source, link_name)
    return

def try_mirror_url(origud, ud, ld, check = False):
    # Return of None or a value means we're finished
    # False means try another url
    try:
        if check:
            found = ud.method.checkstatus(ud, ld)
            if found:
                return found
            return False

        os.chdir(ld.getVar("DL_DIR", True))

        if not os.path.exists(ud.donestamp) or ud.method.need_update(ud, ld):
            ud.method.download(ud, ld)
            if hasattr(ud.method,"build_mirror_data"):
                ud.method.build_mirror_data(ud, ld)

        if not ud.localpath or not os.path.exists(ud.localpath):
            return False

        if ud.localpath == origud.localpath:
            return ud.localpath

        # We may be obtaining a mirror tarball which needs further processing by the real fetcher
        # If that tarball is a local file:// we need to provide a symlink to it
        dldir = ld.getVar("DL_DIR", True)
        if origud.mirrortarball and os.path.basename(ud.localpath) == os.path.basename(origud.mirrortarball) \
                and os.path.basename(ud.localpath) != os.path.basename(origud.localpath):
            bb.utils.mkdirhier(os.path.dirname(ud.donestamp))
            open(ud.donestamp, 'w').close()
            dest = os.path.join(dldir, os.path.basename(ud.localpath)) 
            safe_symlink(ud.localpath, dest)

            if not os.path.exists(origud.donestamp) or origud.method.need_update(origud, ld):
                origud.method.download(origud, ld)
                if hasattr(origud.method,"build_mirror_data"):
                    origud.method.build_mirror_data(origud, ld)
            return ud.localpath

        # Otherwise the result is a local file:// and we symlink to it
        safe_symlink(ud.localpath, origud.localpath)

        update_stamp(origud, ld)
        return ud.localpath

    except bb.fetch2.NetworkAccess:
        raise

    except bb.fetch2.BBFetchException as e:
        if isinstance(e, ChecksumError):
            logger.warn("Mirror checksum failure for url %s (original url: %s)\nCleaning and trying again." % (ud.url, origud.url))
            logger.warn(str(e))
            rename_bad_checksum(ud, e.checksum)
        elif isinstance(e, NoChecksumError):
            raise
        else:
            logger.debug(1, "Mirror fetch failure for url %s (original url: %s)" % (ud.url, origud.url))
            logger.debug(1, str(e))
        try:
            ud.method.clean(ud, ld)
        except UnboundLocalError:
            pass
        return False

def try_mirrors(d, origud, mirrors, check = False):
    """
    Try to use a mirrored version of the sources.
    This method will be automatically called before the fetchers go.

    d Is a bb.data instance
    uri is the original uri we're trying to download
    mirrors is the list of mirrors we're going to try
    """
    ld = d.createCopy()

    uris, uds = build_mirroruris(origud, mirrors, ld)

    for index, uri in enumerate(uris):
        ret = try_mirror_url(origud, uds[index], ld, check)
        if ret != False:
            return ret
    return None

def srcrev_internal_helper(ud, d, name):
    """
    Return:
        a) a source revision if specified
        b) latest revision if SRCREV="AUTOINC"
        c) None if not specified
    """

    srcrev = None
    pn = d.getVar("PN", True)
    attempts = []
    if name != '' and pn:
        attempts.append("SRCREV_%s_pn-%s" % (name, pn))
    if name != '':
        attempts.append("SRCREV_%s" % name)
    if pn:
        attempts.append("SRCREV_pn-%s" % pn)
    attempts.append("SRCREV")

    for a in attempts:
        srcrev = d.getVar(a, True)              
        if srcrev and srcrev != "INVALID":
            break

    if 'rev' in ud.parm and 'tag' in ud.parm:
        raise FetchError("Please specify a ;rev= parameter or a ;tag= parameter in the url %s but not both." % (ud.url))

    if 'rev' in ud.parm or 'tag' in ud.parm:
        if 'rev' in ud.parm:
            parmrev = ud.parm['rev']
        else:
            parmrev = ud.parm['tag']
        if srcrev == "INVALID" or not srcrev:
            return parmrev
        if srcrev != parmrev:
            raise FetchError("Conflicting revisions (%s from SRCREV and %s from the url) found, please spcify one valid value" % (srcrev, parmrev))
        return parmrev

    if srcrev == "INVALID" or not srcrev:
        raise FetchError("Please set a valid SRCREV for url %s (possible key names are %s, or use a ;rev=X URL parameter)" % (str(attempts), ud.url), ud.url)
    if srcrev == "AUTOINC":
        srcrev = ud.method.latest_revision(ud, d, name)

    return srcrev

def get_checksum_file_list(d):
    """ Get a list of files checksum in SRC_URI

    Returns the resolved local paths of all local file entries in
    SRC_URI as a space-separated string
    """
    fetch = Fetch([], d, cache = False, localonly = True)

    dl_dir = d.getVar('DL_DIR', True)
    filelist = []
    for u in fetch.urls:
        ud = fetch.ud[u]

        if ud and isinstance(ud.method, local.Local):
            paths = ud.method.localpaths(ud, d)
            for f in paths:
                pth = ud.decodedurl
                if '*' in pth:
                    f = os.path.join(os.path.abspath(f), pth)
                if f.startswith(dl_dir):
                    # The local fetcher's behaviour is to return a path under DL_DIR if it couldn't find the file anywhere else
                    if os.path.exists(f):
                        bb.warn("Getting checksum for %s SRC_URI entry %s: file not found except in DL_DIR" % (d.getVar('PN', True), os.path.basename(f)))
                    else:
                        bb.warn("Unable to get checksum for %s SRC_URI entry %s: file could not be found" % (d.getVar('PN', True), os.path.basename(f)))
                filelist.append(f + ":" + str(os.path.exists(f)))

    return " ".join(filelist)

def get_file_checksums(filelist, pn):
    """Get a list of the checksums for a list of local files

    Returns the checksums for a list of local files, caching the results as
    it proceeds

    """

    def checksum_file(f):
        try:
            checksum = _checksum_cache.get_checksum(f)
        except OSError as e:
            bb.warn("Unable to get checksum for %s SRC_URI entry %s: %s" % (pn, os.path.basename(f), e))
            return None
        return checksum

    def checksum_dir(pth):
        # Handle directories recursively
        dirchecksums = []
        for root, dirs, files in os.walk(pth):
            for name in files:
                fullpth = os.path.join(root, name)
                checksum = checksum_file(fullpth)
                if checksum:
                    dirchecksums.append((fullpth, checksum))
        return dirchecksums

    checksums = []
    for pth in filelist.split():
        exist = pth.split(":")[1]
        if exist == "False":
            continue
        pth = pth.split(":")[0]
        if '*' in pth:
            # Handle globs
            for f in glob.glob(pth):
                if os.path.isdir(f):
                    checksums.extend(checksum_dir(f))
                else:
                    checksum = checksum_file(f)
                    checksums.append((f, checksum))
        elif os.path.isdir(pth):
            checksums.extend(checksum_dir(pth))
        else:
            checksum = checksum_file(pth)
            checksums.append((pth, checksum))

    checksums.sort(key=operator.itemgetter(1))
    return checksums


class FetchData(object):
    """
    A class which represents the fetcher state for a given URI.
    """
    def __init__(self, url, d, localonly = False):
        # localpath is the location of a downloaded result. If not set, the file is local.
        self.donestamp = None
        self.localfile = ""
        self.localpath = None
        self.lockfile = None
        self.mirrortarball = None
        self.basename = None
        self.basepath = None
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
        if self.md5_name in self.parm:
            self.md5_expected = self.parm[self.md5_name]
        elif self.type not in ["http", "https", "ftp", "ftps", "sftp"]:
            self.md5_expected = None
        else:
            self.md5_expected = d.getVarFlag("SRC_URI", self.md5_name)
        if self.sha256_name in self.parm:
            self.sha256_expected = self.parm[self.sha256_name]
        elif self.type not in ["http", "https", "ftp", "ftps", "sftp"]:
            self.sha256_expected = None
        else:
            self.sha256_expected = d.getVarFlag("SRC_URI", self.sha256_name)
        self.ignore_checksums = False

        self.names = self.parm.get("name",'default').split(',')

        self.method = None
        for m in methods:
            if m.supports(self, d):
                self.method = m
                break                

        if not self.method:
            raise NoMethodError(url)

        if localonly and not isinstance(self.method, local.Local):
            raise NonLocalMethod()

        if self.parm.get("proto", None) and "protocol" not in self.parm:
            logger.warn('Consider updating %s recipe to use "protocol" not "proto" in SRC_URI.', d.getVar('PN', True))
            self.parm["protocol"] = self.parm.get("proto", None)

        if hasattr(self.method, "urldata_init"):
            self.method.urldata_init(self, d)

        if "localpath" in self.parm:
            # if user sets localpath for file, use it instead.
            self.localpath = self.parm["localpath"]
            self.basename = os.path.basename(self.localpath)
        elif self.localfile:
            self.localpath = self.method.localpath(self, d)

        dldir = d.getVar("DL_DIR", True)
        # Note: .done and .lock files should always be in DL_DIR whereas localpath may not be.
        if self.localpath and self.localpath.startswith(dldir):
            basepath = self.localpath
        elif self.localpath:
            basepath = dldir + os.sep + os.path.basename(self.localpath)
        else:
            basepath = dldir + os.sep + (self.basepath or self.basename)
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
            self.localpath = self.method.localpath(self, d)

    def getSRCDate(self, d):
        """
        Return the SRC Date for the component

        d the bb.data module
        """
        if "srcdate" in self.parm:
            return self.parm['srcdate']

        pn = d.getVar("PN", True)

        if pn:
            return d.getVar("SRCDATE_%s" % pn, True) or d.getVar("SRCDATE", True) or d.getVar("DATE", True)

        return d.getVar("SRCDATE", True) or d.getVar("DATE", True)

class FetchMethod(object):
    """Base class for 'fetch'ing data"""

    def __init__(self, urls = []):
        self.urls = []

    def supports(self, urldata, d):
        """
        Check to see if this fetch class supports a given url.
        """
        return 0

    def localpath(self, urldata, d):
        """
        Return the local filename of a given url assuming a successful fetch.
        Can also setup variables in urldata for use in go (saving code duplication
        and duplicate code execution)
        """
        return os.path.join(data.getVar("DL_DIR", d, True), urldata.localfile)

    def supports_checksum(self, urldata):
        """
        Is localpath something that can be represented by a checksum?
        """

        # We cannot compute checksums for directories
        if os.path.isdir(urldata.localpath) == True:
            return False
        if urldata.localpath.find("*") != -1:
             return False

        return True

    def recommends_checksum(self, urldata):
        """
        Is the backend on where checksumming is recommended (should warnings 
        be displayed if there is no checksum)?
        """
        return False

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

    def need_update(self, ud, d):
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

    def download(self, urldata, d):
        """
        Fetch urls
        Assumes localpath was called first
        """
        raise NoMethodError(url)

    def unpack(self, urldata, rootdir, data):
        iterate = False
        file = urldata.localpath

        try:
            unpack = bb.utils.to_boolean(urldata.parm.get('unpack'), True)
        except ValueError as exc:
            bb.fatal("Invalid value for 'unpack' parameter for %s: %s" %
                     (file, urldata.parm.get('unpack')))

        base, ext = os.path.splitext(file)
        if ext in ['.gz', '.bz2', '.Z', '.xz', '.lz']:
            efile = os.path.join(rootdir, os.path.basename(base))
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
            elif file.endswith('.tar.lz'):
                cmd = 'lzip -dc %s | tar x --no-same-owner -f -' % file
            elif file.endswith('.lz'):
                cmd = 'lzip -dc %s > %s' % (file, efile)
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
            elif file.endswith('.rpm') or file.endswith('.srpm'):
                if 'extract' in urldata.parm:
                    unpack_file = urldata.parm.get('extract')
                    cmd = 'rpm2cpio.sh %s | cpio -id %s' % (file, unpack_file)
                    iterate = True
                    iterate_file = unpack_file
                else:
                    cmd = 'rpm2cpio.sh %s | cpio -id' % (file)
            elif file.endswith('.deb') or file.endswith('.ipk'):
                cmd = 'ar -p %s data.tar.gz | zcat | tar --no-same-owner -xpf -' % file

        if not unpack or not cmd:
            # If file == dest, then avoid any copies, as we already put the file into dest!
            dest = os.path.join(rootdir, os.path.basename(file))
            if (file != dest) and not (os.path.exists(dest) and os.path.samefile(file, dest)):
                if os.path.isdir(file):
                    # If for example we're asked to copy file://foo/bar, we need to unpack the result into foo/bar
                    basepath = getattr(urldata, "basepath", None)
                    destdir = "."
                    if basepath and basepath.endswith("/"):
                        basepath = basepath.rstrip("/")
                    elif basepath:
                        basepath = os.path.dirname(basepath)
                    if basepath and basepath.find("/") != -1:
                        destdir = basepath[:basepath.rfind('/')]
                        destdir = destdir.strip('/')
                    if destdir != "." and not os.access("%s/%s" % (rootdir, destdir), os.F_OK):
                        os.makedirs("%s/%s" % (rootdir, destdir))
                    cmd = 'cp -fpPR %s %s/%s/' % (file, rootdir, destdir)
                    #cmd = 'tar -cf - -C "%d" -ps . | tar -xf - -C "%s/%s/"' % (file, rootdir, destdir)
                else:
                    # The "destdir" handling was specifically done for FILESPATH
                    # items.  So, only do so for file:// entries.
                    if urldata.type == "file" and urldata.path.find("/") != -1:
                       destdir = urldata.path.rsplit("/", 1)[0]
                       if urldata.parm.get('subdir') != None:
                          destdir = urldata.parm.get('subdir') + "/" + destdir
                    else:
                       if urldata.parm.get('subdir') != None:
                          destdir = urldata.parm.get('subdir')
                       else:
                          destdir = "."
                    bb.utils.mkdirhier("%s/%s" % (rootdir, destdir))
                    cmd = 'cp -f %s %s/%s/' % (file, rootdir, destdir)

        if not cmd:
            return

        # Change to subdir before executing command
        save_cwd = os.getcwd();
        os.chdir(rootdir)
        if 'subdir' in urldata.parm:
            newdir = ("%s/%s" % (rootdir, urldata.parm.get('subdir')))
            bb.utils.mkdirhier(newdir)
            os.chdir(newdir)

        path = data.getVar('PATH', True)
        if path:
            cmd = "PATH=\"%s\" %s" % (path, cmd)
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

    def try_premirror(self, urldata, d):
        """
        Should premirrors be used?
        """
        return True

    def checkstatus(self, urldata, d):
        """
        Check the status of a URL
        Assumes localpath was called first
        """
        logger.info("URL %s could not be checked for status since no method exists.", url)
        return True

    def latest_revision(self, ud, d, name):
        """
        Look in the cache for the latest revision, if not present ask the SCM.
        """
        if not hasattr(self, "_latest_revision"):
            raise ParameterError("The fetcher for this URL does not support _latest_revision", url)

        revs = bb.persist_data.persist('BB_URI_HEADREVS', d)
        key = self.generate_revision_key(ud, d, name)
        try:
            return revs[key]
        except KeyError:
            revs[key] = rev = self._latest_revision(ud, d, name)
            return rev

    def sortable_revision(self, ud, d, name):
        latest_rev = self._build_revision(ud, d, name)
        return True, str(latest_rev)

    def generate_revision_key(self, ud, d, name):
        key = self._revision_key(ud, d, name)
        return "%s-%s" % (key, d.getVar("PN", True) or "")

class Fetch(object):
    def __init__(self, urls, d, cache = True, localonly = False):
        if localonly and cache:
            raise Exception("bb.fetch2.Fetch.__init__: cannot set cache and localonly at same time")

        if len(urls) == 0:
            urls = d.getVar("SRC_URI", True).split()
        self.urls = urls
        self.d = d
        self.ud = {}

        fn = d.getVar('FILE', True)
        if cache and fn and fn in urldata_cache:
            self.ud = urldata_cache[fn]

        for url in urls:
            if url not in self.ud:
                try:
                    self.ud[url] = FetchData(url, d, localonly)
                except NonLocalMethod:
                    if localonly:
                        self.ud[url] = None
                        pass

        if fn and cache:
            urldata_cache[fn] = self.ud

    def localpath(self, url):
        if url not in self.urls:
            self.ud[url] = FetchData(url, self.d)

        self.ud[url].setup_localpath(self.d)
        return self.d.expand(self.ud[url].localpath)

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

        network = self.d.getVar("BB_NO_NETWORK", True)
        premirroronly = (self.d.getVar("BB_FETCH_PREMIRRORONLY", True) == "1")

        for u in urls:
            ud = self.ud[u]
            ud.setup_localpath(self.d)
            m = ud.method
            localpath = ""

            lf = bb.utils.lockfile(ud.lockfile)

            try:
                self.d.setVar("BB_NO_NETWORK", network)
 
                if os.path.exists(ud.donestamp) and not m.need_update(ud, self.d):
                    localpath = ud.localpath
                elif m.try_premirror(ud, self.d):
                    logger.debug(1, "Trying PREMIRRORS")
                    mirrors = mirror_from_string(self.d.getVar('PREMIRRORS', True))
                    localpath = try_mirrors(self.d, ud, mirrors, False)

                if premirroronly:
                    self.d.setVar("BB_NO_NETWORK", "1")

                os.chdir(self.d.getVar("DL_DIR", True))

                firsterr = None
                if not localpath and ((not os.path.exists(ud.donestamp)) or m.need_update(ud, self.d)):
                    try:
                        logger.debug(1, "Trying Upstream")
                        m.download(ud, self.d)
                        if hasattr(m, "build_mirror_data"):
                            m.build_mirror_data(ud, self.d)
                        localpath = ud.localpath
                        # early checksum verify, so that if checksum mismatched,
                        # fetcher still have chance to fetch from mirror
                        update_stamp(ud, self.d)

                    except bb.fetch2.NetworkAccess:
                        raise

                    except BBFetchException as e:
                        if isinstance(e, ChecksumError):
                            logger.warn("Checksum failure encountered with download of %s - will attempt other sources if available" % u)
                            logger.debug(1, str(e))
                            rename_bad_checksum(ud, e.checksum)
                        elif isinstance(e, NoChecksumError):
                            raise
                        else:
                            logger.warn('Failed to fetch URL %s, attempting MIRRORS if available' % u)
                            logger.debug(1, str(e))
                        firsterr = e
                        # Remove any incomplete fetch
                        m.clean(ud, self.d)
                        logger.debug(1, "Trying MIRRORS")
                        mirrors = mirror_from_string(self.d.getVar('MIRRORS', True))
                        localpath = try_mirrors (self.d, ud, mirrors)

                if not localpath or ((not os.path.exists(localpath)) and localpath.find("*") == -1):
                    if firsterr:
                        logger.error(str(firsterr))
                    raise FetchError("Unable to fetch URL from any source.", u)

                update_stamp(ud, self.d)

            except BBFetchException as e:
                if isinstance(e, ChecksumError):
                    logger.error("Checksum failure fetching %s" % u)
                raise

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
            mirrors = mirror_from_string(self.d.getVar('PREMIRRORS', True))
            ret = try_mirrors(self.d, ud, mirrors, True)
            if not ret:
                # Next try checking from the original uri, u
                try:
                    ret = m.checkstatus(ud, self.d)
                except:
                    # Finally, try checking uri, u, from MIRRORS
                    mirrors = mirror_from_string(self.d.getVar('MIRRORS', True))
                    ret = try_mirrors(self.d, ud, mirrors, True)

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

            if self.d.expand(self.localpath) is None:
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

            if not ud.localfile and ud.localpath is None:
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
from . import gitsm
from . import gitannex
from . import local
from . import svn
from . import wget
from . import ssh
from . import sftp
from . import perforce
from . import bzr
from . import hg
from . import osc
from . import repo
from . import clearcase

methods.append(local.Local())
methods.append(wget.Wget())
methods.append(svn.Svn())
methods.append(git.Git())
methods.append(gitsm.GitSM())
methods.append(gitannex.GitANNEX())
methods.append(cvs.Cvs())
methods.append(ssh.SSH())
methods.append(sftp.SFTP())
methods.append(perforce.Perforce())
methods.append(bzr.Bzr())
methods.append(hg.Hg())
methods.append(osc.Osc())
methods.append(repo.Repo())
methods.append(clearcase.ClearCase())
