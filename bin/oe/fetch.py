#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
OpenEmbedded 'Fetch' implementations

Classes for obtaining upstream sources for the
OpenEmbedded (http://openembedded.org) build infrastructure.

NOTE that it requires Python 2.x due to its use of static methods.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

import os, re
import oe
import oe.data

class FetchError(Exception):
    """Exception raised when a download fails"""

class NoMethodError(Exception):
    """Exception raised when there is no method to obtain a supplied url or set of urls"""

class MissingParameterError(Exception):
    """Exception raised when a fetch method is missing a critical parameter in the url"""

#decodeurl("cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;module=familiar/dist/ipkg;tag=V0-99-81")
#('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'})

def uri_replace(uri, uri_find, uri_replace, d = oe.data.init()):
#   oe.note("uri_replace: operating on %s" % uri)
    if not uri or not uri_find or not uri_replace:
        oe.debug(1, "uri_replace: passed an undefined value, not replacing")
    uri_decoded = list(oe.decodeurl(uri))
    uri_find_decoded = list(oe.decodeurl(uri_find))
    uri_replace_decoded = list(oe.decodeurl(uri_replace))
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
                        localfn = oe.fetch.localpath(uri, d)
                        if localfn:
                            result_decoded[loc] = os.path.dirname(result_decoded[loc]) + "/" + os.path.basename(oe.fetch.localpath(uri, d))
#                       oe.note("uri_replace: matching %s against %s and replacing with %s" % (i, uri_decoded[loc], uri_replace_decoded[loc]))
            else:
#               oe.note("uri_replace: no match")
                return uri
#           else:
#               for j in i.keys():
#                   FIXME: apply replacements against options
    return oe.encodeurl(result_decoded)

methods = []

def init(urls = [], d = oe.data.init()):
    for m in methods:
        m.urls = []

    for u in urls:
        for m in methods:
            m.data = d
            if m.supports(u, d):
                m.urls.append(u)

def go(d = oe.data.init()):
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

def localpath(url, d = oe.data.init()):
    for m in methods:
        if m.supports(url, d):
            return m.localpath(url, d)
    return url

class Fetch(object):
    """Base class for 'fetch'ing data"""

    def __init__(self, urls = []):
        self.urls = []
        for url in urls:
            if self.supports(oe.decodeurl(url), d) is 1:
                self.urls.append(url)

    def supports(url, d):
        """Check to see if this fetch class supports a given url.
           Expects supplied url in list form, as outputted by oe.decodeurl().
        """
        return 0
    supports = staticmethod(supports)

    def localpath(url, d = oe.data.init()):
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

class Wget(Fetch):
    """Class to fetch urls via 'wget'"""
    def supports(url, d):
        """Check to see if a given url can be fetched using wget.
           Expects supplied url in list form, as outputted by oe.decodeurl().
        """
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        return type in ['http','https','ftp']
    supports = staticmethod(supports)

    def localpath(url, d):
#       strip off parameters
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]
        url = oe.encodeurl([type, host, path, user, pswd, {}])
        return os.path.join(oe.data.getVar("DL_DIR", d), os.path.basename(url))
    localpath = staticmethod(localpath)

    def go(self, d = oe.data.init(), urls = []):
        """Fetch urls"""
        def fetch_uri(uri, basename, dl, md5, d):
            if os.path.exists(dl):
#               file exists, but we didnt complete it.. trying again..
                fetchcmd = oe.data.getVar("RESUMECOMMAND", d, 1)
            else:
                fetchcmd = oe.data.getVar("FETCHCOMMAND", d, 1)

            oe.note("fetch " + uri)
            fetchcmd = fetchcmd.replace("${URI}", uri)
            fetchcmd = fetchcmd.replace("${FILE}", basename)
            oe.debug(2, "executing " + fetchcmd)
            ret = os.system(fetchcmd)
            if ret != 0:
                return False

#           supposedly complete.. write out md5sum
            if oe.which(oe.data.getVar('PATH', d), 'md5sum'):
                try:
                    md5pipe = os.popen('md5sum ' + dl)
                    md5data = (md5pipe.readline().split() or [ "" ])[0]
                    md5pipe.close()
                except OSError:
                    md5data = ""
                md5out = file(md5, 'w')
                md5out.write(md5data)
                md5out.close()
            else:
                md5out = file(md5, 'w')
                md5out.write("")
                md5out.close()
            return True

        if not urls:
            urls = self.urls

        from copy import deepcopy
        localdata = deepcopy(d)
        oe.data.setVar('OVERRIDES', "wget:" + oe.data.getVar('OVERRIDES', localdata), localdata)
        oe.data.update_data(localdata)

        for uri in urls:
            completed = 0
            (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(uri, localdata))
            basename = os.path.basename(path)
            dl = self.localpath(uri, d)
            dl = oe.data.expand(dl, localdata)
            md5 = dl + '.md5'

            if os.path.exists(md5):
