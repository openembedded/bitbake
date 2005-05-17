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
import bb.data

class FetchError(Exception):
    """Exception raised when a download fails"""

class NoMethodError(Exception):
    """Exception raised when there is no method to obtain a supplied url or set of urls"""

class MissingParameterError(Exception):
    """Exception raised when a fetch method is missing a critical parameter in the url"""

#decodeurl("cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;module=familiar/dist/ipkg;tag=V0-99-81")
#('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'})

def uri_replace(uri, uri_find, uri_replace, d = bb.data.init()):
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

def init(urls = [], d = bb.data.init()):
    for m in methods:
        m.urls = []

    for u in urls:
        for m in methods:
            m.data = d
            if m.supports(u, d):
                m.urls.append(u)

def go(d = bb.data.init()):
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

def localpath(url, d = bb.data.init()):
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

    def localpath(url, d = bb.data.init()):
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
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
        return type in ['http','https','ftp']
    supports = staticmethod(supports)

    def localpath(url, d):
#       strip off parameters
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]
        url = bb.encodeurl([type, host, path, user, pswd, {}])
        return os.path.join(bb.data.getVar("DL_DIR", d), os.path.basename(url))
    localpath = staticmethod(localpath)

    def go(self, d = bb.data.init(), urls = []):
        """Fetch urls"""
        def fetch_uri(uri, basename, dl, md5, d):
            if os.path.exists(dl):
#               file exists, but we didnt complete it.. trying again..
                fetchcmd = bb.data.getVar("RESUMECOMMAND", d, 1)
            else:
                fetchcmd = bb.data.getVar("FETCHCOMMAND", d, 1)

            bb.note("fetch " + uri)
            fetchcmd = fetchcmd.replace("${URI}", uri)
            fetchcmd = fetchcmd.replace("${FILE}", basename)
            bb.debug(2, "executing " + fetchcmd)
            ret = os.system(fetchcmd)
            if ret != 0:
                return False

#           supposedly complete.. write out md5sum
            if bb.which(bb.data.getVar('PATH', d), 'md5sum'):
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

        localdata = bb.data.createCopy(d)
        bb.data.setVar('OVERRIDES', "wget:" + bb.data.getVar('OVERRIDES', localdata), localdata)
        bb.data.update_data(localdata)

        for uri in urls:
            completed = 0
            (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(uri, localdata))
            basename = os.path.basename(path)
            dl = self.localpath(uri, d)
            dl = bb.data.expand(dl, localdata)
            md5 = dl + '.md5'

            if os.path.exists(md5):
