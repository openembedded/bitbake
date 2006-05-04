# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake Smart Dictionary Implementation

Functions for interacting with the data structure used by the
BitBake build tools.

Copyright (C) 2003, 2004  Chris Larson
Copyright (C) 2004, 2005  Seb Frankengul
Copyright (C) 2005, 2006  Holger Hans Peter Freyther
Copyright (C) 2005        Uli Luckas
Copyright (C) 2005        ROAD GmbH

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

import copy, os, re, sys, time, types
from bb   import note, debug, error, fatal, utils, methodpool
from sets import Set

try:
    import cPickle as pickle
except ImportError:
    import pickle
    print "NOTE: Importing cPickle failed. Falling back to a very slow implementation."

__setvar_keyword__ = ["_append","_prepend"]
__setvar_regexp__ = re.compile('(?P<base>.*?)(?P<keyword>_append|_prepend)(_(?P<add>.*))?')
__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")


class DataSmart:
    def __init__(self):
        self.dict = {}

        # cookie monster tribute
        self._special_values = {}
        self._seen_overrides = {}

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
                    error('expansion of %s returned non-string %s' % (olds, s))
            except KeyboardInterrupt:
                raise
            except:
                note("%s:%s while evaluating:\n%s" % (sys.exc_info()[0], sys.exc_info()[1], s))
                raise
        return s

    def initVar(self, var):
        if not var in self.dict:
            self.dict[var] = {}

    def _findVar(self,var):
        _dest = self.dict

        while (_dest and var not in _dest):
            if not "_data" in _dest:
                _dest = None
                break
            _dest = _dest["_data"]

        if _dest and var in _dest:
            return _dest[var]
        return None

    def _makeShadowCopy(self, var):
        if var in self.dict:
            return

        local_var = self._findVar(var)

        if local_var:
            self.dict[var] = copy.copy(local_var)
        else:
            self.initVar(var)

    def setVar(self,var,value):
        match  = __setvar_regexp__.match(var)
        if match and match.group("keyword") in __setvar_keyword__:
            base = match.group('base')
            keyword = match.group("keyword")
            override = match.group('add')
            l = self.getVarFlag(base, keyword) or []
            l.append([value, override])
            self.setVarFlag(base, keyword, l)

            # pay the cookie monster
            try:
                self._special_values[keyword].add( base )
            except:
                self._special_values[keyword] = Set()
                self._special_values[keyword].add( base )

            # SRC_URI_append_simpad is both a flag and a override
            #if not override in self._seen_overrides:
            #    self._seen_overrides[override] = Set()
            #self._seen_overrides[override].add( base )
            return

        if not var in self.dict:
            self._makeShadowCopy(var)
        if self.getVarFlag(var, 'matchesenv'):
            self.delVarFlag(var, 'matchesenv')
            self.setVarFlag(var, 'export', 1)

        # more cookies for the cookie monster
        if '_' in var:
            override = var[var.rfind('_')+1:]
            if not override in self._seen_overrides:
                self._seen_overrides[override] = Set()
            self._seen_overrides[override].add( var )

        # setting var
        self.dict[var]["content"] = value

    def getVar(self,var,exp):
        value = self.getVarFlag(var,"content")

        if exp and value:
            return self.expand(value,var)
        return value

    def delVar(self,var):
        self.dict[var] = {}

    def setVarFlag(self,var,flag,flagvalue):
        if not var in self.dict:
            self._makeShadowCopy(var)
        self.dict[var][flag] = flagvalue

    def getVarFlag(self,var,flag):
        local_var = self._findVar(var)
        if local_var:
            if flag in local_var:
                return copy.copy(local_var[flag])
        return None

    def delVarFlag(self,var,flag):
        local_var = self._findVar(var)
        if not local_var:
            return
        if not var in self.dict:
            self._makeShadowCopy(var)

        if var in self.dict and flag in self.dict[var]:
            del self.dict[var][flag]

    def setVarFlags(self,var,flags):
        if not var in self.dict:
            self._makeShadowCopy(var)

        for i in flags.keys():
            if i == "content":
                continue
            self.dict[var][i] = flags[i]

    def getVarFlags(self,var):
        local_var = self._findVar(var)
        flags = {}

        if local_var:
            for i in self.dict[var].keys():
                if i == "content":
                    continue
                flags[i] = self.dict[var][i]

        if len(flags) == 0:
            return None
        return flags


    def delVarFlags(self,var):
        if not var in self.dict:
            self._makeShadowCopy(var)

        if var in self.dict:
            content = None

            # try to save the content
            if "content" in self.dict[var]:
                content  = self.dict[var]["content"]
                self.dict[var]            = {}
                self.dict[var]["content"] = content
            else:
                del self.dict[var]


    def createCopy(self):
        """
        Create a copy of self by setting _data to self
        """
        # we really want this to be a DataSmart...
        data = DataSmart()
        data.dict["_data"] = self.dict
        data._seen_overrides = copy.deepcopy(self._seen_overrides)
        data._special_values = copy.deepcopy(self._special_values)

        return data

    # Dictionary Methods
    def keys(self):
        def _keys(d, mykey):
            if "_data" in d:
                _keys(d["_data"],mykey)

            for key in d.keys():
                if key != "_data":
                    mykey[key] = None
        keytab = {}
        _keys(self.dict,keytab)
        return keytab.keys()

    def __getitem__(self,item):
        #print "Warning deprecated"
        return self.getVar(item, False)

    def __setitem__(self,var,data):
        #print "Warning deprecated"
        self.setVar(var,data)