#               complete, nothing to see here..
                continue

            premirrors = [ i.split() for i in (oe.data.getVar('PREMIRRORS', localdata, 1) or "").split('\n') if i ]
            for (find, replace) in premirrors:
                newuri = uri_replace(uri, find, replace)
                if newuri != uri:
                    if fetch_uri(newuri, basename, dl, md5, localdata):
                        completed = 1
                        break

            if completed:
                continue

            if fetch_uri(uri, basename, dl, md5, localdata):
                continue

#           try mirrors
            mirrors = [ i.split() for i in (oe.data.getVar('MIRRORS', localdata, 1) or "").split('\n') if i ]
            for (find, replace) in mirrors:
                newuri = uri_replace(uri, find, replace)
                if newuri != uri:
                    if fetch_uri(newuri, basename, dl, md5, localdata):
                        completed = 1
                        break

            if not completed:
                raise FetchError(uri)

        del localdata


methods.append(Wget())

class Cvs(Fetch):
    """Class to fetch a module or modules from cvs repositories"""
    def supports(url, d):
        """Check to see if a given url can be fetched with cvs.
           Expects supplied url in list form, as outputted by oe.decodeurl().
        """
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        return type in ['cvs', 'pserver']
    supports = staticmethod(supports)

    def localpath(url, d):
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]

        if not "module" in parm:
            raise MissingParameterError("cvs method needs a 'module' parameter")
        else:
            module = parm["module"]
        if 'tag' in parm:
            tag = parm['tag']
        else:
            tag = ""
        if 'date' in parm:
            date = parm['date']
        else:
            if not tag:
                date = oe.data.getVar("CVSDATE", d, 1) or oe.data.getVar("DATE", d, 1)
            else:
                date = ""

        return os.path.join(oe.data.getVar("DL_DIR", d, 1),oe.data.expand('%s_%s_%s_%s.tar.gz' % ( module.replace('/', '.'), host, tag, date), d))
    localpath = staticmethod(localpath)

    def go(self, d = oe.data.init(), urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        from copy import deepcopy
        localdata = deepcopy(d)
        oe.data.setVar('OVERRIDES', "cvs:%s" % oe.data.getVar('OVERRIDES', localdata), localdata)
        oe.data.update_data(localdata)

        for loc in urls:
            (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(loc, localdata))
            if not "module" in parm:
                raise MissingParameterError("cvs method needs a 'module' parameter")
            else:
                module = parm["module"]

            dlfile = self.localpath(loc, localdata)
            dldir = oe.data.getVar('DL_DIR', localdata, 1)
#           if local path contains the cvs
#           module, consider the dir above it to be the
#           download directory
#           pos = dlfile.find(module)
#           if pos:
#               dldir = dlfile[:pos]
#           else:
#               dldir = os.path.dirname(dlfile)

#           setup cvs options
            options = []
            if 'tag' in parm:
                tag = parm['tag']
            else:
                tag = ""

            if 'date' in parm:
                date = parm['date']
            else:
                if not tag:
                    date = oe.data.getVar("CVSDATE", d, 1) or oe.data.getVar("DATE", d, 1)
                else:
                    date = ""

            if "method" in parm:
                method = parm["method"]
            else:
                method = "pserver"

            if "localdir" in parm:
                localdir = parm["localdir"]
            else:
                localdir = os.path.basename(module)

            cvs_rsh = None
            if method == "ext":
                if "rsh" in parm:
                    cvs_rsh = parm["rsh"]

            tarfn = oe.data.expand('%s_%s_%s_%s.tar.gz' % (module.replace('/', '.'), host, tag, date), localdata)
            oe.data.setVar('TARFILES', dlfile, localdata)
            oe.data.setVar('TARFN', tarfn, localdata)

            dl = os.path.join(dldir, tarfn)
            if os.access(dl, os.R_OK):
                oe.debug(1, "%s already exists, skipping cvs checkout." % tarfn)
                continue

            pn = oe.data.getVar('PN', d, 1)
            cvs_tarball_stash = None
            if pn:
                cvs_tarball_stash = oe.data.getVar('CVS_TARBALL_STASH_%s' % pn, d, 1)
            if cvs_tarball_stash == None:
                cvs_tarball_stash = oe.data.getVar('CVS_TARBALL_STASH', d, 1)
            if cvs_tarball_stash:
                fetchcmd = oe.data.getVar("FETCHCOMMAND_wget", d, 1)
                uri = cvs_tarball_stash + tarfn
                oe.note("fetch " + uri)
                fetchcmd = fetchcmd.replace("${URI}", uri)
                ret = os.system(fetchcmd)
                if ret == 0:
                    oe.note("Fetched %s from tarball stash, skipping checkout" % tarfn)
                    continue

            if date:
                options.append("-D %s" % date)
            if tag:
                options.append("-r %s" % tag)

            olddir = os.path.abspath(os.getcwd())
            os.chdir(oe.data.expand(dldir, localdata))

#           setup cvsroot
            cvsroot = ":" + method + ":" + user
            if pswd:
                cvsroot += ":" + pswd
            cvsroot += "@" + host + ":" + path

            oe.data.setVar('CVSROOT', cvsroot, localdata)
            oe.data.setVar('CVSCOOPTS', " ".join(options), localdata)
            oe.data.setVar('CVSMODULE', module, localdata)
            cvscmd = oe.data.getVar('FETCHCOMMAND', localdata, 1)

            if cvs_rsh:
                cvscmd = "CVS_RSH=\"%s\" %s" % (cvs_rsh, cvscmd)

#           create temp directory
            oe.debug(2, "Fetch: creating temporary directory")
            oe.mkdirhier(oe.data.expand('${WORKDIR}', localdata))
            oe.data.setVar('TMPBASE', oe.data.expand('${WORKDIR}/oecvs.XXXXXX', localdata), localdata)
            tmppipe = os.popen(oe.data.getVar('MKTEMPDIRCMD', localdata, 1) or "false")
            tmpfile = tmppipe.readline().strip()
            if not tmpfile:
                oe.error("Fetch: unable to create temporary directory.. make sure 'mktemp' is in the PATH.")
                raise FetchError(module)

#           check out sources there
            os.chdir(tmpfile)
            oe.note("Fetch " + loc)
            oe.debug(1, "Running %s" % cvscmd)
            myret = os.system(cvscmd)
            if myret != 0:
                try:
                    os.rmdir(tmpfile)
                except OSError:
                    pass
                raise FetchError(module)

            os.chdir(os.path.join(tmpfile, os.path.dirname(module)))
#           tar them up to a defined filename
            myret = os.system("tar -czvf %s %s" % (os.path.join(dldir,tarfn), localdir))
            if myret != 0:
                try:
                    os.unlink(tarfn)
                except OSError:
                    pass
#           cleanup
            os.system('rm -rf %s' % tmpfile)
            os.chdir(olddir)
        del localdata

methods.append(Cvs())

class Bk(Fetch):
    def supports(url, d):
        """Check to see if a given url can be fetched via bitkeeper.
           Expects supplied url in list form, as outputted by oe.decodeurl().
        """
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        return type in ['bk']
    supports = staticmethod(supports)

methods.append(Bk())

class Local(Fetch):
    def supports(url, d):
        """Check to see if a given url can be fetched in the local filesystem.
           Expects supplied url in list form, as outputted by oe.decodeurl().
        """
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        return type in ['file','patch']
    supports = staticmethod(supports)

    def localpath(url, d):
        """Return the local filename of a given url assuming a successful fetch.
        """
        path = url.split("://")[1]
        newpath = path
        if path[0] != "/":
            filespath = oe.data.getVar('FILESPATH', d, 1)
            if filespath:
                newpath = oe.which(filespath, path)
            if not newpath:
                filesdir = oe.data.getVar('FILESDIR', d, 1)
                if filesdir:
                    newpath = os.path.join(filesdir, path)
        return newpath
    localpath = staticmethod(localpath)

    def go(self, urls = []):
        """Fetch urls (no-op for Local method)"""
#       no need to fetch local files, we'll deal with them in place.
        return 1

methods.append(Local())

class Svn(Fetch):
    """Class to fetch a module or modules from svn repositories"""
    def supports(url, d):
        """Check to see if a given url can be fetched with svn.
           Expects supplied url in list form, as outputted by oe.decodeurl().
        """
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        return type in ['svn']
    supports = staticmethod(supports)

    def localpath(url, d):
        (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]

        if not "module" in parm:
            raise MissingParameterError("svn method needs a 'module' parameter")
        else:
            module = parm["module"]
        if 'tag' in parm:
            tag = parm['tag']
        else:
            tag = ""
        if 'date' in parm:
            date = parm['date']
        else:
            if not tag or tag == "HEAD":
                date = oe.data.getVar("CVSDATE", d, 1) or oe.data.getVar("DATE", d, 1)
            else:
                date = ""

        return os.path.join(oe.data.getVar("DL_DIR", d, 1),oe.data.expand('%s_%s_%s_%s.tar.gz' % ( module.replace('/', '.'), host, tag, date), d))
    localpath = staticmethod(localpath)

    def go(self, d = oe.data.init(), urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        from copy import deepcopy
        localdata = deepcopy(d)
        oe.data.setVar('OVERRIDES', "svn:%s" % oe.data.getVar('OVERRIDES', localdata), localdata)
        oe.data.update_data(localdata)

        for loc in urls:
            (type, host, path, user, pswd, parm) = oe.decodeurl(oe.data.expand(loc, localdata))
            if not "module" in parm:
                raise MissingParameterError("svn method needs a 'module' parameter")
            else:
                module = parm["module"]

            dlfile = self.localpath(loc, localdata)
            dldir = oe.data.getVar('DL_DIR', localdata, 1)
#           if local path contains the svn
#           module, consider the dir above it to be the
#           download directory
#           pos = dlfile.find(module)
#           if pos:
#               dldir = dlfile[:pos]
#           else:
#               dldir = os.path.dirname(dlfile)

#           setup svn options
            options = []
            if 'tag' in parm:
                tag = parm['tag']
            else:
                tag = ""

            if 'date' in parm:
                date = parm['date']
            else:
                if not tag or tag == "HEAD":
                    date = oe.data.getVar("CVSDATE", d, 1) or oe.data.getVar("DATE", d, 1)
                else:
                    date = ""

            if "method" in parm:
                method = parm["method"]
            else:
                method = "pserver"

            svn_rsh = None
            if method == "ext":
                if "rsh" in parm:
                    svn_rsh = parm["rsh"]

            tarfn = oe.data.expand('%s_%s_%s_%s.tar.gz' % (module.replace('/', '.'), host, tag, date), localdata)
            oe.data.setVar('TARFILES', dlfile, localdata)
            oe.data.setVar('TARFN', tarfn, localdata)

            dl = os.path.join(dldir, tarfn)
            if os.access(dl, os.R_OK):
                oe.debug(1, "%s already exists, skipping svn checkout." % tarfn)
                continue

            svn_tarball_stash = oe.data.getVar('CVS_TARBALL_STASH', d, 1)
            if svn_tarball_stash:
                fetchcmd = oe.data.getVar("FETCHCOMMAND_wget", d, 1)
                uri = svn_tarball_stash + tarfn
                oe.note("fetch " + uri)
                fetchcmd = fetchcmd.replace("${URI}", uri)
                ret = os.system(fetchcmd)
                if ret == 0:
                    oe.note("Fetched %s from tarball stash, skipping checkout" % tarfn)
                    continue

            if date:
                options.append("-D %s" % date)
            if tag:
                options.append("-r %s" % tag)

            olddir = os.path.abspath(os.getcwd())
            os.chdir(oe.data.expand(dldir, localdata))

#           setup svnroot
#            svnroot = ":" + method + ":" + user
#            if pswd:
#                svnroot += ":" + pswd
            svnroot = host + path

            oe.data.setVar('SVNROOT', svnroot, localdata)
            oe.data.setVar('SVNCOOPTS', " ".join(options), localdata)
            oe.data.setVar('SVNMODULE', module, localdata)
            svncmd = oe.data.getVar('FETCHCOMMAND', localdata, 1)
            svncmd = "svn co http://%s/%s" % (svnroot, module)

            if svn_rsh:
                svncmd = "svn_RSH=\"%s\" %s" % (svn_rsh, svncmd)

#           create temp directory
            oe.debug(2, "Fetch: creating temporary directory")
            oe.mkdirhier(oe.data.expand('${WORKDIR}', localdata))
            oe.data.setVar('TMPBASE', oe.data.expand('${WORKDIR}/oesvn.XXXXXX', localdata), localdata)
            tmppipe = os.popen(oe.data.getVar('MKTEMPDIRCMD', localdata, 1) or "false")
            tmpfile = tmppipe.readline().strip()
            if not tmpfile:
                oe.error("Fetch: unable to create temporary directory.. make sure 'mktemp' is in the PATH.")
                raise FetchError(module)

#           check out sources there
            os.chdir(tmpfile)
            oe.note("Fetch " + loc)
            oe.note(svncmd)
            oe.debug(1, "Running %s" % svncmd)
            myret = os.system(svncmd)
            if myret != 0:
                try:
                    os.rmdir(tmpfile)
                except OSError:
                    pass
                raise FetchError(module)

            os.chdir(os.path.join(tmpfile, os.path.dirname(module)))
#           tar them up to a defined filename
            myret = os.system("tar -czvf %s %s" % (os.path.join(dldir,tarfn), os.path.basename(module)))
            if myret != 0:
                try:
                    os.unlink(tarfn)
                except OSError:
                    pass
#           cleanup
            os.system('rm -rf %s' % tmpfile)
            os.chdir(olddir)
        del localdata

methods.append(Svn())
