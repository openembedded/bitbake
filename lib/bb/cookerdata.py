
#
# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2003 - 2005 Michael 'Mickey' Lauer
# Copyright (C) 2005        Holger Hans Peter Freyther
# Copyright (C) 2005        ROAD GmbH
# Copyright (C) 2006        Richard Purdie
#
# SPDX-License-Identifier: GPL-2.0-only
#

import dataclasses
import logging
import os
import re
import sys
import hashlib
import graphlib
import glob
from functools import wraps

import bb.cache
import bb.codeparser
import bb.data
import bb.data_smart
import bb.event
import bb.fetch
import bb.parse
import bb.utils

logger      = logging.getLogger("BitBake")
parselog    = logging.getLogger("BitBake.Parsing")

class ConfigParameters(object):
    def __init__(self, argv=None):
        self.options, targets = self.parseCommandLine(argv or sys.argv)
        self.environment = self.parseEnvironment()

        self.options.pkgs_to_build = targets or []

        for key, val in self.options.__dict__.items():
            setattr(self, key, val)

    def parseCommandLine(self, argv=sys.argv):
        raise Exception("Caller must implement commandline option parsing")

    def parseEnvironment(self):
        return os.environ.copy()

    def updateFromServer(self, server):
        if not self.options.cmd:
            defaulttask, error = server.runCommand(["getVariable", "BB_DEFAULT_TASK"])
            if error:
                raise Exception("Unable to get the value of BB_DEFAULT_TASK from the server: %s" % error)
            self.options.cmd = defaulttask or "build"
        _, error = server.runCommand(["setConfig", "cmd", self.options.cmd])
        if error:
            raise Exception("Unable to set configuration option 'cmd' on the server: %s" % error)

        if not self.options.pkgs_to_build:
            bbpkgs, error = server.runCommand(["getVariable", "BBTARGETS"])
            if error:
                raise Exception("Unable to get the value of BBTARGETS from the server: %s" % error)
            if bbpkgs:
                self.options.pkgs_to_build.extend(bbpkgs.split())

    def updateToServer(self, server, environment):
        options = {}
        for o in ["halt", "force", "invalidate_stamp",
                  "dry_run", "dump_signatures",
                  "extra_assume_provided", "profile",
                  "prefile", "postfile", "server_timeout",
                  "nosetscene", "setsceneonly", "skipsetscene",
                  "runall", "runonly", "writeeventlog"]:
            options[o] = getattr(self.options, o)

        options['build_verbose_shell'] = self.options.verbose
        options['build_verbose_stdout'] = self.options.verbose
        options['default_loglevel'] = bb.msg.loggerDefaultLogLevel
        options['debug_domains'] = bb.msg.loggerDefaultDomains

        ret, error = server.runCommand(["updateConfig", options, environment, sys.argv])
        if error:
            raise Exception("Unable to update the server configuration with local parameters: %s" % error)

    def parseActions(self):
        # Parse any commandline into actions
        action = {'action':None, 'msg':None}
        if self.options.show_environment:
            if 'world' in self.options.pkgs_to_build:
                action['msg'] = "'world' is not a valid target for --environment."
            elif 'universe' in self.options.pkgs_to_build:
                action['msg'] = "'universe' is not a valid target for --environment."
            elif len(self.options.pkgs_to_build) > 1:
                action['msg'] = "Only one target can be used with the --environment option."
            elif self.options.buildfile and len(self.options.pkgs_to_build) > 0:
                action['msg'] = "No target should be used with the --environment and --buildfile options."
            elif self.options.pkgs_to_build:
                action['action'] = ["showEnvironmentTarget", self.options.pkgs_to_build]
            else:
                action['action'] = ["showEnvironment", self.options.buildfile]
        elif self.options.buildfile is not None:
            action['action'] = ["buildFile", self.options.buildfile, self.options.cmd]
        elif self.options.revisions_changed:
            action['action'] = ["compareRevisions"]
        elif self.options.show_versions:
            action['action'] = ["showVersions"]
        elif self.options.parse_only:
            action['action'] = ["parseFiles"]
        elif self.options.dot_graph:
            if self.options.pkgs_to_build:
                action['action'] = ["generateDotGraph", self.options.pkgs_to_build, self.options.cmd]
            else:
                action['msg'] = "Please specify a package name for dependency graph generation."
        else:
            if self.options.pkgs_to_build:
                action['action'] = ["buildTargets", self.options.pkgs_to_build, self.options.cmd]
            else:
                #action['msg'] = "Nothing to do.  Use 'bitbake world' to build everything, or run 'bitbake --help' for usage information."
                action = None
        self.options.initialaction = action
        return action

