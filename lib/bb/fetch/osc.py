# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
Bitbake "Fetch" implementation for osc (Opensuse build service client).
Based on the svn "Fetch" implementation.

"""

import  os
import  sys
import  bb
from    bb       import data
from    bb.fetch import Fetch
from    bb.fetch import FetchError
from    bb.fetch import MissingParameterError
from    bb.fetch import runfetchcmd

class Osc(Fetch):
    """Class to fetch a module or modules from Opensuse build server 
       repositories."""

    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with osc.
        """
        return ud.type in ['osc']

    def localpath(self, url, ud, d):
        if not "module" in ud.parm:
            raise MissingParameterError("osc method needs a 'module' parameter.")

        ud.module = ud.parm["module"]

        # Create paths to osc checkouts
        relpath = ud.path
        if relpath.startswith('/'):
            # Remove leading slash as os.path.join can't cope
            relpath = relpath[1:]
        ud.pkgdir = os.path.join(data.expand('${OSCDIR}', d), ud.host)
        ud.moddir = os.path.join(ud.pkgdir, relpath, ud.module)

        if 'rev' in ud.parm:
            ud.revision = ud.parm['rev']
        else:
            pv = data.getVar("PV", d, 0)
            rev = Fetch.srcrev_internal_helper(ud, d)
            if rev and rev != True:
                ud.revision = rev
            else:
                ud.revision = ""

        ud.localfile = data.expand('%s_%s_%s.tar.gz' % (ud.module.replace('/', '.'), ud.path.replace('/', '.'), ud.revision), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def _buildosccommand(self, ud, d, command):
        """
        Build up an ocs commandline based on ud
        command is "fetch", "update", "info"
        """

        basecmd = data.expand('${FETCHCMD_osc}', d)

        proto = "ocs"
        if "proto" in ud.parm:
            proto = ud.parm["proto"]
        
        options = []

        config = "-c %s" % self.generate_config(ud, d)

        if ud.revision:
            options.append("-r %s" % ud.revision)

        coroot = ud.path
        if coroot.startswith('/'):
            # Remove leading slash as os.path.join can't cope
            coroot= coroot[1:]

        if command is "fetch":
            osccmd = "%s %s co %s/%s %s" % (basecmd, config, coroot, ud.module, " ".join(options))
        elif command is "update":
            osccmd = "%s %s up %s" % (basecmd, config, " ".join(options))
        else:
            raise FetchError("Invalid osc command %s" % command)

        return osccmd

    def go(self, loc, ud, d):
        """
        Fetch url
        """

        # Try to use the tarball stash
        if Fetch.try_mirror(d, ud.localfile):
            bb.msg.debug(1, bb.msg.domain.Fetcher, "%s already exists or was mirrored, skipping osc checkout." % ud.localpath)
            return

        bb.msg.debug(2, bb.msg.domain.Fetcher, "Fetch: checking for module directory '" + ud.moddir + "'")

        if os.access(os.path.join(data.expand('${OSCDIR}', d), ud.path, ud.module), os.R_OK):
            oscupdatecmd = self._buildosccommand(ud, d, "update")
            bb.msg.note(1, bb.msg.domain.Fetcher, "Update "+ loc)
            # update sources there
            os.chdir(ud.moddir)
            bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % oscupdatecmd)
            runfetchcmd(oscupdatecmd, d)
        else:
            oscfetchcmd = self._buildosccommand(ud, d, "fetch")
            bb.msg.note(1, bb.msg.domain.Fetcher, "Fetch " + loc)
            # check out sources there
            bb.mkdirhier(ud.pkgdir)
            os.chdir(ud.pkgdir)
            bb.msg.debug(1, bb.msg.domain.Fetcher, "Running %s" % oscfetchcmd)
            runfetchcmd(oscfetchcmd, d)
        
        os.chdir(os.path.join(ud.pkgdir + ud.path))
        # tar them up to a defined filename
        try:
            runfetchcmd("tar -czf %s %s" % (ud.localpath, ud.module), d)
        except:
            t, v, tb = sys.exc_info()
            try:
                os.unlink(ud.localpath)
            except OSError:
                pass
            raise t, v, tb

    def supports_srcrev(self):
        return False

    def generate_config(self, ud, d):
        """
        Generate a .oscrc to be used for this run.
        """

        config_path = "%s/oscrc" % data.expand('${OSCDIR}', d)
        if (os.path.exists(config_path)):
            os.remove(config_path) 

        f = open(config_path, 'w')
        f.write("[general]\n")
        f.write("apisrv = %s\n" % ud.host)
        f.write("scheme = http\n")
        f.write("su-wrapper = su -c\n")
        f.write("build-root = %s\n" % data.expand('${WORKDIR}', d))
        f.write("urllist = http://moblin-obs.jf.intel.com:8888/build/%(project)s/%(repository)s/%(buildarch)s/:full/%(name)s.rpm\n")
        f.write("extra-pkgs = gzip\n")
        f.write("\n")
        f.write("[%s]\n" % ud.host)
        f.write("user = %s\n" % ud.parm["user"])
        f.write("pass = %s\n" % ud.parm["pswd"])
        f.close()
        
        return config_path
