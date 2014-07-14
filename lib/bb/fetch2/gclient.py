# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' gclient implementation

Copyright (C) 2013, Karfield Chen. All rights reserved.

"""

import os
import bb
from   bb    import data
from   bb.fetch2 import FetchMethod
from   bb.fetch2 import runfetchcmd
from   bb.fetch2 import logger

class Gclient(FetchMethod):
    """Class for sync code from depot-based repositories"""
    def init(self, d):
        pass

    def supports(self, url, ud, d):
        """
        Check to see if a given url starts with "depot" or "gclient".
        """
        return ud.type in ["depot", "gclient"]

    def supports_checksum(self, urldata):
        """
        checksum? needn't.
        """
        return False

    def urldata_init(self, ud, d):
        """
        supported options:
            name: package name
        """
        ud.name = ud.parm.get('name', '')
        ud.njobs = ud.parm.get('jobs', '1')
        ud.packname = "gclient_%s%s_%s" % (ud.host, ud.path.replace("/", "."), ud.name)
        ud.localfile = data.expand("%s.tar.gz" % ud.packname, d)

    def download(self, loc, ud, d):
        """
        do fetch
        """
        # if the package has been downloaded, just return
        if os.access(os.path.join(data.getVar("DL_DIR", d, True), ud.localfile), os.R_OK):
            logger.debug(1, "%s already exists (or was stashed). Skipping gclient sync.", ud.localpath)
            return

        depot_dir = data.getVar("DEPOTDIR", d, True) or os.path.join(data.getVar("DL_DIR", d, True), "depot")
        sync_dir = os.path.join(depot_dir, ud.packname)

        bb.utils.mkdirhier(sync_dir)
        os.chdir(sync_dir)

        if not os.path.exists(os.path.join(sync_dir, ".gclient")):
            logger.info('This is the first time to sync this depot, config it as htttp://%s%s'
                    % (ud.host, ud.path))
            runfetchcmd('gclient config http://%s%s' % (ud.host, ud.path), d)

        logger.info('Start to sync source code..')
        runfetchcmd('gclient fetch --jobs %s' % ud.njobs, d)

        logger.info('Creating tarball %s.' % ud.localfile)
        runfetchcmd('tar --exclude .svn --exclude .git -czf %s ./' %
                os.path.join(data.getVar("DL_DIR", d, True), ud.localfile), d)

    def supports_srcrev(self):
        return False

    def _build_revision(self, url, ud, d):
        return None

    def _want_sortable_revision(self, url, ud, d):
        return False