class CookerConfiguration(object):
    """
    Manages build options and configurations for one run
    """

    def __init__(self):
        self.debug_domains = bb.msg.loggerDefaultDomains
        self.default_loglevel = bb.msg.loggerDefaultLogLevel
        self.extra_assume_provided = []
        self.prefile = []
        self.postfile = []
        self.cmd = None
        self.halt = True
        self.force = False
        self.profile = False
        self.nosetscene = False
        self.setsceneonly = False
        self.skipsetscene = False
        self.invalidate_stamp = False
        self.dump_signatures = []
        self.build_verbose_shell = False
        self.build_verbose_stdout = False
        self.dry_run = False
        self.tracking = False
        self.skip_fragments = False
        self.writeeventlog = False
        self.limited_deps = False
        self.runall = []
        self.runonly = []

        self.env = {}

    def __getstate__(self):
        state = {}
        for key in self.__dict__.keys():
            state[key] = getattr(self, key)
        return state

    def __setstate__(self,state):
        for k in state:
            setattr(self, k, state[k])


def catch_parse_error(func):
    """Exception handling bits for our parsing"""
    @wraps(func)
    def wrapped(fn, *args):
        try:
            return func(fn, *args)
        except Exception as exc:
            import traceback

            bbdir = os.path.dirname(__file__) + os.sep
            exc_class, exc, tb = sys.exc_info()
            for tb in iter(lambda: tb.tb_next, None):
                # Skip frames in bitbake itself, we only want the metadata
                fn, _, _, _ = traceback.extract_tb(tb, 1)[0]
                if not fn.startswith(bbdir):
                    break
            parselog.critical("Unable to parse %s" % fn, exc_info=(exc_class, exc, tb))
            raise bb.BBHandledException()
    return wrapped

@catch_parse_error
def parse_config_file(fn, data, include=True):
    return bb.parse.handle(fn, data, include, baseconfig=True)

@catch_parse_error
def _inherit(bbclass, data):
    bb.parse.BBHandler.inherit(bbclass, "configuration INHERITs", 0, data)
    return data

def findConfigFile(configfile, data):
    search = []
    bbpath = data.getVar("BBPATH")
    if bbpath:
        for i in bbpath.split(":"):
            search.append(os.path.join(i, "conf", configfile))
    path = os.getcwd()
    while path != "/":
        search.append(os.path.join(path, "conf", configfile))
        path, _ = os.path.split(path)

    for i in search:
        if os.path.exists(i):
            return i

    return None

#
# We search for a conf/bblayers.conf under an entry in BBPATH or in cwd working
# up to /. If that fails, bitbake would fall back to cwd.
#

def findTopdir():
    d = bb.data.init()
    bbpath = None
    if 'BBPATH' in os.environ:
        bbpath = os.environ['BBPATH']
        d.setVar('BBPATH', bbpath)

    layerconf = findConfigFile("bblayers.conf", d)
    if layerconf:
        return os.path.dirname(os.path.dirname(layerconf))

    return os.path.abspath(os.getcwd())

@dataclasses.dataclass
class Layer:
    path: str
    version: str
    compat: set[str] = dataclasses.field(default_factory=set)
    depends: dict[dict] = dataclasses.field(default_factory=dict)
    recommends: dict[dict] = dataclasses.field(default_factory=dict)
    fragment_recommends_any: set[str] = dataclasses.field(default_factory=set)

