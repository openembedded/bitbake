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
from   bb import data
from   bb.fetch import Fetch

class Local(Fetch):
    def supports(self, url, urldata, d):
        """
        Check to see if a given url can be fetched with cvs.
        """
        return urldata.type in ['file','patch']

    def localpath(self, url, urldata, d):
        """Return the local filename of a given url assuming a successful fetch.
        """
        path = url.split("://")[1]
        newpath = path
        if path[0] != "/":
            filespath = data.getVar('FILESPATH', d, 1)
            if filespath:
                newpath = bb.which(filespath, path)
            if not newpath:
                filesdir = data.getVar('FILESDIR', d, 1)
                if filesdir:
                    newpath = os.path.join(filesdir, path)
        # We don't set localfile as for this fetcher the file is already local!
        return newpath

    def go(self, url, urldata, d):
        """Fetch urls (no-op for Local method)"""
        # no need to fetch local files, we'll deal with them in place.
        return 1
