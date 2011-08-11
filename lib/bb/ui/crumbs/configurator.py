#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2011        Intel Corporation
#
# Authored by Joshua Lock <josh@linux.intel.com>
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

import gobject
import copy
import re, os
from bb import data

class Configurator(gobject.GObject):

    """
    A GObject to handle writing modified configuration values back
    to conf files.
    """
    __gsignals__ = {
        "layers-loaded"  : (gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE,
                           ()),
        "layers-changed" : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                            ())
    }

    def __init__(self):
        gobject.GObject.__init__(self)
        self.local = None
        self.bblayers = None
        self.enabled_layers = {}
        self.loaded_layers = {}
        self.config = {}
        self.orig_config = {}

    # NOTE: cribbed from the cooker...
    def _parse(self, f, data, include=False):
        try:
            return bb.parse.handle(f, data, include)
        except (IOError, bb.parse.ParseError) as exc:
            parselog.critical("Unable to parse %s: %s" % (f, exc))
            sys.exit(1)

    def _loadLocalConf(self, path):
        def getString(var):
            return bb.data.getVar(var, data, True) or ""

        self.local = path

        if self.orig_config:
            del self.orig_config
            self.orig_config = {}

        data = bb.data.init()
        data = self._parse(self.local, data)

        # We only need to care about certain variables
        mach = getString('MACHINE')
        if mach and mach != self.config.get('MACHINE', ''):
            self.config['MACHINE'] = mach
        sdkmach = getString('SDKMACHINE')
        if sdkmach and sdkmach != self.config.get('SDKMACHINE', ''):
            self.config['SDKMACHINE'] = sdkmach
        distro = getString('DISTRO')
        if distro and distro != self.config.get('DISTRO', ''):
            self.config['DISTRO'] = distro
        bbnum = getString('BB_NUMBER_THREADS')
        if bbnum and bbnum != self.config.get('BB_NUMBER_THREADS', ''):
            self.config['BB_NUMBER_THREADS'] = bbnum
        pmake = getString('PARALLEL_MAKE')
        if pmake and pmake != self.config.get('PARALLEL_MAKE', ''):
            self.config['PARALLEL_MAKE'] = pmake
        pclass = getString('PACKAGE_CLASSES')
        if pclass and pclass != self.config.get('PACKAGE_CLASSES', ''):
            self.config['PACKAGE_CLASSES'] = pclass
        fstypes = getString('IMAGE_FSTYPES')
        if fstypes and fstypes != self.config.get('IMAGE_FSTYPES', ''):
            self.config['IMAGE_FSTYPES'] = fstypes

        # Values which aren't always set in the conf must be explicitly
        # loaded as empty values for save to work
        incompat = getString('INCOMPATIBLE_LICENSE')
        if incompat and incompat != self.config.get('INCOMPATIBLE_LICENSE', ''):
            self.config['INCOMPATIBLE_LICENSE'] = incompat
        else:
            self.config['INCOMPATIBLE_LICENSE'] = ""

        # Non-standard, namespaces, variables for GUI preferences
        toolchain = getString('HOB_BUILD_TOOLCHAIN')
        if toolchain and toolchain != self.config.get('HOB_BUILD_TOOLCHAIN', ''):
            self.config['HOB_BUILD_TOOLCHAIN'] = toolchain
        header = getString('HOB_BUILD_TOOLCHAIN_HEADERS')
        if header and header != self.config.get('HOB_BUILD_TOOLCHAIN_HEADERS', ''):
            self.config['HOB_BUILD_TOOLCHAIN_HEADERS'] = header

        self.orig_config = copy.deepcopy(self.config)

    def setLocalConfVar(self, var, val):
        self.config[var] = val

    def getLocalConfVar(self, var):
        if var in self.config:
            return self.config[var]
        else:
            return ""

    def _loadLayerConf(self, path):
        self.bblayers = path
        self.enabled_layers = {}
        self.loaded_layers = {}
        data = bb.data.init()
        data = self._parse(self.bblayers, data)
        layers = (bb.data.getVar('BBLAYERS', data, True) or "").split()
        for layer in layers:
            # TODO: we may be better off calling the layer by its
            # BBFILE_COLLECTIONS value?
            name = self._getLayerName(layer)
            self.loaded_layers[name] = layer

        self.enabled_layers = copy.deepcopy(self.loaded_layers)
        self.emit("layers-loaded")

    def _addConfigFile(self, path):
        pref, sep, filename = path.rpartition("/")
        if filename == "local.conf" or filename == "hob.local.conf":
            self._loadLocalConf(path)
        elif filename == "bblayers.conf":
            self._loadLayerConf(path)

    def _splitLayer(self, path):
        # we only care about the path up to /conf/layer.conf
        layerpath, conf, end = path.rpartition("/conf/")
        return layerpath

    def _getLayerName(self, path):
        # Should this be the collection name?
        layerpath, sep, name = path.rpartition("/")
        return name

    def disableLayer(self, layer):
        if layer in self.enabled_layers:
            del self.enabled_layers[layer]

    def addLayerConf(self, confpath):
        layerpath = self._splitLayer(confpath)
        name = self._getLayerName(layerpath)

        if not layerpath or not name:
            return None, None
        elif name not in self.enabled_layers:
            self.addLayer(name, layerpath)
            return name, layerpath
        else:
            return name, None

    def addLayer(self, name, path):
        self.enabled_layers[name] = path

    def _isLayerConfDirty(self):
        # if a different number of layers enabled to what was
        # loaded, definitely different
        if len(self.enabled_layers) != len(self.loaded_layers):
            return True

        for layer in self.loaded_layers:
            # if layer loaded but no longer present, definitely dirty
            if layer not in self.enabled_layers:
                return True

        for layer in self.enabled_layers:
            # if this layer wasn't present at load, definitely dirty
            if layer not in self.loaded_layers:
                return True
            # if this layers path has changed, definitely dirty
            if self.enabled_layers[layer] != self.loaded_layers[layer]:
                return True

        return False

    def _constructLayerEntry(self):
        """
        Returns a string representing the new layer selection
        """
        layers = self.enabled_layers.copy()
        # Construct BBLAYERS entry
        layer_entry = "BBLAYERS = \" \\\n"
        if 'meta' in layers:
            layer_entry = layer_entry + "  %s \\\n" % layers['meta']
            del layers['meta']
        for layer in layers:
            layer_entry = layer_entry + "  %s \\\n" % layers[layer]
        layer_entry = layer_entry + "  \""

        return "".join(layer_entry)

    def writeConfFile(self, conffile, contents):
        """
        Make a backup copy of conffile and write a new file in its stead with
        the lines in the contents list.
        """
        # Create a backup of the conf file
        bkup = "%s~" % conffile
        os.rename(conffile, bkup)

        # Write the contents list object to the conf file
        with open(conffile, "w") as new:
            new.write("".join(contents))

    def writeLocalConf(self):
        # Dictionary containing only new or modified variables
        changed_values = {}
        for var in self.config:
            val = self.config[var]
            if self.orig_config.get(var, None) != val:
                changed_values[var] = val

        if not len(changed_values):
            return

        # read the original conf into a list
        with open(self.local, 'r') as config:
            config_lines = config.readlines()

        new_config_lines = ["\n"]
        for var in changed_values:
            # Convenience function for re.subn(). If the pattern matches
            # return a string which contains an assignment using the same
            # assignment operator as the old assignment.
            def replace_val(matchobj):
                var = matchobj.group(1) # config variable
                op = matchobj.group(2) # assignment operator
                val = changed_values[var] # new config value
                return "%s %s \"%s\"" % (var, op, val)

            pattern = '^\s*(%s)\s*([+=?.]+)(.*)' % re.escape(var)
            p = re.compile(pattern)
            cnt = 0
            replaced = False

            # Iterate over the local.conf lines and if they are a match
            # for the pattern comment out the line and append a new line
            # with the new VAR op "value" entry
            for line in config_lines:
                new_line, replacements = p.subn(replace_val, line)
                if replacements:
                    config_lines[cnt] = "#%s" % line
                    new_config_lines.append(new_line)
                    replaced = True
                cnt = cnt + 1

            if not replaced:
                new_config_lines.append("%s = \"%s\"\n" % (var, changed_values[var]))

        # Add the modified variables
        config_lines.extend(new_config_lines)

        self.writeConfFile(self.local, config_lines)

        del self.orig_config
        self.orig_config = copy.deepcopy(self.config)

    def insertTempBBPath(self, bbpath, bbfiles):
        # read the original conf into a list
        with open(self.local, 'r') as config:
            config_lines = config.readlines()

        if bbpath:
            config_lines.append("BBPATH := \"${BBPATH}:%s\"\n" % bbpath)
        if bbfiles:
            config_lines.append("BBFILES := \"${BBFILES} %s\"\n" % bbfiles)

        self.writeConfFile(self.local, config_lines)

    def writeLayerConf(self):
        # If we've not added/removed new layers don't write
        if not self._isLayerConfDirty():
            return

        # This pattern should find the existing BBLAYERS
        pattern = 'BBLAYERS\s=\s\".*\"'

        replacement = self._constructLayerEntry()

        with open(self.bblayers, "r") as f:
            contents = f.read()
            p = re.compile(pattern, re.DOTALL)
            new = p.sub(replacement, contents)

        self.writeConfFile(self.bblayers, new)

        # set loaded_layers for dirtiness tracking
        self.loaded_layers = copy.deepcopy(self.enabled_layers)

        self.emit("layers-changed")

    def configFound(self, handler, path):
        self._addConfigFile(path)

    def loadConfig(self, path):
        self._addConfigFile(path)
