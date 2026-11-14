#
# Copyright BitBake Contributors
#
# SPDX-License-Identifier: GPL-2.0-only
#

import argparse
import logging
import os

logger = logging.getLogger('bitbake-layers')


class LayerPlugin():
    def __init__(self):
        self.tinfoil = None
        self.bblayers = []
        self.layerdata = {}

    def tinfoil_init(self, tinfoil):
        self.tinfoil = tinfoil
        self.bblayers = (self.tinfoil.config_data.getVar('BBLAYERS') or "").split()
        self.layerdata = self.tinfoil.config_data.getVar('layerdata', False) or {}

    @staticmethod
    def add_command(subparsers, cmdname, function, parserecipes=True, *args, **kwargs):
        """Convert docstring for function to help."""
        docsplit = function.__doc__.splitlines()
        help = docsplit[0]
        if len(docsplit) > 1:
            desc = '\n'.join(docsplit[1:])
        else:
            desc = help
        subparser = subparsers.add_parser(cmdname, *args, help=help, description=desc, formatter_class=argparse.RawTextHelpFormatter, **kwargs)
        subparser.set_defaults(func=function, parserecipes=parserecipes)
        return subparser

    def get_layer_name(self, layerdir):
        return os.path.basename(layerdir.rstrip(os.sep))

    def get_file_layerdir(self, filename):
        """Return the directory of the configured layer containing filename, or None"""
        candidates = [filename]
        realfn = os.path.realpath(filename)
        if realfn != filename:
            candidates.append(realfn)
        # Layers can't nest so the first match is the only match
        for fn in candidates:
            for layer in self.layerdata.values():
                if fn.startswith(layer.path + os.sep):
                    return layer.path
        return None

    def get_file_layer(self, filename):
        layerdir = self.get_file_layerdir(filename)
        if layerdir:
            return self.get_layer_name(layerdir)
        else:
            return '?'
