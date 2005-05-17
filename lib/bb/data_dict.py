# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Data-Dict' implementation

Functions for interacting with the data structure used by the
BitBake build tools.

Copyright (C) 2003, 2004  Chris Larson
Copyright (C) 2005        Holger Hans Peter Freyther

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

import os, re, sys, types
from   bb import note, debug, fatal

__setvar_regexp__ = {}
__setvar_regexp__["_append"]  = re.compile('(?P<base>.*?)%s(_(?P<add>.*))?' % "_append")
__setvar_regexp__["_prepend"] = re.compile('(?P<base>.*?)%s(_(?P<add>.*))?' % "_prepend")
__setvar_regexp__["_delete"]  = re.compile('(?P<base>.*?)%s(_(?P<add>.*))?' % "_delete")

__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")


class DataDict:
    def __init__(self):
        self.dict = {}

    def expand(self,s, varname):
        def var_sub(match):
            key = match.group()[2:-1]
            if varname and key:
                if varname == key:
                    raise Exception("variable %s references itself!" % varname)
            var = self.getVar(key, 1)
            if var is not None:
                return var
            else:
                return match.group()

        def python_sub(match):
            import bb
            code = match.group()[3:-1]
            locals()['d'] = self
            s = eval(code)
            if type(s) == types.IntType: s = str(s)
            return s

        if type(s) is not types.StringType: # sanity check
            return s

        while s.find('$') != -1:
            olds = s
            try:
                s = __expand_var_regexp__.sub(var_sub, s)
                s = __expand_python_regexp__.sub(python_sub, s)
                if s == olds: break
                if type(s) is not types.StringType: # sanity check
                    import bb
                    bb.error('expansion of %s returned non-string %s' % (olds, s))
            except KeyboardInterrupt:
                raise
            except:
                note("%s:%s while evaluating:\n%s" % (sys.exc_info()[0], sys.exc_info()[1], s))
                raise
        return s

    def initVar(self, var):
        if not var in self.dict:
            self.dict[var] = {}

        if not "flags" in self.dict[var]:
            self.dict[var]["flags"] = {}

    def setVar(self,var,value):
        for v in ["_append", "_prepend", "_delete"]:
            match = __setvar_regexp__[v].match(var)

            if match:
                base = match.group('base')
                override = match.group('add')
                l = self.getVarFlag(base, v) or []
                if override == 'delete':
                    if l.count([value, None]):
                        del l[l.index([value, None])]
                l.append([value, override])
                self.setVarFlag(base, v, l)
                return

        self.initVar(var)
        if self.getVarFlag(var, 'matchesenv'):
            self.delVarFlag(var, 'matchesenv')
            self.setVarFlag(var, 'export', 1)
        self.dict[var]["content"] = value

    def getVar(self,var,exp):
        if not var in self.dict or not "content" in self.dict[var]:
            return None

        if exp:
            return self.expand(self.dict[var]["content"], var)
        return self.dict[var]["content"]

    def delVar(self,var):
        if var in self.dict:
            del self.dict[var]

    def setVarFlag(self,var,flag,flagvalue):
        self.initVar(var)
        self.dict[var]["flags"][flag] = flagvalue

    def getVarFlag(self,var,flag):
        if var in self.dict and "flags" in self.dict[var] and flag in self.dict[var]["flags"]:
            di = self.dict[var]
            di = di["flags"]
            return di[flag]
        return None

    def delVarFlag(self,var,flag):
        if var in self.dict and "flags" in self.dict[var] and flag in self.dict[var]["flags"]:
            del self.dict[var]["flags"][flag]

    def setVarFlags(self,var,flags):
        self.initVar(var)
        if flags == None:
            debug("Setting Null Flag %s" % var)

        self.dict[var]["flags"] = flags

    def getVarFlags(self,var):
        if var in self.dict and "flags" in self.dict[var]:
            return self.dict[var]["flags"]

        return None

    def delVarFlags(self,var):
        if var in self.dict and "flags" in self.dict[var]:
            del self.dict[var]["flags"]

    # Dictionary Methods
    def keys(self):
        return self.dict.keys()

    def iterkeys(self):
        return self.dict.iterkeys()

    def iteritems(self):
        return self.dict.iteritems()

    def items(self):
        return self.dict.items()

    def __getitem__(self,y):
        return self.dict.__getitem__(y)

    def __setitem__(self,x,y):
        self.dict.__setitem__(x,y)

