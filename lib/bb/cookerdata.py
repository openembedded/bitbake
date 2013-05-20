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

    def setConfigParameters(self, parameters):
        self.params = parameters
        for key, val in parameters.options.__dict__.items():
            setattr(self, key, val)

    def setServerRegIdleCallback(self, srcb):
        self.server_register_idlecallback = srcb