class CookerDataBuilder(object):

    def __init__(self, cookercfg, worker = False):

        self.prefiles = cookercfg.prefile
        self.postfiles = cookercfg.postfile
        self.tracking = cookercfg.tracking
        self.skip_fragments = cookercfg.skip_fragments

        bb.utils.set_context(bb.utils.clean_context())
        bb.event.set_class_handlers(bb.event.clean_class_handlers())
        self.basedata = bb.data.init()
        if self.tracking:
            self.basedata.enableTracking()
        if self.skip_fragments:
            self.basedata.setVar("_BB_SKIP_FRAGMENTS", "1")

        # Keep a datastore of the initial environment variables and their
        # values from when BitBake was launched to enable child processes
        # to use environment variables which have been cleaned from the
        # BitBake processes env
        self.savedenv = bb.data.init()
        for k in cookercfg.env:
            self.savedenv.setVar(k, cookercfg.env[k])
            if k in bb.data_smart.bitbake_renamed_vars:
                bb.error('Shell environment variable %s has been renamed to %s' % (k, bb.data_smart.bitbake_renamed_vars[k]))
                bb.fatal("Exiting to allow enviroment variables to be corrected")

        filtered_keys = bb.utils.approved_variables()
        bb.data.inheritFromOS(self.basedata, self.savedenv, filtered_keys)
        self.basedata.setVar("BB_ORIGENV", self.savedenv)
        self.basedata.setVar("__bbclasstype", "global")

        if worker:
            self.basedata.setVar("BB_WORKERCONTEXT", "1")

        self.data = self.basedata
        self.mcdata = {}

    def calc_datastore_hashes(self, clean=True):
        if not clean:
            self.data_hash = None
            return

        data_hash = hashlib.sha256()
        data_hash.update(self.data.get_hash().encode('utf-8'))
        multiconfig = (self.data.getVar("BBMULTICONFIG") or "").split()
        for config in multiconfig:
            data_hash.update(self.mcdata[config].get_hash().encode('utf-8'))
        self.data_hash = data_hash.hexdigest()

    def parseBaseConfiguration(self, worker=False):
        mcdata = {}
        try:
            self.data, self.layerdata = self.parseConfigurationFiles(self.prefiles, self.postfiles)

            servercontext = self.data.getVar("BB_WORKERCONTEXT", False) is None and not worker
            bb.fetch.fetcher_init(self.data, servercontext)
            bb.parse.init_parser(self.data)

            bb.event.fire(bb.event.ConfigParsed(), self.data)

            reparse_cnt = 0
            while self.data.getVar("BB_INVALIDCONF", False) is True:
                if reparse_cnt > 20:
                    logger.error("Configuration has been re-parsed over 20 times, "
                                 "breaking out of the loop...")
                    raise Exception("Too deep config re-parse loop. Check locations where "
                                    "BB_INVALIDCONF is being set (ConfigParsed event handlers)")
                self.data.setVar("BB_INVALIDCONF", False)
                self.data, self.layerdata = self.parseConfigurationFiles(self.prefiles, self.postfiles)
                reparse_cnt += 1
                bb.event.fire(bb.event.ConfigParsed(), self.data)

            bb.parse.init_parser(self.data)
            mcdata[''] = self.data

            multiconfig = (self.data.getVar("BBMULTICONFIG") or "").split()
            for config in multiconfig:
                if config[0].isdigit():
                    bb.fatal("Multiconfig name '%s' is invalid as multiconfigs cannot start with a digit" % config)
                parsed_mcdata, _ = self.parseConfigurationFiles(self.prefiles, self.postfiles, config)
                bb.event.fire(bb.event.ConfigParsed(), parsed_mcdata)
                mcdata[config] = parsed_mcdata
            if multiconfig:
                bb.event.fire(bb.event.MultiConfigParsed(mcdata), self.data)

        except bb.data_smart.ExpansionError as e:
            logger.error(str(e))
            raise bb.BBHandledException()

        bb.codeparser.update_module_dependencies(self.data)

        # Handle obsolete variable names
        d = self.data
        renamedvars = d.getVarFlags('BB_RENAMED_VARIABLES') or {}
        renamedvars.update(bb.data_smart.bitbake_renamed_vars)
        issues = False
        for v in renamedvars:
            if d.getVar(v) != None or d.hasOverrides(v):
                issues = True
                loginfo = {}
                history = d.varhistory.get_variable_refs(v)
                for h in history:
                    for line in history[h]:
                        loginfo = {'file' : h, 'line' : line}
                        bb.data.data_smart._print_rename_error(v, loginfo, renamedvars)
                if not history:
                    bb.data.data_smart._print_rename_error(v, loginfo, renamedvars)
        if issues:
            raise bb.BBHandledException()

        for mc in mcdata:
            mcdata[mc].renameVar("__depends", "__base_depends")
            mcdata[mc].setVar("__bbclasstype", "recipe")

        # Create a copy so we can reset at a later date when UIs disconnect
        self.mcorigdata = mcdata
        for mc in mcdata:
            self.mcdata[mc] = bb.data.createCopy(mcdata[mc])
        self.data = self.mcdata['']
        self.calc_datastore_hashes()

    def reset(self):
        # We may not have run parseBaseConfiguration() yet
        if not hasattr(self, 'mcorigdata'):
            return
        for mc in self.mcorigdata:
            self.mcdata[mc] = bb.data.createCopy(self.mcorigdata[mc])
        self.data = self.mcdata['']

    def _findLayerConf(self, data):
        return findConfigFile("bblayers.conf", data)

    def parseConfigurationFiles(self, prefiles, postfiles, mc = ""):
        data = bb.data.createCopy(self.basedata)
        data.setVar("BB_CURRENT_MC", mc)

        # Parse files for loading *before* bitbake.conf and any includes
        for f in prefiles:
            data = parse_config_file(f, data)

        layerconf = self._findLayerConf(data)
        layerdata = {}
        if layerconf:
            parselog.debug2("Found bblayers.conf (%s)", layerconf)
            # By definition bblayers.conf is in conf/ of TOPDIR.
            # We may have been called with cwd somewhere else so reset TOPDIR
            data.setVar("TOPDIR", os.path.dirname(os.path.dirname(layerconf)))
            data = parse_config_file(layerconf, data)

            if not data.getVar("BB_CACHEDIR"):
                data.setVar("BB_CACHEDIR", "${TOPDIR}/cache")

            bb.codeparser.parser_cache_init(data.getVar("BB_CACHEDIR"))

            layers = (data.getVar('BBLAYERS') or "").split()
            broken_layers = []

            if not layers:
                bb.fatal("The bblayers.conf file doesn't contain any BBLAYERS definition")

            data = bb.data.createCopy(data)
            approved = bb.utils.approved_variables()

            # Check whether present layer directories exist
            for layer in layers:
                if not os.path.isdir(layer):
                    broken_layers.append(layer)

            if broken_layers:
                parselog.critical("The following layer directories do not exist:")
                for layer in broken_layers:
                    parselog.critical("   %s", layer)
                parselog.critical("Please check BBLAYERS in %s" % (layerconf))
                raise bb.BBHandledException()

            bitbakedir = os.path.realpath(os.path.dirname(__file__) + "/../../")
            data.setVar("LAYERDIR_bitbake", bitbakedir)
            data.setVarFlag("LAYERDIR_bitbake", "vardepvalue", "")

            layerseries = None
            layer_safevars = tuple()
            errors = []
            for layer in layers:
                parselog.debug2("Adding layer %s" % layer)
                if 'HOME' in approved and '~' in layer:
                    layer = os.path.expanduser(layer)
                if layer.endswith('/'):
                    layer = layer.rstrip('/')
                layer = os.path.realpath(layer)

                ld = data.createCopy()
                ld.setVar('LAYERDIR', layer)
                #ld.setVar('LAYERDIR_RE', re.escape(layer))
                ld = parse_config_file(os.path.join(layer, "conf", "layer.conf"), ld)

                layername = ld.getVar("LAYERNAME")
                if not layername:
                    errors.append("Layer %s does not set LAYERNAME" % layer)
                    continue
                if layername in layerdata:
                    errors.append("LAYERNAME %s is used by both %s and %s" % (layername, layer, layerdata[layername].path))
                    continue

                nested = False
                for pathcheck in layerdata:
                    otherpath = layerdata[pathcheck].path
                    if layer.startswith(otherpath + "/") or otherpath.startswith(layer + "/"):
                        errors.append("Layer path %s (layer %s) conflicts with path %s from layer %s. Layers can't nest." % (layer, layername, otherpath, pathcheck))
                        nested = True
                if nested:
                    continue

                def getVar(var, layername, ld):
                    value = ld.getVar(var)
                    if not value:
                        value = ld.getVar("%s_%s" % (var, layername))
                    return value

                layerdata[layername] = Layer(
                    path=layer,
                    version=getVar("LAYERVERSION", layername, ld) or "1",
                    compat=set((getVar("LAYERSERIES_COMPAT", layername, ld) or "").split()),
                    depends=bb.utils.explode_dep_versions2(getVar("LAYERDEPENDS", layername, ld) or ""),
                    recommends=bb.utils.explode_dep_versions2(getVar("LAYERRECOMMENDS", layername, ld) or ""),
                    fragment_recommends_any=set((getVar("LAYER_FRAGMENT_RECOMMENDS_ANY", layername, ld) or "").split()),
                )

                if not layerdata[layername].compat:
                    errors.append("Layer %s should set LAYERSERIES_COMPAT in its conf/layer.conf file to list the core layer names it is compatible with." % (layername))

                if not layerseries:
                    layerseries = set((ld.getVar("LAYERSERIES_CORENAMES") or "").split())
                if not layer_safevars:
                    layer_safevars = tuple((ld.getVar("LAYER_PASSTHROUGH_VARS_PREFIXES") or "").split())

                for var in ld:
                    if var.startswith(("LAYERNAME", "LAYERDEPENDS", "LAYERRECOMMENDS", "LAYERVERSION", "LAYERSERIES_COMPAT", "LAYERSERIES_CORENAMES", "LAYERDIR",  "LAYER_FRAGMENT_RECOMMENDS_ANY", "LAYER_PASSTHROUGH_VARS_PREFIXES")):
                        continue
                    if var.startswith(("BBFILE_COLLECTIONS", "BBFILE_PRIORITY", "BBFILE_PATTERN")):
                        bb.warn("Support for %s was removed and the variable is being ignored but is set by layer %s" % (var, layer))
                        continue
                    if var in ["BBPATH", "BBFILES", "BBFILES_DYNAMIC"]:
                        if ld.getVar(var) != data.getVar(var):
                            bb.warn("%s now set automatically, the variable is being ignored but is set by layer %s" % (var, layer))
                            bb.warn(str(ld.getVar(var, expand=False)))
                        continue
                    if var in data and (ld.getVar(var) == data.getVar(var)):
                        continue
                    if var.startswith(layer_safevars):
                        pass
                    elif var.startswith(("BBLAYERS_LAYERINDEX_NAME", "BB_GLOBAL_PYMODULES")):
                        pass
                    elif var == "__depends":
                        pass
                    else:
                        bb.warn("Variable %s is set by %s and will be ignored" % (var, layer))
                    data.setVar(var, ld.getVar(var))

            if not layerseries:
                errors.append("No layer sets LAYERSERIES_CORENAMES")
            data.setVar("LAYERSERIES_CORENAMES", " ".join(sorted(layerseries)))
            data.setVar("LAYER_PASSTHROUGH_VARS_PREFIXES", " ".join(layer_safevars))

            layers = set(layerdata)
            for layer in layerdata:
                data.setVar("LAYERDIR_%s" % layer, layerdata[layer].path)
                data.setVarFlag("LAYERDIR_%s" % layer, "vardepvalue", "")
                if not (layerdata[layer].compat & layerseries):
                    errors.append("Layer %s is not compatible with the core layer which only supports these series: %s (layer is compatible with %s)"
                              % (layer, " ".join(layerseries), " ".join(layerdata[layer].compat)))

                # Check dependencies
                if not set(layerdata[layer].depends).issubset(layers):
                    errors.append("Layer %s depends on %s but that layer isn't configured" % (layer, " ".join(set(layerdata[layer].depends) - layers)))
                    continue

                # Check dependency versions
                for dep in layerdata[layer].depends:
                    for verop in layerdata[layer].depends[dep]:
                        (op, depver) = verop.split()
                        layerver = layerdata[dep].version
                        if not layerver:
                            errors.append("Layer '%s' depends on version %s of layer '%s', which exists in your configuration but does not specify a version. Check that you are using the correct matching versions/branches of these two layers." % (layer, verop, dep))
                            continue
                        try:
                            res = bb.utils.vercmp_string_op(layerver, depver, op)
                        except bb.utils.VersionStringException as vse:
                            bb.fatal('Error parsing LAYERDEPENDS for layer %s: %s' % (layer, str(vse)))
                        if not res:
                            errors.append("Layer '%s' depends on version %s of layer '%s', but version %s is currently enabled in your configuration. Check that you are using the correct matching versions/branches of these two layers." % (layer, verop, dep, layerver))

                # Check recommends versions
                for dep in layerdata[layer].recommends:
                    for verop in layerdata[layer].recommends[dep]:
                        if dep not in layerdata:
                            continue
                        (op, depver) = verop.split()
                        layerver = layerdata[dep].version
                        if not layerver:
                            errors.append("Layer '%s' recommends version %s of layer '%s', which exists in your configuration but does not specify a version. Check that you are using the correct matching versions/branches of these two layers." % (layer, verop, dep))
                            continue
                        try:
                            res = bb.utils.vercmp_string_op(layerver, depver, op)
                        except bb.utils.VersionStringException as vse:
                            bb.fatal('Error parsing LAYERRECOMMENDS for layer %s: %s' % (layer, str(vse)))
                        if not res:
                            errors.append("Layer '%s' recommends version %s of layer '%s', but version %s is currently enabled in your configuration. Check that you are using the correct matching versions/branches of these two layers." % (layer, verop, dep, layerver))

            data.setVar("layerdata", layerdata)

            if errors:
                for error in errors:
                    bb.error(error)
                bb.fatal("Layer errors found, parsing stopped")

            # Using the layer dependencies, work out the order layers should be listed
            # in BBPATH and searched for BBFILES
            layerorder = graphlib.TopologicalSorter()
            for layer in sorted(layerdata.keys()):
                layerorder.add(layer)
                for dep in layerdata[layer].depends:
                    layerorder.add(layer, dep)

            try:
                ordering = list(layerorder.static_order())
            except graphlib.CycleError as exc:
                bb.fatal("Circular dependencies found from LAYERDEPENDS, can't continue. (%s)" % str(exc))

            # Construct BBPATH
            data.setVar("BBPATH", ":".join(["${TOPDIR}"] + [layerdata[layer].path for layer in ordering[::-1]]))

            # Construct BBFILES
            #  - any recipes subdirs are added through a glob
            #  - any /dynamic-recipes/<layername>/ are added if the named layer is present
            bbfiles = []
            for layer in ordering:
                recipes = layerdata[layer].path + "/recipes*"
                if glob.glob(recipes):
                    bbfiles.append(recipes)
                dynamic_recipes = layerdata[layer].path + "/dynamic-recipes"
                if os.path.isdir(dynamic_recipes):
                    for deplayer in os.listdir(dynamic_recipes):
                        if not os.path.isdir(dynamic_recipes + "/" + deplayer):
                            continue
                        if deplayer in layerdata:
                            bbfiles.append(dynamic_recipes + "/" + deplayer)
            data.setVar("BBFILES", " ".join(bbfiles))

        if not data.getVar("BBPATH"):
            msg = "The BBPATH variable is not set"
            if not layerconf:
                msg += (" and bitbake did not find a conf/bblayers.conf file in"
                        " the expected location.\nMaybe you accidentally"
                        " invoked bitbake from the wrong directory?")
            bb.fatal(msg)

        # A directory listed more than once in BBPATH is a configuration
        # error, e.g. a layer in both the BBPATH env var and BBLAYERS. Compare
        # resolved paths so "dir" and "dir/" or a symlink to it also match, and
        # ignore the empty entries left by stray colons
        entries = {}
        for p in data.getVar("BBPATH").split(":"):
            if p:
                entries.setdefault(os.path.realpath(p), []).append(p)
        duplicates = [" ".join(paths) for paths in entries.values() if len(paths) > 1]
        if duplicates:
            bb.fatal("BBPATH contains duplicate entries:\n    %s\nCheck the BBPATH environment variable, bblayers.conf and the layer.conf files." % "\n    ".join(duplicates))

        if not data.getVar("TOPDIR"):
            data.setVar("TOPDIR", os.path.abspath(os.getcwd()))
        if not data.getVar("BB_CACHEDIR"):
            data.setVar("BB_CACHEDIR", "${TOPDIR}/cache")
        bb.codeparser.parser_cache_init(data.getVar("BB_CACHEDIR"))

        data = parse_config_file(os.path.join("conf", "bitbake.conf"), data)

        # Parse files for loading *after* bitbake.conf and any includes
        for p in postfiles:
            data = parse_config_file(p, data)

        # Handle any INHERITs and inherit the base class
        bbclasses  = ["base"] + (data.getVar('INHERIT') or "").split()
        for bbclass in bbclasses:
            data = _inherit(bbclass, data)

        # Normally we only register event handlers at the end of parsing .bb files
        # We register any handlers we've found so far here...
        for var in data.getVar('__BBHANDLERS', False) or []:
            handlerfn = data.getVarFlag(var, "filename", False)
            if not handlerfn:
                parselog.critical("Undefined event handler function '%s'" % var)
                raise bb.BBHandledException()
            handlerln = int(data.getVarFlag(var, "lineno", False))
            bb.event.register(var, data.getVar(var, False),  (data.getVarFlag(var, "eventmask") or "").split(), handlerfn, handlerln, data)

        data.setVar('BBINCLUDED',bb.parse.get_file_depends(data))

        return data, layerdata

    @staticmethod
    def _parse_recipe(bb_data, bbfile, appends, mc, layername):
        bb_data.setVar("__BBMULTICONFIG", mc)
        bb_data.setVar("FILE_LAYERNAME", layername)

        bb_data.setVar("__BB_RECIPE_FILE", bbfile)

        bbfile_loc = os.path.abspath(os.path.dirname(bbfile))
        bb.parse.cached_mtime_noerror(bbfile_loc)

        if appends:
            bb_data.setVar('__BBAPPEND', " ".join(appends))

        layerdir = bb_data.getVar("LAYERDIR_%s" % layername)
        if layerdir:
             conffile = layerdir + "/conf/layervars.conf"
             bb.parse.mark_dependency(bb_data, conffile)
             if os.path.exists(conffile):
                 bb.parse.handle(conffile, bb_data, True, baseconfig=True)

        return bb.parse.handle(bbfile, bb_data)

    def parseRecipeVariants(self, bbfile, appends, virtonly=False, mc=None, layername=None):
        """
        Load and parse one .bb build file
        Return the data and whether parsing resulted in the file being skipped
        """

        if virtonly:
            (bbfile, virtual, mc) = bb.cache.virtualfn2realfn(bbfile)
            bb_data = self.mcdata[mc].createCopy()
            bb_data.setVar("__ONLYFINALISE", virtual or "default")
            return self._parse_recipe(bb_data, bbfile, appends, mc, layername)

        if mc is not None:
            bb_data = self.mcdata[mc].createCopy()
            return self._parse_recipe(bb_data, bbfile, appends, mc, layername)

        bb_data = self.data.createCopy()
        datastores = self._parse_recipe(bb_data, bbfile, appends, '', layername)

        for mc in self.mcdata:
            if not mc:
                continue
            bb_data = self.mcdata[mc].createCopy()
            newstores = self._parse_recipe(bb_data, bbfile, appends, mc, layername)
            for ns in newstores:
                datastores["mc:%s:%s" % (mc, ns)] = newstores[ns]

        return datastores

    def parseRecipe(self, virtualfn, appends, layername):
        """
        Return a complete set of data for fn.
        To do this, we need to parse the file.
        """
        logger.debug("Parsing %s (full)" % virtualfn)
        (fn, virtual, mc) = bb.cache.virtualfn2realfn(virtualfn)
        datastores = self.parseRecipeVariants(virtualfn, appends, virtonly=True, layername=layername)
        return datastores[virtual]
