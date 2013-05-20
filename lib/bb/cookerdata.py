#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2003 - 2005 Michael 'Mickey' Lauer
# Copyright (C) 2005        Holger Hans Peter Freyther
# Copyright (C) 2005        ROAD GmbH
# Copyright (C) 2006        Richard Purdie
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

import os, sys
from functools import wraps
import logging
from bb import data

logger      = logging.getLogger("BitBake")
parselog    = logging.getLogger("BitBake.Parsing")

class ConfigParameters(object):
    def __init__(self):
        self.options, targets = self.parseCommandLine()
        self.environment = self.parseEnvironment()

        self.options.pkgs_to_build = targets or []

        self.options.tracking = False
        if self.options.show_environment:
            self.options.tracking = True

        for key, val in self.options.__dict__.items():
            setattr(self, key, val)

    def parseCommandLine(self):
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
            bbpkgs, error = server.runCommand(["getVariable", "BBPKGS"])
            if error:
                raise Exception("Unable to get the value of BBPKGS from the server: %s" % error)
            if bbpkgs:
                self.options.pkgs_to_build.extend(bbpkgs.split())

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
            elif len(self.options.pkgs_to_build) > 0:
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
        self.debug_domains = []
        self.extra_assume_provided = []
        self.prefile = []
        self.postfile = []
        self.debug = 0
        self.cmd = None
        self.abort = True
        self.force = False
        self.ui = None
        self.profile = False
        self.nosetscene = False
        self.invalidate_stamp = False
        self.dump_signatures = False
        self.dry_run = False

    def setConfigParameters(self, parameters):
        self.params = parameters
        for key in self.__dict__.keys():
            if key in parameters.options.__dict__:
                setattr(self, key, parameters.options.__dict__[key])

    def setServerRegIdleCallback(self, srcb):
        self.server_register_idlecallback = srcb

def catch_parse_error(func):
    """Exception handling bits for our parsing"""
    @wraps(func)
    def wrapped(fn, *args):
        try:
            return func(fn, *args)
        except (IOError, bb.parse.ParseError, bb.data_smart.ExpansionError) as exc:
            parselog.critical("Unable to parse %s: %s" % (fn, exc))
            sys.exit(1)
    return wrapped

@catch_parse_error
def _parse(fn, data, include=True):
    return bb.parse.handle(fn, data, include)

@catch_parse_error
def _inherit(bbclass, data):
    bb.parse.BBHandler.inherit(bbclass, "configuration INHERITs", 0, data)
    return data

def findConfigFile(configfile):
    path = os.getcwd()
    while path != "/":
        confpath = os.path.join(path, "conf", configfile)
        if os.path.exists(confpath):
            return confpath

        path, _ = os.path.split(path)
    return None

class CookerDataBuilder(object):

    def __init__(self, params, worker = False):

        self.prefiles = params.prefile
        self.postfiles = params.postfile
        self.tracking = params.tracking

        self.data = bb.data.init()
        if self.tracking:
            self.data.enableTracking()

        # Keep a datastore of the initial environment variables and their
        # values from when BitBake was launched to enable child processes
        # to use environment variables which have been cleaned from the
        # BitBake processes env
        self.savedenv = bb.data.init()
        savedenv = params.environment
        for k in savedenv:
            self.savedenv.setVar(k, savedenv[k])

        filtered_keys = bb.utils.approved_variables()
        bb.data.inheritFromOS(self.data, self.savedenv, filtered_keys)
        self.data.setVar("BB_ORIGENV", self.savedenv)
        
        if worker:
            self.data.setVar("BB_WORKERCONTEXT", "1")

    def parseBaseConfiguration(self):
        try:
            self.parseConfigurationFiles(self.prefiles, self.postfiles)
        except SyntaxError:
            sys.exit(1)
        except Exception:
            logger.exception("Error parsing configuration files")
            sys.exit(1)

    def _findLayerConf(self):
        return findConfigFile("bblayers.conf")

    def parseConfigurationFiles(self, prefiles, postfiles):
        data = self.data
        bb.parse.init_parser(data)

        # Parse files for loading *before* bitbake.conf and any includes
        for f in prefiles:
            data = _parse(f, data)

        layerconf = self._findLayerConf()
        if layerconf:
            parselog.debug(2, "Found bblayers.conf (%s)", layerconf)
            data = _parse(layerconf, data)

            layers = (data.getVar('BBLAYERS', True) or "").split()

            data = bb.data.createCopy(data)
            for layer in layers:
                parselog.debug(2, "Adding layer %s", layer)
                data.setVar('LAYERDIR', layer)
                data = _parse(os.path.join(layer, "conf", "layer.conf"), data)
                data.expandVarref('LAYERDIR')

            data.delVar('LAYERDIR')

        if not data.getVar("BBPATH", True):
            raise SystemExit("The BBPATH variable is not set")

        data = _parse(os.path.join("conf", "bitbake.conf"), data)

        # Parse files for loading *after* bitbake.conf and any includes
        for p in postfiles:
            data = _parse(p, data)

        # Handle any INHERITs and inherit the base class
        bbclasses  = ["base"] + (data.getVar('INHERIT', True) or "").split()
        for bbclass in bbclasses:
            data = _inherit(bbclass, data)

        # Nomally we only register event handlers at the end of parsing .bb files
        # We register any handlers we've found so far here...
        for var in data.getVar('__BBHANDLERS') or []:
            bb.event.register(var, data.getVar(var))

        if data.getVar("BB_WORKERCONTEXT", False) is None:
            bb.fetch.fetcher_init(data)
        bb.codeparser.parser_cache_init(data)
        bb.event.fire(bb.event.ConfigParsed(), data)

        if data.getVar("BB_INVALIDCONF") is True:
            data.setVar("BB_INVALIDCONF", False)
            self.parseConfigurationFiles(self.prefiles, self.postfiles)
            return

        bb.parse.init_parser(data)
        data.setVar('BBINCLUDED',bb.parse.get_file_depends(data))
        self.data = data
        self.data_hash = data.get_hash()



