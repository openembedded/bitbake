# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' git submodules implementation

Inherits from and extends the Git fetcher to retrieve submodules of a git repository
after cloning.

SRC_URI = "gitsm://<see Git fetcher for syntax>"

See the Git fetcher, git://, for usage documentation.

NOTE: Switching a SRC_URI from "git://" to "gitsm://" requires a clean of your recipe.

"""

# Copyright (C) 2013 Richard Purdie
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

import os
import bb
import copy
from   bb.fetch2.git import Git
from   bb.fetch2 import runfetchcmd
from   bb.fetch2 import logger
from   bb.fetch2 import Fetch
from   bb.fetch2 import BBFetchException

class GitSM(Git):
    def supports(self, ud, d):
        """
        Check to see if a given url can be fetched with git.
        """
        return ud.type in ['gitsm']

    @staticmethod
    def parse_gitmodules(gitmodules):
        modules = {}
        module = ""
        for line in gitmodules.splitlines():
            if line.startswith('[submodule'):
                module = line.split('"')[1]
                modules[module] = {}
            elif module and line.strip().startswith('path'):
                path = line.split('=')[1].strip()
                modules[module]['path'] = path
            elif module and line.strip().startswith('url'):
                url = line.split('=')[1].strip()
                modules[module]['url'] = url
        return modules

    def update_submodules(self, ud, d):
        submodules = []
        paths = {}
        revision = {}
        uris = {}
        local_paths = {}

        for name in ud.names:
            try:
                gitmodules = runfetchcmd("%s show %s:.gitmodules" % (ud.basecmd, ud.revisions[name]), d, quiet=True, workdir=ud.clonedir)
            except:
                # No submodules to update
                continue

            for m, md in self.parse_gitmodules(gitmodules).items():
                submodules.append(m)
                paths[m] = md['path']
                revision[m] = ud.revisions[name]
                uris[m] = md['url']
                if uris[m].startswith('..'):
                    newud = copy.copy(ud)
                    newud.path = os.path.realpath(os.path.join(newud.path, md['url']))
                    uris[m] = Git._get_repo_url(self, newud)

        for module in submodules:
            try:
                module_hash = runfetchcmd("%s ls-tree -z -d %s %s" % (ud.basecmd, revision[module], paths[module]), d, quiet=True, workdir=ud.clonedir)
            except:
                # If the command fails, we don't have a valid file to check.  If it doesn't
                # fail -- it still might be a failure, see next check...
                module_hash = ""

            if not module_hash:
                logger.debug(1, "submodule %s is defined, but is not initialized in the repository. Skipping", module)
                continue

            module_hash = module_hash.split()[2]

            # Build new SRC_URI
            if "://" not in uris[module]:
                # It's ssh if the format does NOT have "://", but has a ':'
                if ":" in uris[module]:
                    proto = "ssh"
                    if ":/" in uris[module]:
                        url = "gitsm://" + uris[module].replace(':/', '/', 1)
                    else:
                        url = "gitsm://" + uris[module].replace(':', '/', 1)
                else: # Fall back to 'file' if there is no ':'
                    proto = "file"
                    url = "gitsm://" + uris[module]
            else:
                proto = uris[module].split(':', 1)[0]
                url = uris[module].replace('%s:' % proto, 'gitsm:', 1)

            url += ';protocol=%s' % proto
            url += ";name=%s" % module
            url += ";bareclone=1;nocheckout=1;nobranch=1"

            ld = d.createCopy()
            # Not necessary to set SRC_URI, since we're passing the URI to
            # Fetch.
            #ld.setVar('SRC_URI', url)
            ld.setVar('SRCREV_%s' % module, module_hash)

            # Workaround for issues with SRCPV/SRCREV_FORMAT errors
            # error refer to 'multiple' repositories.  Only the repository
            # in the original SRC_URI actually matters...
            ld.setVar('SRCPV', d.getVar('SRCPV'))
            ld.setVar('SRCREV_FORMAT', module)

            newfetch = Fetch([url], ld, cache=False)
            newfetch.download()
            local_paths[module] = newfetch.localpath(url)

            # Correct the submodule references to the local download version...
            runfetchcmd("%(basecmd)s config submodule.%(module)s.url %(url)s" % {'basecmd': ud.basecmd, 'module': module, 'url' : local_paths[module]}, d, workdir=ud.clonedir)

            symlink_path = os.path.join(ud.clonedir, 'modules', paths[module])
            if not os.path.exists(symlink_path):
                try:
                    os.makedirs(os.path.dirname(symlink_path), exist_ok=True)
                except OSError:
                    pass
                os.symlink(local_paths[module], symlink_path)

        return True

    def download(self, ud, d):
        Git.download(self, ud, d)
        self.update_submodules(ud, d)

    def unpack_submodules(self, repo_conf, ud, d):
        submodules = []
        paths = {}
        revision = {}
        uris = {}
        local_paths = {}

        for name in ud.names:
            try:
                gitmodules = runfetchcmd("%s show %s:.gitmodules" % (ud.basecmd, ud.revisions[name]), d, quiet=True, workdir=ud.destdir)
            except:
                # No submodules to update
                continue

            for m, md in self.parse_gitmodules(gitmodules).items():
                submodules.append(m)
                paths[m] = md['path']
                revision[m] = ud.revisions[name]
                uris[m] = md['url']
                if uris[m].startswith('..'):
                    newud = copy.copy(ud)
                    newud.path = os.path.realpath(os.path.join(newud.path, md['url']))
                    uris[m] = Git._get_repo_url(self, newud)

        modules_updated = False

        for module in submodules:
            try:
                module_hash = runfetchcmd("%s ls-tree -z -d %s %s" % (ud.basecmd, revision[module], paths[module]), d, quiet=True, workdir=ud.destdir)
            except:
                # If the command fails, we don't have a valid file to check.  If it doesn't
                # fail -- it still might be a failure, see next check...
                module_hash = ""

            if not module_hash:
                logger.debug(1, "submodule %s is defined, but is not initialized in the repository. Skipping", module)
                continue

            modules_updated = True

            module_hash = module_hash.split()[2]

            # Build new SRC_URI
            if "://" not in uris[module]:
                # It's ssh if the format does NOT have "://", but has a ':'
                if ":" in uris[module]:
                    proto = "ssh"
                    if ":/" in uris[module]:
                        url = "gitsm://" + uris[module].replace(':/', '/', 1)
                    else:
                        url = "gitsm://" + uris[module].replace(':', '/', 1)
                else: # Fall back to 'file' if there is no ':'
                    proto = "file"
                    url = "gitsm://" + uris[module]
            else:
                proto = uris[module].split(':', 1)[0]
                url = uris[module].replace('%s:' % proto, 'gitsm:', 1)

            url += ';protocol=%s' % proto
            url += ";name=%s" % module
            url += ";bareclone=1;nobranch=1;subpath=%s" % paths[module]

            ld = d.createCopy()
            # Not necessary to set SRC_URI, since we're passing the URI to
            # Fetch.
            #ld.setVar('SRC_URI', url)
            ld.setVar('SRCREV_%s' % module, module_hash)

            # Workaround for issues with SRCPV/SRCREV_FORMAT errors
            # error refer to 'multiple' repositories.  Only the repository
            # in the original SRC_URI actually matters...
            ld.setVar('SRCPV', d.getVar('SRCPV'))
            ld.setVar('SRCREV_FORMAT', module)

            newfetch = Fetch([url], ld, cache=False)
            newfetch.unpack(root=os.path.join(repo_conf, 'modules'))
            local_paths[module] = newfetch.localpath(url)

            # Correct the submodule references to the local download version...
            runfetchcmd("%(basecmd)s config submodule.%(module)s.url %(url)s" % {'basecmd': ud.basecmd, 'module': module, 'url' : local_paths[module]}, d, workdir=ud.destdir)

            if ud.shallow:
                runfetchcmd("%(basecmd)s config submodule.%(module)s.shallow true" % {'basecmd': ud.basecmd, 'module': module}, d, workdir=ud.destdir)

            # Ensure the submodule repository is NOT set to bare, since we're checking it out...
            runfetchcmd("%s config core.bare false" % (ud.basecmd), d, quiet=True, workdir=os.path.join(repo_conf, 'modules', paths[module]))

        return modules_updated

    def unpack(self, ud, destdir, d):
        Git.unpack(self, ud, destdir, d)

        # Copy over the submodules' fetched histories too.
        if ud.bareclone:
            repo_conf = ud.destdir
        else:
            repo_conf = os.path.join(ud.destdir, '.git')

        if self.unpack_submodules(repo_conf, ud, d):
            # Run submodule update, this sets up the directories -- without touching the config
            runfetchcmd("%s submodule update --recursive --no-fetch" % (ud.basecmd), d, quiet=True, workdir=ud.destdir)
