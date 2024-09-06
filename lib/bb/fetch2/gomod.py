"""
BitBake 'Fetch' implementation for Go modules

The gomod fetcher is used to download Go modules to the module cache from a
module proxy.

Example SRC_URI:

SRC_URI += "gomod://golang.org/x/net;version=v0.9.0;sha256sum=..."

Required SRC_URI parameters:

- version
    The version of the module.

Optional SRC_URI parameters:

- mod
    Fetch and unpack the go.mod file only instead of the complete module.
    The go command may need to download go.mod files for many different modules
    when computing the build list, and go.mod files are much smaller than
    module zip files.
    The default is "0", set mod=1 for the go.mod file only.

- sha256sum
    The checksum of the module zip file, or the go.mod file in case of fetching
    only the go.mod file. Alternatively, set the SRC_URI varible flag for
    "module@version.sha256sum".

Related variables:

- GO_MOD_PROXY
    The module proxy used by the fetcher.

- GO_MOD_CACHE_DIR
    The directory where the module cache is located.
    This must match the exported GOMODCACHE variable for the go command to find
    the downloaded modules.

See the Go modules reference, https://go.dev/ref/mod, for more information
about the module cache, module proxies and version control systems.
"""

import os
import re
import shutil
import zipfile

import bb
from bb.fetch2 import FetchError
from bb.fetch2 import MissingParameterError
from bb.fetch2.wget import Wget


def escape(path):
    """Escape capital letters using exclamation points."""
    return re.sub(r'([A-Z])', lambda m: '!' + m.group(1).lower(), path)


class GoMod(Wget):
    """Class to fetch Go modules from a Go module proxy via wget"""

    def supports(self, ud, d):
        """Check to see if a given URL is for this fetcher."""
        return ud.type == 'gomod'

    def urldata_init(self, ud, d):
        """Set up to download the module from the module proxy.

        Set up to download the module zip file to the module cache directory
        and unpack the go.mod file (unless downloading only the go.mod file):

        cache/download/<module>/@v/<version>.zip: The module zip file.
        cache/download/<module>/@v/<version>.mod: The go.mod file.
        """

        proxy = d.getVar('GO_MOD_PROXY') or 'proxy.golang.org'
        moddir = d.getVar('GO_MOD_CACHE_DIR') or 'pkg/mod'

        if 'version' not in ud.parm:
            raise MissingParameterError('version', ud.url)

        module = ud.host + ud.path
        ud.parm['module'] = module

        # Set URL and filename for wget download
        path = escape(module + '/@v/' + ud.parm['version'])
        if ud.parm.get('mod', '0') == '1':
            path += '.mod'
        else:
            path += '.zip'
            ud.parm['unpack'] = '0'
        ud.url = bb.fetch2.encodeurl(
            ('https', proxy, '/' + path, None, None, None))
        ud.parm['downloadfilename'] = path

        # Set name parameter if sha256sum is set in recipe
        name = f"{module}@{ud.parm['version']}"
        if d.getVarFlag('SRC_URI', name + '.sha256sum'):
            ud.parm['name'] = name

        # Set subdir for unpack
        ud.parm['subdir'] = os.path.join(moddir, 'cache/download',
                                         os.path.dirname(path))

        super().urldata_init(ud, d)

    def unpack(self, ud, rootdir, d):
        """Unpack the module in the module cache."""

        # Unpack the module zip file or go.mod file
        super().unpack(ud, rootdir, d)

        if ud.localpath.endswith('.zip'):
            # Unpack the go.mod file from the zip file
            module = ud.parm['module']
            unpackdir = os.path.join(rootdir, ud.parm['subdir'])
            name = os.path.basename(ud.localpath).rsplit('.', 1)[0] + '.mod'
            bb.note(f"Unpacking {name} to {unpackdir}/")
            with zipfile.ZipFile(ud.localpath) as zf:
                with open(os.path.join(unpackdir, name), mode='wb') as mf:
                    try:
                        f = module + '@' + ud.parm['version'] + '/go.mod'
                        shutil.copyfileobj(zf.open(f), mf)
                    except KeyError:
                        # If the module does not have a go.mod file, synthesize
                        # one containing only a module statement.
                        mf.write(f'module {module}\n'.encode())