#               complete, nothing to see here..
                continue

            premirrors = [ i.split() for i in (bb.data.getVar('PREMIRRORS', localdata, 1) or "").split('\n') if i ]
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
            mirrors = [ i.split() for i in (bb.data.getVar('MIRRORS', localdata, 1) or "").split('\n') if i ]
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
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
        return type in ['cvs', 'pserver']
    supports = staticmethod(supports)

    def localpath(url, d):
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
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
                date = bb.data.getVar("CVSDATE", d, 1) or bb.data.getVar("DATE", d, 1)
            else:
                date = ""

        return os.path.join(bb.data.getVar("DL_DIR", d, 1),bb.data.expand('%s_%s_%s_%s.tar.gz' % ( module.replace('/', '.'), host, tag, date), d))
    localpath = staticmethod(localpath)

    def go(self, d = bb.data.init(), urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        localdata = bb.data.createCopy(d)
        bb.data.setVar('OVERRIDES', "cvs:%s" % bb.data.getVar('OVERRIDES', localdata), localdata)
        bb.data.update_data(localdata)

        for loc in urls:
            (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(loc, localdata))
            if not "module" in parm:
                raise MissingParameterError("cvs method needs a 'module' parameter")
            else:
                module = parm["module"]

            dlfile = self.localpath(loc, localdata)
            dldir = bb.data.getVar('DL_DIR', localdata, 1)
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
                    date = bb.data.getVar("CVSDATE", d, 1) or bb.data.getVar("DATE", d, 1)
                else:
                    date = ""

            if "method" in parm:
                method = parm["method"]
            else:
                method = "pserver"

            if "localdir" in parm:
                localdir = parm["localdir"]
            else:
                localdir = module

            cvs_rsh = None
            if method == "ext":
                if "rsh" in parm:
                    cvs_rsh = parm["rsh"]

            tarfn = bb.data.expand('%s_%s_%s_%s.tar.gz' % (module.replace('/', '.'), host, tag, date), localdata)
            bb.data.setVar('TARFILES', dlfile, localdata)
            bb.data.setVar('TARFN', tarfn, localdata)

            dl = os.path.join(dldir, tarfn)
            if os.access(dl, os.R_OK):
                bb.debug(1, "%s already exists, skipping cvs checkout." % tarfn)
                continue

            pn = bb.data.getVar('PN', d, 1)
            cvs_tarball_stash = None
            if pn:
                cvs_tarball_stash = bb.data.getVar('CVS_TARBALL_STASH_%s' % pn, d, 1)
            if cvs_tarball_stash == None:
                cvs_tarball_stash = bb.data.getVar('CVS_TARBALL_STASH', d, 1)
            if cvs_tarball_stash:
                fetchcmd = bb.data.getVar("FETCHCOMMAND_wget", d, 1)
                uri = cvs_tarball_stash + tarfn
                bb.note("fetch " + uri)
                fetchcmd = fetchcmd.replace("${URI}", uri)
                ret = os.system(fetchcmd)
                if ret == 0:
                    bb.note("Fetched %s from tarball stash, skipping checkout" % tarfn)
                    continue

            if date:
                options.append("-D %s" % date)
            if tag:
                options.append("-r %s" % tag)

            olddir = os.path.abspath(os.getcwd())
            os.chdir(bb.data.expand(dldir, localdata))

#           setup cvsroot
            if method == "dir":
                cvsroot = path
            else:
                cvsroot = ":" + method + ":" + user
                if pswd:
                    cvsroot += ":" + pswd
                cvsroot += "@" + host + ":" + path

            bb.data.setVar('CVSROOT', cvsroot, localdata)
            bb.data.setVar('CVSCOOPTS', " ".join(options), localdata)
            bb.data.setVar('CVSMODULE', module, localdata)
            cvscmd = bb.data.getVar('FETCHCOMMAND', localdata, 1)
            cvsupdatecmd = bb.data.getVar('UPDATECOMMAND', localdata, 1)

            if cvs_rsh:
                cvscmd = "CVS_RSH=\"%s\" %s" % (cvs_rsh, cvscmd)
                cvsupdatecmd = "CVS_RSH=\"%s\" %s" % (cvs_rsh, cvsupdatecmd)

#           create module directory
            bb.debug(2, "Fetch: checking for module directory")
            pkg=bb.data.expand('${PN}', d)
            pkgdir=os.path.join(bb.data.expand('${CVSDIR}', localdata), pkg)
            moddir=os.path.join(pkgdir,localdir)
            if os.access(os.path.join(moddir,'CVS'), os.R_OK):
                bb.note("Update " + loc)
#               update sources there
                os.chdir(moddir)
                myret = os.system(cvsupdatecmd)
            else:
                bb.note("Fetch " + loc)
#               check out sources there
                bb.mkdirhier(pkgdir)
                os.chdir(pkgdir)
                bb.debug(1, "Running %s" % cvscmd)
                myret = os.system(cvscmd)

            if myret != 0:
                try:
                    os.rmdir(moddir)
                except OSError:
                    pass
                raise FetchError(module)

            os.chdir(moddir)
            os.chdir('..')
#           tar them up to a defined filename
            myret = os.system("tar -czf %s %s" % (os.path.join(dldir,tarfn), os.path.basename(moddir)))
            if myret != 0:
                try:
                    os.unlink(tarfn)
                except OSError:
                    pass
            os.chdir(olddir)
        del localdata

methods.append(Cvs())

class Bk(Fetch):
    def supports(url, d):
        """Check to see if a given url can be fetched via bitkeeper.
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
        return type in ['bk']
    supports = staticmethod(supports)

methods.append(Bk())

class Local(Fetch):
    def supports(url, d):
        """Check to see if a given url can be fetched in the local filesystem.
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
        return type in ['file','patch']
    supports = staticmethod(supports)

    def localpath(url, d):
        """Return the local filename of a given url assuming a successful fetch.
        """
        path = url.split("://")[1]
        newpath = path
        if path[0] != "/":
            filespath = bb.data.getVar('FILESPATH', d, 1)
            if filespath:
                newpath = bb.which(filespath, path)
            if not newpath:
                filesdir = bb.data.getVar('FILESDIR', d, 1)
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
           Expects supplied url in list form, as outputted by bb.decodeurl().
        """
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
        return type in ['svn']
    supports = staticmethod(supports)

    def localpath(url, d):
        (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(url, d))
        if "localpath" in parm:
#           if user overrides local path, use it.
            return parm["localpath"]

        if not "module" in parm:
            raise MissingParameterError("svn method needs a 'module' parameter")
        else:
            module = parm["module"]
        if 'rev' in parm:
            revision = parm['rev']
        else:
            revision = ""

        date = bb.data.getVar("CVSDATE", d, 1) or bb.data.getVar("DATE", d, 1)

        return os.path.join(bb.data.getVar("DL_DIR", d, 1),bb.data.expand('%s_%s_%s_%s.tar.gz' % ( module.replace('/', '.'), host, revision, date), d))
    localpath = staticmethod(localpath)

    def go(self, d = bb.data.init(), urls = []):
        """Fetch urls"""
        if not urls:
            urls = self.urls

        localdata = bb.data.createCopy(d)
        bb.data.setVar('OVERRIDES', "svn:%s" % bb.data.getVar('OVERRIDES', localdata), localdata)
        bb.data.update_data(localdata)

        for loc in urls:
            (type, host, path, user, pswd, parm) = bb.decodeurl(bb.data.expand(loc, localdata))
            if not "module" in parm:
                raise MissingParameterError("svn method needs a 'module' parameter")
            else:
                module = parm["module"]

            dlfile = self.localpath(loc, localdata)
            dldir = bb.data.getVar('DL_DIR', localdata, 1)
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
            if 'rev' in parm:
                revision = parm['rev']
            else:
                revision = ""

            date = bb.data.getVar("CVSDATE", d, 1) or bb.data.getVar("DATE", d, 1)

            if "method" in parm:
                method = parm["method"]
            else:
                method = "pserver"

            if "proto" in parm:
                proto = parm["proto"]
            else:
                proto = "svn"

            svn_rsh = None
            if method == "ext":
                if "rsh" in parm:
                    svn_rsh = parm["rsh"]

            tarfn = bb.data.expand('%s_%s_%s_%s.tar.gz' % (module.replace('/', '.'), host, revision, date), localdata)
            bb.data.setVar('TARFILES', dlfile, localdata)
            bb.data.setVar('TARFN', tarfn, localdata)

            dl = os.path.join(dldir, tarfn)
            if os.access(dl, os.R_OK):
                bb.debug(1, "%s already exists, skipping svn checkout." % tarfn)
                continue

            svn_tarball_stash = bb.data.getVar('CVS_TARBALL_STASH', d, 1)
            if svn_tarball_stash:
                fetchcmd = bb.data.getVar("FETCHCOMMAND_wget", d, 1)
                uri = svn_tarball_stash + tarfn
                bb.note("fetch " + uri)
                fetchcmd = fetchcmd.replace("${URI}", uri)
                ret = os.system(fetchcmd)
                if ret == 0:
                    bb.note("Fetched %s from tarball stash, skipping checkout" % tarfn)
                    continue

            olddir = os.path.abspath(os.getcwd())
            os.chdir(bb.data.expand(dldir, localdata))

#           setup svnroot
#            svnroot = ":" + method + ":" + user
#            if pswd:
#                svnroot += ":" + pswd
            svnroot = host + path

            bb.data.setVar('SVNROOT', svnroot, localdata)
            bb.data.setVar('SVNCOOPTS', " ".join(options), localdata)
            bb.data.setVar('SVNMODULE', module, localdata)
            svncmd = bb.data.getVar('FETCHCOMMAND', localdata, 1)
            svncmd = "svn co %s://%s/%s" % (proto, svnroot, module)

            if revision:
                svncmd = "svn co -r %s %s://%s/%s" % (revision, proto, svnroot, module)
            if svn_rsh:
                svncmd = "svn_RSH=\"%s\" %s" % (svn_rsh, svncmd)

#           create temp directory
            bb.debug(2, "Fetch: creating temporary directory")
            bb.mkdirhier(bb.data.expand('${WORKDIR}', localdata))
            bb.data.setVar('TMPBASE', bb.data.expand('${WORKDIR}/oesvn.XXXXXX', localdata), localdata)
            tmppipe = os.popen(bb.data.getVar('MKTEMPDIRCMD', localdata, 1) or "false")
            tmpfile = tmppipe.readline().strip()
            if not tmpfile:
                bb.error("Fetch: unable to create temporary directory.. make sure 'mktemp' is in the PATH.")
                raise FetchError(module)

#           check out sources there
            os.chdir(tmpfile)
            bb.note("Fetch " + loc)
            bb.debug(1, "Running %s" % svncmd)
            myret = os.system(svncmd)
            if myret != 0:
                try:
                    os.rmdir(tmpfile)
                except OSError:
                    pass
                raise FetchError(module)

            os.chdir(os.path.join(tmpfile, os.path.dirname(module)))
#           tar them up to a defined filename
            myret = os.system("tar -czf %s %s" % (os.path.join(dldir,tarfn), os.path.basename(module)))
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
