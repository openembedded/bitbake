# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
'''
BitBake 'Fetch' implementations

This implementation is for Secure Shell (SSH), and attempts to comply with the
IETF secsh internet draft:
    http://tools.ietf.org/wg/secsh/draft-ietf-secsh-scp-sftp-ssh-uri/

    Currently does not support the sftp parameters, as this uses scp
    Also does not support the 'fingerprint' connection parameter.

'''

# Copyright (C) 2006  OpenedHand Ltd.
#
#
# Based in part on svk.py:
#    Copyright (C) 2006 Holger Hans Peter Freyther
#    Based on svn.py:
#        Copyright (C) 2003, 2004  Chris Larson
#        Based on functions from the base bb module:
#            Copyright 2003 Holger Schurig
#
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

import re, os
from   bb import data
from   bb.fetch2 import FetchMethod
from   bb.fetch2 import FetchError
from   bb.fetch2 import logger
from   bb.fetch2 import runfetchcmd


__pattern__ = re.compile(r'''
 \s*                 # Skip leading whitespace
 ssh://              # scheme
 (                   # Optional username/password block
  (?P<user>\S+)      # username
  (:(?P<pass>\S+))?  # colon followed by the password (optional)
 )?
 (?P<cparam>(;[^;]+)*)?  # connection parameters block (optional)
 @
 (?P<host>\S+?)          # non-greedy match of the host
 (:(?P<port>[0-9]+))?    # colon followed by the port (optional)
 /
 (?P<path>[^;]+)         # path on the remote system, may be absolute or relative,
                         # and may include the use of '~' to reference the remote home
                         # directory
 (?P<sparam>(;[^;]+)*)?  # parameters block (optional)
 $
''', re.VERBOSE)

class SSH(FetchMethod):
    '''Class to fetch a module or modules via Secure Shell'''

    def supports(self, url, urldata, d):
        return __pattern__.match(url) != None

    def localpath(self, url, urldata, d):
        m = __pattern__.match(urldata.url)
        path = m.group('path')
        host = m.group('host')
        lpath = os.path.join(data.getVar('DL_DIR', d, True), host, os.path.basename(path))
        return lpath

    def download(self, url, urldata, d):
        dldir = data.getVar('DL_DIR', d, True)

        m = __pattern__.match(url)
        path = m.group('path')
        host = m.group('host')
        port = m.group('port')
        user = m.group('user')
        password = m.group('pass')

        ldir = os.path.join(dldir, host)
        lpath = os.path.join(ldir, os.path.basename(path))

        if not os.path.exists(ldir):
            os.makedirs(ldir)

        if port:
            port = '-P %s' % port
        else:
            port = ''

        if user:
            fr = user
            if password:
                fr += ':%s' % password
            fr += '@%s' % host
        else:
            fr = host
        fr += ':%s' % path


        import commands
        cmd = 'scp -B -r %s %s %s/' % (
            port,
            commands.mkarg(fr),
            commands.mkarg(ldir)
        )

        bb.fetch2.check_network_access(d, cmd, urldata.url)

        runfetchcmd(cmd, d)

